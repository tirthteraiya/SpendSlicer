"""Native desktop shell for the SpendSlicer dashboard.

Starts the FastAPI app on a loopback port in a background thread, then opens
the dashboard in the operating system's own webview — WebKit on macOS,
WebView2 on Windows. This is what the .dmg and .exe builds run.

Design notes
------------
*In-process server, not a subprocess.* A frozen PyInstaller binary re-executes
itself for any child process, so spawning a server subprocess would need
``multiprocessing.freeze_support`` plus argv sentinels to avoid a fork bomb. A
daemon thread running ``uvicorn.Server.run`` avoids that entirely.

*Ephemeral port.* Binding a fixed 8080 collides with anything already there —
including a second copy of SpendSlicer. We ask the OS for a free port and hand
that to uvicorn.

*Per-run auth token.* The server is loopback-only, but its CSRF check covers
only state-changing methods; a page in the user's browser could otherwise fire
cross-origin GETs at the port and spend real Cost Explorer money. So each run
mints a random token, exports it as SPENDSLICER_AUTH_TOKEN before the app is
imported, and passes it to the webview once via the URL.

*Browser fallback.* If pywebview is missing or no native webview is available
(a bare Linux container, an ancient Windows without WebView2), fall back to the
default browser rather than dying.
"""

from __future__ import annotations

import contextlib
import logging
import os
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

WINDOW_TITLE = "SpendSlicer"
_STARTUP_TIMEOUT_SECONDS = 45.0


def _storage_path() -> Path:
    """Where the webview keeps localStorage/cookies between runs."""
    base = os.environ.get("SPENDSLICER_CACHE_DIR")
    root = Path(base) if base else Path.home() / ".cache" / "spendslicer"
    return root / "webview"


def _wait_until_serving(url: str, token: str, timeout: float) -> bool:
    """Poll until the server answers, or the timeout expires."""
    deadline = time.monotonic() + timeout
    request = urllib.request.Request(url, headers={"X-SpendSlicer-Token": token})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            with opener.open(request, timeout=2) as resp:  # noqa: S310
                if resp.status == 200:
                    return True
        except urllib.error.HTTPError:
            pass  # a 401 or 404 is not a usable dashboard
        except (urllib.error.URLError, OSError, ConnectionError):
            pass  # not listening yet
        time.sleep(0.15)
    return False


def _start_server(host: str, port: int):
    """Reserve the socket before launching, so another process cannot take it."""
    import uvicorn

    from spendslicer.web.app import app

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=os.environ.get("SPENDSLICER_LOG_LEVEL", "warning"),
        access_log=False,
        # Windowed Windows executables have no stdout for isatty().
        use_colors=False,
    )
    server = uvicorn.Server(config)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.bind((host, port))
    except OSError:
        listener.close()
        raise
    port = int(listener.getsockname()[1])
    thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True, name="spendslicer-server")
    thread.start()
    return server, thread, port


def _open_window(url: str) -> bool:
    """Open the native webview. False if no webview backend is usable."""
    try:
        import webview
    except ImportError:
        log.warning("pywebview is not installed — falling back to the browser.")
        return False

    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.create_window(
            WINDOW_TITLE,
            url,
            width=1440,
            height=940,
            min_size=(1024, 700),
            confirm_close=False,
        )
        # Persist profile/period preferences across native app launches.
        # Financial cache entries live in the backend's account-bound SQLite cache.
        storage = _storage_path()
        storage.mkdir(parents=True, exist_ok=True)
        # Blocks until the user closes the window.
        webview.start(private_mode=False, storage_path=str(storage))
        return True
    except Exception as exc:
        log.warning("Native webview unavailable (%s) — falling back to the browser.", exc)
        return False


def main() -> int:
    logging.basicConfig(
        level=os.environ.get("SPENDSLICER_LOG_LEVEL", "WARNING").upper(),
        format="%(levelname)s %(name)s: %(message)s",
    )

    if sys.platform == "darwin":
        # An app opened from Finder gets PATH=/usr/bin:/bin:/usr/sbin:/sbin, so
        # a profile whose credential_process is a Homebrew tool (aws-vault,
        # granted, 1Password's op) fails here while working in the terminal.
        os.environ["PATH"] = os.pathsep.join(
            [os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin"]
        )

    host = "127.0.0.1"
    try:
        port = int(os.environ.get("SPENDSLICER_PORT") or 0)
        if not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
    except ValueError:
        log.error("SPENDSLICER_PORT must be an integer between 0 and 65535.")
        return 1

    # Must be set before spendslicer.web.app is imported: the app reads the token
    # at request time, but starting clean avoids any import-order surprise.
    token = os.environ.get("SPENDSLICER_AUTH_TOKEN") or secrets.token_urlsafe(32)
    os.environ["SPENDSLICER_AUTH_TOKEN"] = token

    try:
        server, thread, port = _start_server(host, port)
    except OSError as exc:
        log.error("Could not start the local server: %s", exc)
        return 1

    base = f"http://{host}:{port}"
    if not _wait_until_serving(f"{base}/app", token, _STARTUP_TIMEOUT_SECONDS):
        server.should_exit = True
        thread.join(timeout=5)
        # Windowed builds have sys.stderr = None; writing to it would crash.
        if sys.stderr:
            sys.stderr.write(
                f"SpendSlicer: the local server did not start within "
                f"{_STARTUP_TIMEOUT_SECONDS:.0f}s.\n"
            )
        return 1

    app_url = f"{base}/app?token={token}"

    try:
        if not _open_window(app_url):
            import webbrowser

            webbrowser.open(app_url)
            print(f"SpendSlicer is running at {base}/app")
            print("Press Ctrl+C to stop the server.")
            with contextlib.suppress(KeyboardInterrupt):
                threading.Event().wait()
    finally:
        server.should_exit = True
        thread.join(timeout=5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
