"""Launch external credential helpers with the system's library paths.

PyInstaller changes DLL/shared-library lookup for its own bundled modules.
Those paths must not leak into aws-vault, aws or another credential_process.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading

from botocore.credentials import ProcessProvider

_spawn_lock = threading.Lock()


def _popen(*args, **kwargs):
    env = dict(kwargs.pop("env", os.environ))
    for key in ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"):
        if f"{key}_ORIG" in env:
            env[key] = env[f"{key}_ORIG"]
        else:
            env.pop(key, None)
    bundle = os.path.normcase(os.path.abspath(sys._MEIPASS))
    env["PATH"] = os.pathsep.join(
        p for p in env.get("PATH", "").split(os.pathsep)
        if not p or not os.path.normcase(os.path.abspath(p)).startswith(bundle + os.sep)
        and os.path.normcase(os.path.abspath(p)) != bundle
    )
    if sys.platform != "win32":
        return subprocess.Popen(*args, env=env, **kwargs)  # noqa: S603

    import ctypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.SetDllDirectoryW.argtypes = [ctypes.c_wchar_p]
    # DLL lookup is process-wide: clear it only for the short spawn interval.
    with _spawn_lock:
        size = kernel.GetDllDirectoryW(0, None)
        original = ctypes.create_unicode_buffer(size + 1)
        kernel.GetDllDirectoryW(size + 1, original)
        kernel.SetDllDirectoryW(None)
        try:
            return subprocess.Popen(*args, env=env, **kwargs)  # noqa: S603
        finally:
            kernel.SetDllDirectoryW(original.value or None)


def configure(session) -> None:
    resolver = session.get_component("credential_provider")
    resolver.get_provider("custom-process")._popen = _popen
    # SDK extension point is private; the platform tests exercise both direct
    # and source_profile helpers so SDK upgrades cannot silently break it.
    builder = resolver.get_provider("assume-role")._profile_provider_builder
    builder._create_process_provider = lambda profile_name: ProcessProvider(
        profile_name, load_config=lambda: session.full_config, popen=_popen,
    )
