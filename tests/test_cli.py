"""Public CLI contract and browser-launch readiness, without AWS calls."""

from __future__ import annotations

import asyncio
import builtins
import importlib
import threading
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest

from spendslicer import __version__
from spendslicer.cli import main


@pytest.mark.parametrize("args", [["--help"], ["-h"], ["--version"], ["-V"],
                                 ["doctor", "--help"], ["cur", "--help"]])
def test_information_commands_do_not_import_server_or_aws(args, monkeypatch, capsys):
    original_import = builtins.__import__

    def guarded_import(name, *a, **kw):
        assert name.split(".")[0] not in {"boto3", "botocore", "fastapi", "uvicorn", "duckdb"}
        return original_import(name, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert f"spendslicer {__version__}" in output if args[0] in {"--version", "-V"} else "usage:" in output


@pytest.fixture
def web(monkeypatch):
    module = importlib.import_module("spendslicer.web.app")
    monkeypatch.delenv("SPENDSLICER_HOST", raising=False)
    monkeypatch.delenv("SPENDSLICER_PORT", raising=False)
    return module


def test_bare_command_starts_dashboard_and_opens_browser(web, monkeypatch):
    launch = Mock()
    monkeypatch.setattr(web, "serve", launch)
    assert main([]) == 0
    launch.assert_called_once_with(host="127.0.0.1", port=8080, open_browser=True)


def test_launch_flags_override_environment(web, monkeypatch):
    launch = Mock()
    monkeypatch.setattr(web, "serve", launch)
    monkeypatch.setenv("SPENDSLICER_HOST", "0.0.0.0")
    monkeypatch.setenv("SPENDSLICER_PORT", "9000")
    assert main(["--host", "127.0.0.1", "--port", "8081", "--no-browser"]) == 0
    launch.assert_called_once_with(host="127.0.0.1", port=8081, open_browser=False)


def test_launch_uses_environment_defaults(web, monkeypatch):
    launch = Mock()
    monkeypatch.setattr(web, "serve", launch)
    monkeypatch.setenv("SPENDSLICER_HOST", "::1")
    monkeypatch.setenv("SPENDSLICER_PORT", "9090")
    assert main([]) == 0
    launch.assert_called_once_with(host="::1", port=9090, open_browser=True)


@pytest.mark.parametrize("args", [["--port", "0"], ["--port", "65536"], ["--port", "abc"],
                                 ["--unknown"], ["typo"]])
def test_invalid_arguments_never_launch(args, web, monkeypatch, capsys):
    launch = Mock()
    monkeypatch.setattr(web, "serve", launch)
    with pytest.raises(SystemExit) as exc:
        main(args)
    assert exc.value.code == 2
    launch.assert_not_called()
    assert "error:" in capsys.readouterr().err


def test_interrupt_returns_standard_exit_code(web, monkeypatch):
    monkeypatch.setattr(web, "serve", Mock(side_effect=KeyboardInterrupt))
    assert main([]) == 130


def test_doctor_offline_and_cur_arguments_still_dispatch(monkeypatch):
    doctor = importlib.import_module("spendslicer.doctor")
    check = Mock(return_value=0)
    monkeypatch.setattr(doctor, "run", check)
    assert main(["doctor", "--offline"]) == 0
    check.assert_called_once_with(check_identity=False)
    cur = importlib.import_module("spendslicer.cur.setup")
    command = Mock(return_value=0)
    monkeypatch.setattr(cur, "main", command)
    assert main(["cur", "status"]) == 0
    command.assert_called_once_with(["status"])


def test_missing_cur_extra_has_install_hint(monkeypatch, capsys):
    cur = importlib.import_module("spendslicer.cur.setup")
    monkeypatch.setattr(cur, "main", Mock(side_effect=ModuleNotFoundError(name="duckdb")))
    assert main(["cur", "status"]) == 2
    assert 'pip install "spendslicer[cur]"' in capsys.readouterr().err


@pytest.mark.parametrize("started,exiting", [(True, False), (False, True), (True, True)])
def test_browser_opens_only_after_successful_startup(started, exiting, web, monkeypatch, capsys):
    import uvicorn

    ready = threading.Event()
    opened = threading.Event()
    urls = []

    class Server:
        def __init__(self, config):
            self.started = False
            self.should_exit = False

        async def startup(self, sockets=None):
            self.started, self.should_exit = started, exiting
            if started and not exiting:
                ready.set()

        def run(self):
            asyncio.run(self.startup())

    def browser(url):
        assert ready.is_set()
        urls.append(url)
        opened.set()

    monkeypatch.setattr(uvicorn, "Server", Server)
    monkeypatch.setattr(web, "_open_browser", browser)
    monkeypatch.setenv("SPENDSLICER_AUTH_TOKEN", "custom+token&value")
    web.serve(host="::1", port=9090, open_browser=True)
    if started and not exiting:
        assert opened.wait(2)
        assert urlsplit(urls[0]).netloc == "[::1]:9090"
        assert parse_qs(urlsplit(urls[0]).query)["token"] == ["custom+token&value"]
        assert urls[0] in capsys.readouterr().out
    else:
        assert not opened.is_set()


@pytest.mark.parametrize("result", [False, OSError("No graphical browser")])
def test_browser_failure_keeps_manual_link_available(result, web, monkeypatch, caplog):
    import webbrowser

    browser = Mock(return_value=result) if result is False else Mock(side_effect=result)
    monkeypatch.setattr(webbrowser, "open", browser)
    web._open_browser("http://127.0.0.1:8080/app?token=test")
    assert "Open the dashboard link" in caplog.text


def test_default_browser_receives_url(web, monkeypatch):
    import webbrowser

    browser = Mock(return_value=True)
    monkeypatch.setattr(webbrowser, "open", browser)
    web._open_browser("http://127.0.0.1:8080/app?token=test")
    browser.assert_called_once_with("http://127.0.0.1:8080/app?token=test")


def test_no_browser_uses_existing_server_path(web, monkeypatch):
    import uvicorn

    server = Mock()
    browser = Mock()
    monkeypatch.setattr(uvicorn, "run", server)
    monkeypatch.setattr(web, "_open_browser", browser)
    web.serve(open_browser=False)
    server.assert_called_once_with(web.app, host="127.0.0.1", port=8080, access_log=False)
    browser.assert_not_called()


def test_real_server_is_reachable_when_default_browser_opens(web, monkeypatch):
    import socket
    import urllib.request
    import webbrowser

    import uvicorn
    from fastapi import FastAPI

    app = FastAPI()

    @app.get("/app")
    def index():
        return {"ready": True}

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]

    servers = []
    responses = []
    original_run = uvicorn.Server.run

    def run(server, *args, **kwargs):
        servers.append(server)
        timeout = threading.Timer(5, lambda: setattr(server, "should_exit", True))
        timeout.daemon = True
        timeout.start()
        try:
            return original_run(server, *args, **kwargs)
        finally:
            timeout.cancel()

    def browser(url):
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(url, timeout=2) as response:
                responses.append((response.status, response.read()))
        finally:
            servers[0].should_exit = True
        return True

    monkeypatch.setattr(web, "app", app)
    monkeypatch.setattr(uvicorn.Server, "run", run)
    monkeypatch.setattr(webbrowser, "open", browser)
    web.serve(port=port, open_browser=True)
    assert responses == [(200, b'{"ready":true}')]
