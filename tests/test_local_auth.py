import importlib

from fastapi.testclient import TestClient


def test_local_browser_reconnects_without_a_token(monkeypatch, tmp_path):
    from spendslicer.web import deps
    from spendslicer.web.sqlite_cache import SqliteCache

    # Verify the authenticated POST against a disposable cache, never the user's cache.
    monkeypatch.setattr(deps, "_cache", SqliteCache(tmp_path / "auth-test.db"))
    module = importlib.import_module("spendslicer.web.app")
    monkeypatch.delenv("SPENDSLICER_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("_SPENDSLICER_LOCAL_TOKEN", raising=False)
    token = module._ensure_auth_token()
    c = TestClient(module.app, base_url="http://localhost:8080", client=("127.0.0.1", 12345))
    assert c.get("/api/auth/local").status_code == 403
    headers = {"Sec-Fetch-Site": "same-origin", "X-SpendSlicer-Local-UI": "1"}
    response = c.get("/api/auth/local", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"token": token}
    assert response.headers["Cache-Control"] == "no-store"
    assert c.post("/api/cache/clear", headers={"X-SpendSlicer-Token": token}).status_code == 200
    for site in ("cross-site", "same-site", "none"):
        assert c.get("/api/auth/local", headers={**headers, "Sec-Fetch-Site": site}).status_code == 403
    assert c.get("/api/auth/local", headers={**headers, "Origin": "https://evil.example"}).status_code == 403
    assert c.get("/api/auth/local", headers={**headers, "Host": "evil.example"}).status_code == 403
    preflight = c.options("/api/auth/local", headers={"Origin": "https://evil.example", "Access-Control-Request-Headers": "x-spendslicer-local-ui", "Access-Control-Request-Method": "GET"})
    assert "Access-Control-Allow-Origin" not in preflight.headers


def test_remote_client_cannot_discover_local_token(monkeypatch):
    from spendslicer.web import app

    monkeypatch.setenv("SPENDSLICER_AUTH_TOKEN", "generated-token")
    monkeypatch.setenv("_SPENDSLICER_LOCAL_TOKEN", "generated-token")
    c = TestClient(app, base_url="http://localhost:8080", client=("192.0.2.1", 12345))
    assert c.get("/api/auth/local", headers={"Sec-Fetch-Site": "same-origin", "X-SpendSlicer-Local-UI": "1"}).status_code == 403


def test_configured_token_is_never_disclosed(monkeypatch):
    from spendslicer.web import app

    monkeypatch.setenv("SPENDSLICER_AUTH_TOKEN", "configured-token")
    monkeypatch.delenv("_SPENDSLICER_LOCAL_TOKEN", raising=False)
    c = TestClient(app, base_url="http://localhost:8080", client=("127.0.0.1", 12345))
    assert c.get("/api/auth/local", headers={"Sec-Fetch-Site": "same-origin", "X-SpendSlicer-Local-UI": "1"}).status_code == 403
