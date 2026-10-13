"""Real loopback startup plus native-window behavior, without AWS calls."""
import importlib
import socket
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from spendslicer import desktop


@pytest.mark.parametrize("windowed", [False, True])
def test_server_owns_its_port_and_serves_without_using_a_proxy(monkeypatch, windowed):
    app = FastAPI()
    @app.get("/app")
    def index():
        return HTMLResponse("<html>SpendSlicer</html>")
    module = importlib.import_module("spendslicer.web.app")
    monkeypatch.setattr(module, "app", app)
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("NO_PROXY", "")
    if windowed:
        monkeypatch.setattr(sys, "stdout", None)
        monkeypatch.setattr(sys, "stderr", None)
    server, thread, port = desktop._start_server("127.0.0.1", 0)
    try:
        assert port > 0
        assert desktop._wait_until_serving(f"http://127.0.0.1:{port}/app", "test-token", 5)
        with socket.socket() as other, pytest.raises(OSError):
            other.bind(("127.0.0.1", port))
    finally:
        server.should_exit = True
        thread.join(timeout=5)
    assert not thread.is_alive()


def test_exports_are_enabled_in_native_windows(monkeypatch, tmp_path):
    webview = SimpleNamespace(settings={}, create_window=MagicMock(), start=MagicMock())
    monkeypatch.setitem(sys.modules, "webview", webview)
    monkeypatch.setenv("SPENDSLICER_CACHE_DIR", str(tmp_path / "cache with spaces"))
    assert desktop._open_window("http://127.0.0.1:8080/app")
    assert webview.settings["ALLOW_DOWNLOADS"] is True
    assert webview.start.call_args.kwargs["private_mode"] is False
    assert desktop._storage_path().is_dir()


def test_no_native_renderer_falls_back_to_the_browser(monkeypatch):
    webview = SimpleNamespace(settings={}, create_window=MagicMock(side_effect=RuntimeError("No GUI")))
    monkeypatch.setitem(sys.modules, "webview", webview)
    assert desktop._open_window("http://127.0.0.1:8080/app") is False


@pytest.mark.parametrize("port", ["abc", "65536", "-1"])
def test_invalid_port_is_an_actionable_failure(monkeypatch, caplog, port):
    monkeypatch.setenv("SPENDSLICER_PORT", port)
    assert desktop.main() == 1
    assert "SPENDSLICER_PORT" in caplog.text


def test_main_stops_the_server_when_the_window_closes(monkeypatch):
    server, thread = SimpleNamespace(should_exit=False), MagicMock()
    monkeypatch.setenv("SPENDSLICER_PORT", "0")
    monkeypatch.setattr(desktop, "_start_server", lambda *args: (server, thread, 12345))
    monkeypatch.setattr(desktop, "_wait_until_serving", lambda *args: True)
    monkeypatch.setattr(desktop, "_open_window", lambda url: True)
    assert desktop.main() == 0
    assert server.should_exit is True
    thread.join.assert_called_once()
