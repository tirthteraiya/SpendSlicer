"""Launch the local dashboard or run a diagnostic/CUR command."""

from __future__ import annotations

import argparse
import os
import sys

from spendslicer import __version__


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if args and args[0] == "cur":
        from spendslicer.cur.setup import main as cur_main
        try:
            return cur_main(args[1:])
        except ModuleNotFoundError as exc:
            if exc.name != "duckdb":
                raise
            print('CUR support is not installed. Run: pip install "spendslicer[cur]"', file=sys.stderr)
            return 2
    if args and args[0] == "doctor":
        from spendslicer.doctor import main as doctor_main
        return doctor_main(args[1:])

    parser = argparse.ArgumentParser(
        prog="spendslicer",
        description="Start the local AWS cost dashboard and open it in your default browser.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Other commands:\n"
               "  spendslicer doctor --help   AWS credential diagnostics\n"
               "  spendslicer cur --help      CUR warehouse commands (requires spendslicer[cur])\n"
               "  spendslicer-desktop         Native desktop window (requires spendslicer[desktop])\n\n"
               "Keep this terminal open while using the dashboard. Press Ctrl+C to stop.",
    )
    parser.add_argument("-V", "--version", action="version", version=f"spendslicer {__version__}")
    parser.add_argument("--host", default=os.environ.get("SPENDSLICER_HOST", "127.0.0.1"),
                        help="bind address (default: SPENDSLICER_HOST or 127.0.0.1)")
    parser.add_argument("--port", type=int, default=os.environ.get("SPENDSLICER_PORT", "8080"),
                        help="port, 1–65535 (default: SPENDSLICER_PORT or 8080)")
    parser.add_argument("--no-browser", action="store_true", help="start without opening a browser")
    options = parser.parse_args(args)
    if not 1 <= options.port <= 65535:
        parser.error("--port must be between 1 and 65535")

    from spendslicer.web.app import serve

    try:
        serve(host=options.host, port=options.port, open_browser=not options.no_browser)
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
