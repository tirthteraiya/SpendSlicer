"""CI check of the actual frozen executable, using empty temporary AWS files."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    binary = root / "dist" / "SpendSlicer" / ("SpendSlicer.exe" if sys.platform == "win32" else "SpendSlicer")
    with tempfile.TemporaryDirectory(prefix="SpendSlicer ü smoke ") as directory:
        temp = Path(directory)
        config, credentials = temp / "config", temp / "credentials"
        config.write_text("[profile testing-team]\nregion=us-east-1\n", encoding="utf-8")
        credentials.write_text("", encoding="utf-8")
        env = dict(os.environ)
        for key in list(env):
            if key.startswith("AWS_") or key.startswith("SPENDSLICER_"):
                env.pop(key)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        env.update({
            "AWS_CONFIG_FILE": str(config), "AWS_SHARED_CREDENTIALS_FILE": str(credentials),
            "AWS_EC2_METADATA_DISABLED": "true", "SPENDSLICER_CACHE_DIR": str(temp / "cache"),
            "SPENDSLICER_AUTH_TOKEN": "disposable-smoke-token", "SPENDSLICER_PORT": str(port),
        })
        process = subprocess.Popen([str(binary)], env=env)  # noqa: S603
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = f"http://127.0.0.1:{port}"
        def get(path, authenticated=True):
            headers = {"X-SpendSlicer-Token": "disposable-smoke-token"} if authenticated else {}
            return opener.open(urllib.request.Request(base + path, headers=headers), timeout=3)  # noqa: S310
        try:
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    raise RuntimeError(f"Frozen app exited before startup: {process.returncode}")
                try:
                    with get("/app") as response:
                        html = response.read().decode()
                    break
                except (urllib.error.URLError, OSError):
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Frozen app did not serve its dashboard") from None
                    time.sleep(0.2)
            assets = re.findall(r'(?:src|href)="(/app/assets/[^\"]+)"', html)
            assert assets, "Frozen dashboard is missing its bundled assets"
            for asset in assets:
                with get(asset) as response:
                    assert response.status == 200 and response.read()
            with get("/api/ui/context") as response:
                context = json.load(response)
            assert set(context["profiles"]) == {"default", "testing-team"}
            for path, authenticated, expected in (
                ("/api/ui/context", False, 401),
                ("/api/cost/summary/data?profile=testing-team", True, 400),
            ):
                try:
                    get(path, authenticated).close()
                except urllib.error.HTTPError as error:
                    assert error.code == expected, (path, error.code)
                else:
                    raise AssertionError(f"{path} should fail with {expected}")
            print("Frozen app: startup, assets, custom profile discovery, auth and missing-credential errors passed.")
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
