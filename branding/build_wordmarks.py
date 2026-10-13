"""Build portable outlined Manrope wordmarks. Dev-only: pip install fonttools brotli."""

import base64
import struct
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

KIT = Path(__file__).resolve().parent / "kit"
font = instantiateVariableFont(TTFont(KIT / "fonts/manrope-latin-wght-normal.woff2"), {"wght": 800})
glyphs = font.getGlyphSet()
cmap = font.getBestCmap()
scale = 96 / font["head"].unitsPerEm
parts = []
x = 0.0
# The selected symbol replaces the first S.
for letter in "pendSlicer":
    glyph = glyphs[cmap[ord(letter)]]
    pen = SVGPathPen(glyphs)
    glyph.draw(pen)
    parts.append(f'<path transform="translate({x:.3f} 0)" d="{pen.getCommands()}"/>')
    x += glyph.width - font["head"].unitsPerEm * 0.028
width = x * scale
lettering = "".join(parts)
master = (KIT / "mark-ink.png").read_bytes()
pw, ph = struct.unpack(">II", master[16:24])
png = base64.b64encode(master).decode()
colors = {"ink": "#0F1318", "white": "#FFFFFF", "lime": "#B9F467"}
for name, color in colors.items():
    symbol = (
        f'<defs><filter id="tint" color-interpolation-filters="sRGB">'
        f'<feFlood flood-color="{color}"/>'
        '<feComposite in2="SourceAlpha" operator="in"/></filter></defs>'
        f'<image width="{pw}" height="{ph}" filter="url(#tint)" '
        f'href="data:image/png;base64,{png}"/>'
    )
    (KIT / f"mark-{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {pw} {ph}">'
        f'<title>SpendSlicer angular S mark</title>{symbol}</svg>'
    )
    words = f'<g fill="{color}" transform="translate(0 78) scale({scale} {-scale})">{lettering}</g>'
    inline = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width + 90:.3f} 108">'
        '<title>SpendSlicer</title>'
        f'<g transform="translate(0 -12) scale({106 / pw} {106 / ph})">{symbol}</g>'
        f'<g transform="translate(90 0)">{words}</g></svg>'
    )
    for variant in ("wordmark", "lockup"):
        (KIT / f"{variant}-{name}.svg").write_text(inline)
    (KIT / f"stacked-{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} 420">'
        '<title>SpendSlicer</title>'
        f'<g transform="translate({(width - 300) / 2:.3f} 0) scale({300 / pw} {300 / ph})">{symbol}</g>'
        f'<g transform="translate(0 302)">{words}</g></svg>'
    )
print("Built 12 angular mark and outlined typography files")
