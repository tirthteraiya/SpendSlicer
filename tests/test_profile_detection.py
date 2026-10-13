"""Local credential resolution: no AWS requests, exercised on all three OSes."""
import json
import sys
from types import SimpleNamespace

import pytest
from botocore.exceptions import SSOTokenLoadError
from fastapi import HTTPException

from spendslicer.aws.session import (
    aws_config_locations,
    list_profiles,
    make_session,
    profile_config_fingerprint,
)
from spendslicer.web import context, deps


@pytest.fixture
def aws_files(tmp_path, monkeypatch):
    root = tmp_path / "AWS profiles ü with spaces"
    root.mkdir()
    config, credentials = root / "config", root / "credentials"
    config.write_text("", encoding="utf-8")
    credentials.write_text("[default]\naws_access_key_id=default-key\naws_secret_access_key=test-secret\n[prod]\naws_access_key_id=prod-key\naws_secret_access_key=test-secret\n", encoding="utf-8")
    monkeypatch.setenv("AWS_CONFIG_FILE", str(config))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(credentials))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    for key in ("AWS_PROFILE", "AWS_DEFAULT_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    return config, credentials


@pytest.mark.parametrize("variable", ["AWS_PROFILE", "AWS_DEFAULT_PROFILE"])
def test_explicit_default_and_named_profile_ignore_environment_selection(aws_files, monkeypatch, variable):
    monkeypatch.setenv(variable, "prod")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "environment-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "environment-secret")
    assert make_session("default").get_credentials().access_key == "default-key"
    assert deps.get_session("default").get_credentials().access_key == "default-key"
    assert make_session("prod").get_credentials().access_key == "prod-key"
    assert make_session().get_credentials().access_key == "environment-key"


def test_invalid_environment_profile_does_not_hide_defined_profiles(aws_files, monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "deleted-profile")
    assert list_profiles() == ["default", "prod"]


def test_environment_only_credentials_remain_selectable(aws_files, monkeypatch):
    aws_files[1].write_text("")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "environment-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "environment-secret")
    assert deps.get_profiles() == ["default"]
    assert deps.get_session("default").get_credentials().access_key == "environment-key"


def test_custom_paths_and_sso_profiles_are_discovered_without_signing_in(aws_files):
    config, credentials = aws_files
    config.write_text("[profile sso-team]\nsso_session=company\nsso_account_id=123456789012\nsso_role_name=ReadOnly\n[sso-session company]\nsso_start_url=https://example.invalid/start\nsso_region=us-east-1\n", encoding="utf-8")
    assert list_profiles() == ["default", "prod", "sso-team"]
    assert aws_config_locations()["config_file"] == str(config)
    assert aws_config_locations()["credentials_file"] == str(credentials)


def test_credential_process_runs_from_a_path_with_spaces(aws_files):
    config, _ = aws_files
    helper = config.parent / "credential helper.py"
    payload = {"Version": 1, "AccessKeyId": "process-key", "SecretAccessKey": "test-secret"}
    helper.write_text(f"print({json.dumps(json.dumps(payload))})", encoding="utf-8")
    config.write_text(f'[profile process]\ncredential_process="{sys.executable}" "{helper.as_posix()}"\n', encoding="utf-8")
    credentials = deps.get_session("process").get_credentials()
    assert credentials.method == "custom-process"
    assert credentials.get_frozen_credentials().access_key == "process-key"


def test_profile_discovery_does_not_wait_for_identity_calls(aws_files, monkeypatch):
    monkeypatch.setattr(context, "cache_get", lambda key: None)
    pending = []
    monkeypatch.setattr(context, "schedule_refresh", lambda key, producer: pending.append(producer))
    monkeypatch.setattr(context, "load_profile_bundle", lambda *args: pytest.fail("picker blocked on AWS"))
    assert [p["profile"] for p in context.get_profile_choices()] == ["default", "prod"]
    assert len(pending) == 1


def test_profile_file_changes_invalidate_choices_and_cost_caches(aws_files, monkeypatch):
    monkeypatch.setattr(context, "cache_get", lambda key: None)
    monkeypatch.setattr(context, "schedule_refresh", lambda *args: None)
    before = profile_config_fingerprint()
    namespace = deps.cache_ns("prod")
    aws_files[1].write_text("[prod]\naws_access_key_id=repointed-key\naws_secret_access_key=test-secret\n[new-team]\naws_access_key_id=new-key\naws_secret_access_key=test-secret\n")
    assert profile_config_fingerprint() != before
    assert deps.cache_ns("prod") != namespace
    assert [p["profile"] for p in context.get_profile_choices()] == ["default", "new-team", "prod"]


def test_identity_labels_keep_profiles_distinct_and_skip_region_discovery(monkeypatch):
    written = []
    def bundle(profile, regions):
        assert regions == []
        return SimpleNamespace(profile=profile, account_id="123456789012", display_name=lambda: "company")
    monkeypatch.setattr(context, "load_profile_bundle", bundle)
    monkeypatch.setattr(context, "cache_set", lambda key, value, **kwargs: written.append((value, kwargs)))
    context._resolve_profile_choices("test", ["prod", "dev"])
    assert [p["label"] for p in written[0][0]] == ["dev · company (123456789012)", "prod · company (123456789012)"]
    assert written[0][1] == {"ttl_seconds": 60, "swr_seconds": 0}


def test_expired_sso_is_one_actionable_error(monkeypatch):
    class Session:
        def get_credentials(self):
            raise SSOTokenLoadError(error_msg="Token does not exist")
    monkeypatch.setattr(deps, "make_session", lambda **kwargs: Session())
    with pytest.raises(HTTPException) as error:
        deps.get_session("default")
    assert "aws sso login" in error.value.detail
    assert context.friendly_error(error.value) == error.value.detail


def test_initial_selection_honors_sdk_environment_profile(aws_files, monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_PROFILE", "prod")
    monkeypatch.setattr(context, "cache_get", lambda key: None)
    monkeypatch.setattr(context, "schedule_refresh", lambda *args: None)
    assert context.base_ctx("", "mtd", "dashboard")["active_profile"] == "prod"


def test_helper_account_changes_invalidate_cache_without_a_config_edit(aws_files, monkeypatch):
    from botocore.credentials import Credentials
    current = [Credentials("first-account-key", "test-secret")]
    session = SimpleNamespace(get_credentials=lambda: current[0])
    monkeypatch.setattr(deps, "get_session", lambda profile: session)
    config_revision = profile_config_fingerprint()
    first = deps.cache_ns("prod")
    current[0] = Credentials("second-account-key", "other-secret", "new-token")
    assert profile_config_fingerprint() == config_revision
    assert deps.cache_ns("prod") != first
    assert "first-account-key" not in first and "test-secret" not in first


def test_expired_credentials_cannot_reuse_a_warm_route_cache(aws_files, monkeypatch):
    from spendslicer.web.routes import cost
    monkeypatch.setattr(deps, "get_session", lambda profile: (_ for _ in ()).throw(
        HTTPException(status_code=400, detail="SSO expired")))
    monkeypatch.setattr(cost, "cache_get", lambda key: pytest.fail("must authenticate before cache lookup"))
    with pytest.raises(HTTPException, match="SSO expired"):
        cost.api_cost_summary_data(profile="prod", period="mtd")


def test_request_pins_credentials_but_the_next_request_resolves_again(aws_files, monkeypatch):
    from botocore.credentials import Credentials
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from spendslicer.web.middleware import CECountingMiddleware
    calls = []
    def session(profile):
        calls.append(profile)
        return SimpleNamespace(get_credentials=lambda: Credentials(f"key-{len(calls)}", "secret"))
    monkeypatch.setattr(deps, "make_session", session)
    app = FastAPI()
    app.add_middleware(CECountingMiddleware)
    @app.get("/probe")
    def probe():
        first = deps.cache_ns("prod")
        second = deps.cache_ns("prod")
        return {"same": first == second}
    client = TestClient(app)
    assert client.get("/probe").json()["same"]
    assert calls == ["prod"]
    assert client.get("/probe").json()["same"]
    assert calls == ["prod", "prod"]


@pytest.mark.parametrize("nested", [False, True])
def test_frozen_helpers_do_not_inherit_bundled_library_paths(aws_files, monkeypatch, nested):
    import os
    config, _ = aws_files
    bundle = config.parent / "bundled libraries"
    bundle.mkdir()
    original_path = os.environ.get("PATH", "")
    monkeypatch.setenv("PATH", str(bundle) + os.pathsep + original_path)
    monkeypatch.setenv("LD_LIBRARY_PATH", str(bundle))
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "system-library-path")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    helper = config.parent / "frozen helper.py"
    helper.write_text("import os,json\nassert os.environ['LD_LIBRARY_PATH']=='system-library-path'\nassert " + repr(str(bundle)) + " not in os.environ['PATH'].split(os.pathsep)\nprint(json.dumps({'Version':1,'AccessKeyId':'process-key','SecretAccessKey':'test-secret'}))\n", encoding="utf-8")
    config.write_text(f'[profile process]\ncredential_process="{sys.executable}" "{helper.as_posix()}"\n', encoding="utf-8")
    session = make_session("process")
    if nested:
        # AssumeRoleProvider uses this same builder for every source_profile.
        resolver = session._session.get_component("credential_provider")
        builder = resolver.get_provider("assume-role")._profile_provider_builder
        credentials = builder._create_process_provider("process").load()
    else:
        credentials = session.get_credentials()
    assert credentials.get_frozen_credentials().access_key == "process-key"
    assert os.environ["LD_LIBRARY_PATH"] == str(bundle)


def test_offline_doctor_does_not_call_expired_sso_credentials_working(monkeypatch, capsys):
    import boto3

    from spendslicer import doctor
    monkeypatch.setattr("spendslicer.aws.session.list_profiles", lambda: ["expired"])
    class Credentials:
        method = "sso"
        def get_frozen_credentials(self):
            raise SSOTokenLoadError(error_msg="Token expired")
    monkeypatch.setattr(boto3, "Session", lambda **kwargs: SimpleNamespace(get_credentials=lambda: Credentials()))
    assert doctor.run(check_identity=False) == 1
    assert "No working credentials" in capsys.readouterr().out


@pytest.mark.parametrize("kind", ["audit", "budgets"])
def test_audit_and_budgets_require_credentials_before_warm_cache(aws_files, monkeypatch, kind):
    from spendslicer.web.routes import audit_api, export_api
    monkeypatch.setattr(deps, "get_session", lambda profile: (_ for _ in ()).throw(
        HTTPException(status_code=400, detail="SSO expired")))
    if kind == "audit":
        monkeypatch.setattr(audit_api, "cache_get_swr", lambda key: pytest.fail("auth required first"))
    else:
        monkeypatch.setattr(deps, "cache_get", lambda key: pytest.fail("auth required first"))
    with pytest.raises(HTTPException, match="SSO expired"):
        if kind == "audit":
            audit_api.api_audit_summary_data("prod", "all", 0)
        else:
            export_api.api_budgets_data("prod")


def test_audit_does_not_fan_out_without_a_verified_account(monkeypatch):
    from spendslicer.web.routes import audit_api
    monkeypatch.setattr(audit_api, "get_session", lambda profile: object())
    monkeypatch.setattr(audit_api, "load_profile_bundle", lambda *args, **kwargs: SimpleNamespace(account_id=None))
    monkeypatch.setattr(audit_api, "run_audit", lambda *args, **kwargs: pytest.fail("unverified identity fan-out"))
    assert "verify the AWS account" in audit_api.build_audit_ctx("prod", "all", 0)["error"]


def test_utf8_bom_profiles_and_nested_sdk_config_are_preserved(aws_files):
    config, credentials = aws_files
    config.write_text("[profile équipe]\nregion=us-east-1\ns3 =\n    addressing_style=path\n", encoding="utf-8-sig")
    credentials.write_text("[équipe]\naws_access_key_id=utf8-key\naws_secret_access_key=test-secret\n", encoding="utf-8-sig")
    assert list_profiles() == ["équipe"]
    session = make_session("équipe")
    assert session.get_credentials().access_key == "utf8-key"
    assert session._session.get_scoped_config()["s3"] == {"addressing_style": "path"}


def test_legacy_windows_encoded_profiles_still_work(aws_files, monkeypatch):
    import locale
    config, credentials = aws_files
    config.write_bytes("[profile équipe]\nregion=us-east-1\n".encode("cp1252"))
    credentials.write_bytes("[équipe]\naws_access_key_id=ansi-key\naws_secret_access_key=test-secret\n".encode("cp1252"))
    monkeypatch.setattr(locale, "getpreferredencoding", lambda *args: "cp1252")
    assert list_profiles() == ["équipe"]
    assert make_session("équipe").get_credentials().access_key == "ansi-key"
