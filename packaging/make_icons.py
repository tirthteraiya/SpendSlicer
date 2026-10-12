#!/usr/bin/env python3
"""Convert the approved SpendSlicer app-icon master to desktop formats.

Run `python packaging/make_icons.py`. The committed branding/kit/app-icon.png
is the source of truth; this script only resizes and converts formats.
Pillow is required for PNG, ICO, and ICNS output on every platform.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    sys.exit("Pillow is required: pip install Pillow")

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "packaging/icons"
MASTER = ROOT / "branding/kit/app-icon.png"


def write_icns(master: Path, dest: Path) -> None:
    """Encode PNG-backed macOS icon entries on every platform."""
    with Image.open(master) as src:
        src.save(dest, format="ICNS")


def write_ico(master: Path, dest: Path) -> None:
    """Multi-resolution .ico. Pillow writes these on every platform."""
    src = Image.open(master)
    sizes = [(px, px) for px in (16, 24, 32, 48, 64, 128, 256)]
    src.save(dest, format="ICO", sizes=sizes)


def main() -> int:
    with Image.open(MASTER) as source:
        if source.width != source.height or source.width < 1024:
            raise ValueError("The approved icon master must be square and at least 1024px")
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        master = OUT_DIR / "icon.png"
        source.convert("RGBA").resize((1024, 1024), Image.LANCZOS).save(master)
    ico = OUT_DIR / "icon.ico"
    write_ico(master, ico)
    icns = OUT_DIR / "icon.icns"
    write_icns(master, icns)
    print("Converted the approved icon to PNG and desktop formats")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
