"""AWS session factory — multi-profile, multi-region, parallel fan-out.

Exports:
  - ``accessible_regions(session)`` — EC2 describe_regions
  - ``account_alias_for(session)`` — IAM list_account_aliases
  - ``ProfileBundle`` — one fully-resolved profile: session + account + regions
  - ``load_profile_bundle(profile, regions)`` — single-profile loader
  - ``all_profile_bundles(regions)`` — loads all local profiles in parallel
  - ``fanout(bundles, fn, max_workers)`` — parallel execution across profiles
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

import boto3
import botocore.session
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)

T = TypeVar("T")

# Regions to fall back to when EC2 describe_regions isn't available
_FALLBACK_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-1",
    "us-west-2",
    "eu-west-1",
    "eu-west-2",
    "eu-central-1",
    "ap-south-1",
    "ap-southeast-1",
    "ap-southeast-2",
    "ap-northeast-1",
]


@dataclass
class ProfileBundle:
    """Fully-resolved AWS profile: session, account identity, and usable regions.

    One instance per profile. Create via ``load_profile_bundle()`` or
    ``all_profile_bundles()``; don't construct directly unless testing.
    """

    profile: str
    session: boto3.Session
    account_id: str | None = None
    account_alias: str | None = None
    regions: list[str] = field(default_factory=list)

    def display_name(self) -> str:
        """Human label: alias preferred, then account ID, then profile name."""
        return self.account_alias or self.account_id or self.profile

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"ProfileBundle(profile={self.profile!r}, "
            f"account={self.account_id!r}, alias={self.account_alias!r}, "
            f"regions={len(self.regions)})"
        )


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

def make_session(profile: str | None = None, region: str | None = None) -> boto3.Session:
    """Select an explicit profile, or let boto3 resolve its default chain.

    Explicit "default" selects [default] when it exists. Without that section,
    keep the environment/instance-role fallback for machines with no profiles.
    """
    kw: dict = {}
    # Explicit default must not inherit AWS_PROFILE or environment keys when
    # a literal default profile exists. No profile delegates to boto3's chain.
    if profile and (profile != "default" or "default" in list_profiles()):
        kw["profile_name"] = profile
    if region:
        kw["region_name"] = region
    session = boto3.Session(**kw)
    if getattr(sys, "frozen", False):
        from spendslicer.aws.process_credentials import configure
        configure(session._session)
    return session


# ---------------------------------------------------------------------------
# Profile discovery
# ---------------------------------------------------------------------------

def list_profiles() -> list[str]:
    """Every profile boto3 itself can see.

    This used to parse ~/.aws/credentials and ~/.aws/config by hand with
    configparser. That hardcoded the location and so ignored
    AWS_SHARED_CREDENTIALS_FILE and AWS_CONFIG_FILE, which botocore honours —
    common in CI, containers and corporate setups. The dropdown then listed a
    different set of profiles than the ones sessions actually resolve against,
    which is the confusing half of "the CLI sees my profile but the app does
    not".

    Delegating to botocore keeps the two in agreement by construction, and
    picks up the SSO and credential_process forms the hand parser never
    handled. Note it reports profiles that are *defined*, which is not the
    same as profiles whose credentials resolve — get_session checks that.
    """
    try:
        return sorted(botocore.session.Session().available_profiles)
    except Exception as exc:
        # A malformed config file makes botocore raise here. Returning empty
        # lets get_profiles() fall back to "default" rather than 500 the
        # whole dashboard on a stray character in someone's config.
        log.warning(
            "Could not read AWS profiles (%s); falling back to the default "
            "credential chain. Check ~/.aws/config and ~/.aws/credentials.",
            type(exc).__name__,
        )
        return []


def aws_config_locations() -> dict[str, str]:
    """Where boto3 is actually reading credentials and config from.

    Surfaced in diagnostics because the usual cause of "works in my shell,
    not in the app" is the two processes resolving different files — a
    different HOME/USERPROFILE, or one of the AWS_*_FILE env vars set in only
    one of them.
    """
    try:
        bs = botocore.session.Session()
        return {
            "credentials_file": os.path.expandvars(os.path.expanduser(
                bs.get_config_variable("credentials_file") or ""
            )),
            "config_file": os.path.expandvars(os.path.expanduser(
                bs.get_config_variable("config_file") or ""
            )),
            "profile_env": os.environ.get("AWS_DEFAULT_PROFILE") or os.environ.get("AWS_PROFILE", ""),
        }
    except Exception:
        return {}


def profile_config_fingerprint() -> str:
    """Invalidate discovery and fallback caches when local credential sources change."""
    digest = hashlib.sha256()
    for key, value in sorted(aws_config_locations().items()):
        digest.update(f"{key}={value}\0".encode())
        if key.endswith("_file"):
            try:
                digest.update(Path(value).read_bytes())
            except OSError:
                digest.update(b"unreadable")
    for key in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
                "AWS_ROLE_ARN", "AWS_WEB_IDENTITY_TOKEN_FILE",
                "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "AWS_CONTAINER_CREDENTIALS_FULL_URI"):
        digest.update(f"{key}={os.environ.get(key, '')}\0".encode())
    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Account identity helpers
# ---------------------------------------------------------------------------

def account_id_for(session: boto3.Session) -> str | None:
    """Return the 12-digit AWS account id, or None if STS is unavailable."""
    try:
        return session.client("sts").get_caller_identity()["Account"]
    except (ClientError, KeyError, Exception):
        return None


def account_alias_for(session: boto3.Session) -> str | None:
    """Return the first IAM account alias, or None if none configured / no permission."""
    try:
        resp = session.client("iam").list_account_aliases()
        aliases = resp.get("AccountAliases", [])
        return aliases[0] if aliases else None
    except Exception as exc:
        log.warning("account_alias_for: IAM list_account_aliases failed: %s", type(exc).__name__)
        log.debug("account_alias_for traceback", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Region discovery
# ---------------------------------------------------------------------------

def accessible_regions(session: boto3.Session) -> list[str]:
    """Return opted-in region names for this account, sorted alphabetically.

    Uses EC2 describe_regions with ``AllRegions=False`` so disabled/not-opted-in
    regions are excluded. Falls back to a hardcoded safe set if the call fails
    (e.g. sandbox accounts, no EC2 perms).
    """
    try:
        ec2 = session.client("ec2", region_name="us-east-1")
        resp = ec2.describe_regions(Filters=[{"Name": "opt-in-status", "Values": ["opt-in-not-required", "opted-in"]}])
        return sorted(r["RegionName"] for r in resp.get("Regions", []))
    except Exception as exc:
        log.warning(
            "accessible_regions: EC2 describe_regions failed, using fallback "
            "list: %s", type(exc).__name__,
        )
        log.debug("accessible_regions traceback", exc_info=True)
        return list(_FALLBACK_REGIONS)


# ---------------------------------------------------------------------------
# ProfileBundle loader
# ---------------------------------------------------------------------------

def load_profile_bundle(
    profile: str | None = None,
    regions: list[str] | None = None,
    *,
    session: boto3.Session | None = None,
) -> ProfileBundle:
    """Build a fully-resolved ProfileBundle for one profile.

    If ``regions`` is None, the account's accessible regions are discovered
    via EC2 describe_regions (one API call).
    """
    session = session if session is not None else make_session(profile)
    profile_name = profile or "default"
    account = account_id_for(session)
    alias = account_alias_for(session)
    resolved_regions = regions if regions is not None else accessible_regions(session)
    return ProfileBundle(
        profile=profile_name,
        session=session,
        account_id=account,
        account_alias=alias,
        regions=resolved_regions,
    )


def all_profile_bundles(
    regions: list[str] | None = None,
    max_workers: int = 8,
) -> list[ProfileBundle]:
    """Load all local profiles in parallel, returning one ProfileBundle each.

    Profiles that fail credential validation are silently skipped (they'll
    appear as None in intermediate results and be filtered out).
    """
    profiles = list_profiles()
    if not profiles:
        return []

    bundles: list[ProfileBundle] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(profiles))) as pool:
        futures = {
            pool.submit(load_profile_bundle, p, regions): p
            for p in profiles
        }
        for fut in as_completed(futures):
            try:
                bundle = fut.result()
                if bundle.account_id:  # skip profiles that can't authenticate
                    bundles.append(bundle)
            except Exception as exc:
                log.warning(
                    "all_profile_bundles: skipping profile=%s: %s",
                    futures[fut], type(exc).__name__,
                )
                log.debug("all_profile_bundles traceback", exc_info=True)

    return sorted(bundles, key=lambda b: b.profile)


# ---------------------------------------------------------------------------
# Parallel fan-out
# ---------------------------------------------------------------------------

def fanout(
    bundles: list[ProfileBundle],
    fn: Callable[[ProfileBundle], T],
    max_workers: int = 8,
) -> list[tuple[ProfileBundle, T | Exception]]:
    """Run ``fn(bundle)`` for each bundle in parallel.

    Returns a list of (bundle, result_or_exception) pairs in the order
    results complete. Callers decide how to handle per-profile failures —
    this function never silently swallows them.
    """
    if not bundles:
        return []

    results: list[tuple[ProfileBundle, T | Exception]] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(bundles))) as pool:
        future_to_bundle = {pool.submit(fn, b): b for b in bundles}
        for fut in as_completed(future_to_bundle):
            bundle = future_to_bundle[fut]
            try:
                results.append((bundle, fut.result()))
            except Exception as exc:
                results.append((bundle, exc))

    return results


def fanout_regions(
    bundle: ProfileBundle,
    fn: Callable[[boto3.Session, str], T],
    max_workers: int = 8,
) -> list[tuple[str, T | Exception]]:
    """Run ``fn(session, region)`` for each region in a ProfileBundle in parallel.

    Useful for resource enumeration that must run once per region.
    """
    if not bundle.regions:
        return []

    results: list[tuple[str, T | Exception]] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(bundle.regions))) as pool:
        future_to_region = {
            pool.submit(fn, bundle.session, region): region
            for region in bundle.regions
        }
        for fut in as_completed(future_to_region):
            region = future_to_region[fut]
            try:
                results.append((region, fut.result()))
            except Exception as exc:
                results.append((region, exc))

    return results
