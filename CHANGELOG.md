# Changelog

Notable changes to SpendSlicer. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semver](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-10-12

First public release.

- Final Angular Slice identity: the symbol replaces the first S in Manrope
  wordmarks, with a charcoal/white/slate/lime brand
  palette, downloadable local brand guide, and macOS/Windows/browser icons.
- The app and landing page share the selected logo; brand accents preserve the
  dashboard's existing financial status colors.
- Subtle landing entrances and hover motion respect reduced-motion preferences.

Numbered 1.0.0 rather than 0.x deliberately. The surface people actually
depend on — the CLI, the environment variables and the HTTP endpoints — is
settled, and the accuracy work still ahead makes estimates *better* rather
than breaking anyone's integration. A 0.x label would have understated how
usable this is while buying no real freedom.

### Added

- **On PyPI.** `pipx install spendslicer` gets the dashboard; the tag-triggered
  release workflow publishes through PyPI trusted publishing, and refuses to
  run when the tag and `spendslicer.__version__` disagree.
- **Seven more services named without setup**: NAT Gateway, ElastiCache,
  Secrets Manager, Route 53, EFS, ECR and CloudFront — fifteen in all. NAT,
  ElastiCache, Secrets Manager, Route 53 and EFS are priced from a known rate;
  ECR and CloudFront split the Cost Explorer total by image bytes and bytes
  downloaded.
- **`spendslicer doctor`** prints which credential and config files boto3 is
  reading, every profile it can see, and whether each one resolves. It makes no
  billable calls.
- `python -m spendslicer` runs the CLI.
- **Native desktop builds** for macOS (`.dmg`, Apple Silicon and Intel) and
  Windows (`.zip`). The app binds an OS-assigned loopback port, runs the server
  in-process, and renders the dashboard in the platform webview — WebKit on
  macOS, WebView2 on Windows — falling back to the default browser when no
  webview backend exists. Builds are currently unsigned; see
  [docs/DESKTOP.md](docs/DESKTOP.md).
- **Per-launch auth token in the desktop builds.** Each run mints a random
  `SPENDSLICER_AUTH_TOKEN` and passes it to the webview. A loopback bind alone was
  not enough: the CSRF check only covers state-changing methods, so any page in
  the user's browser could fire cross-origin `GET`s at the port and spend real
  Cost Explorer money.
- **Documentation**: architecture, configuration reference, least-privilege IAM
  policy, CUR setup, desktop install/build, contributing guide, security policy.
- **CI** on Python 3.10–3.14 plus frontend tests, and a PyInstaller smoke build
  on macOS and Windows so packaging breakage surfaces on PRs. A gate fails the
  build when the committed dashboard bundle is stale relative to `frontend/src`.

### Fixed

- **Currency figures display without a line through the digits** in both the
  dashboard and landing page, while keeping the rolling number animation.
- **The landing demo shows a varied testing-3 environment**, including databases,
  servers and S3 buckets, with Top resources visible in its initial screen.
- **Existing browser tabs reconnect automatically** after a local web server
  restart. A loopback-only same-origin handshake refreshes the generated token
  and retries rejected API requests once, restoring account and period pickers
  without weakening token checks or disclosing configured secrets.
- **Web launches now require authentication by default.** A random token is
  generated at launch and a protected dashboard link is printed. Configured
  tokens are preserved, every request validates its hostname, and request
  access logs are disabled to keep token-bearing URLs out of them.
- **PDF export now works after a plain install.** `fpdf2` is a core dependency,
  matching the PDF option offered by the dashboard.
- **Paying Cost Explorer twice for the same numbers.** The trend chart, the
  Resources page total and the forecast each made their own call for data
  already cached, and every export re-ran the full multi-region resource scan
  (~20 calls). All of them now read the cache. Two profiles on one account
  (`default` and `prod`, or several SSO roles) also paid separately; caches are
  keyed by account now.
- **One paid EC2 query per region**, mostly for regions with no EC2 spend.
  Regions with no EC2 spend are now skipped, using a per-region breakdown the
  scan already fetches.
- **EC2 per-resource costs left out today's spend**, and on the 1st of the
  month every EC2 query was rejected outright (start date equal to end date).
- **Dollars vanishing from the Resources total.** ElastiCache, Secrets Manager,
  EFS, ECR, CloudFront and Route 53 had no remainder row, so a failed scan or an
  under-priced formula silently dropped their cost. ECR was multiplied by the
  region count when the regional call failed, and CloudFront and Route 53
  appeared in single-region views.
- **NAT gateways double counted.** They bill into "EC2 - Other" alongside EBS,
  which was rescaled to the full bucket while NAT rows added their cost on top.
- **Credentials.** Profiles are discovered through boto3, so
  `AWS_CONFIG_FILE`, `AWS_SHARED_CREDENTIALS_FILE`, SSO and `credential_process`
  profiles all appear. `default` now means the default credential chain (which
  includes environment variables and instance roles) rather than only a
  profile literally named `default`. Missing credentials fail once with the
  fix in the message instead of one stack trace per region and an empty
  dashboard, and an expired SSO session says to run `aws sso login`.
- **The macOS app couldn't run `credential_process` helpers** installed by
  Homebrew (aws-vault, granted, 1Password's `op`) when launched from Finder,
  which starts apps with a minimal `PATH`.
- RI and Savings Plans utilisation/coverage budgets were read backwards.
- One region blocked by an organization policy (SCP) marked EBS as failed
  everywhere, and a pricing-API timeout failed the whole service's scan.
- Windows: the windowed desktop build crashed while reporting a startup
  timeout, and corrupt-cache recovery could block startup when another process
  held the file open.
- **The dashboard 404'd outside a git checkout.** The React bundle was resolved
  relative to the repo root, so an installed wheel looked for it inside
  site-packages and a frozen build failed outright. Vite now builds into
  `spendslicer/web/static` and a resolver handles all three layouts.
- **Startup blocked on AWS.** Profile resolution ran inline in the lifespan,
  holding the port closed for ~15s with five profiles — far longer with an
  expired SSO session or a downed VPN. It now warms in the background: 15s → 1.1s.
- **`serve()` defaulted to `reload=True`**, which both run scripts used. Reload
  re-execs via a watcher and breaks frozen builds. Now opt-in via
  `SPENDSLICER_RELOAD=1`.
- **CUR ingest could hang shutdown**, sitting in `time.sleep` for up to 6 hours
  with no shutdown hook. It now waits on an event the lifespan sets.
- The Pricing API cache measured TTL with `datetime.utcnow().timestamp()`, which
  reads a naive UTC value as local time. The skew cancelled out, so the TTL
  worked by luck; it now uses a monotonic clock.
- Removed every deprecated `datetime.utcnow()` call and migrated the three
  `@app.on_event` handlers to a lifespan context manager. Test-suite warnings
  went from 19 to 2, both from Starlette itself.

### Changed

- `fastapi` and `uvicorn` are core dependencies, so `pip install spendslicer`
  runs the dashboard. `spendslicer[web]` still installs.
- Open-window cost data is cached for the app-wide TTL (30 minutes) rather than
  15, since Cost Explorer only refreshes a few times a day.
- Regions with no EC2 spend no longer show free-tier instances as $0 rows.
- **Renamed to SpendSlicer.** The project previously carried three names at once:
  the `aws_cost_ultra` package, the `aws-cost-dashboard` repo, and a
  "Cloud Ledger" brand rendered in the UI, PDF reports, and export filenames.
  Environment variables moved from `ACU_*` to `SPENDSLICER_*` and the auth header
  from `X-ACU-Token` to `X-SpendSlicer-Token`. No back-compat aliases — there were
  no released users.
- **Minimum Python is now 3.10** (3.9 is end-of-life).
- Dropped `reportlab`, declared as a dependency but imported nowhere.
- Removed `requirements.txt`; it duplicated `pyproject.toml` and had drifted,
  pinning `pytest` as a runtime dependency while missing real ones.
- Lint clean: 196 ruff findings → 0.
- Stripped ~30 `FINDING NN` markers referencing a private audit tracker, plus
  `Phase 1/2/3` planning notes, keeping the reasoning they annotated.
- Corrected the README's accuracy claim. It advertised exact per-instance EC2
  cost via Cost Explorer `RESOURCE_ID`; that path had been removed because
  `GetCostAndUsageWithResources` bills $0.00001 per usage record and dominated
  running cost. Per-resource figures are estimates unless the CUR warehouse is
  enabled, and the docs now say so.

### Known limitations

- The Pricing API fallback table only carries `ap-south-1` rates.
- Desktop builds are unsigned, so macOS Gatekeeper and Windows SmartScreen warn
  on first launch.

[1.0.0]: https://github.com/tirthteraiya/SpendSlicer/releases/tag/v1.0.0
