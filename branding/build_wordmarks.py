"""Build portable outlined Manrope wordmarks. Dev-only: pip install fonttools brotli."""

import base64
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
for letter in "SpendSlicer":
    glyph = glyphs[cmap[ord(letter)]]
    pen = SVGPathPen(glyphs)
    glyph.draw(pen)
    parts.append(f'<path transform="translate({x:.3f} 0)" d="{pen.getCommands()}"/>')
    x += glyph.width - font["head"].unitsPerEm * 0.028
width = x * scale
assert 450 < width < 650, width
lettering = "".join(parts)
png = base64.b64encode((KIT / "mark-ink.png").read_bytes()).decode()
colors = {"ink": "#0F1318", "white": "#FFFFFF", "lime": "#B9F467"}
for name, color in colors.items():
    symbol = (
        f'<defs><filter id="tint" color-interpolation-filters="sRGB">'
        f'<feFlood flood-color="{color}"/>'
        '<feComposite in2="SourceAlpha" operator="in"/></filter></defs>'
        f'<image width="1254" height="1254" filter="url(#tint)" '
        f'href="data:image/png;base64,{png}"/>'
    )
    (KIT / f"mark-{name}.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1254 1254">'
        f'<title>SpendSlicer dollar-slice mark</title>{symbol}</svg>'
    )
    words = f'<g fill="{color}" transform="translate(0 78) scale({scale} {-scale})">{lettering}</g>'
    (KIT / f"wordmark-{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} 108">'
        f'<title>SpendSlicer</title>{words}</svg>'
    )
    (KIT / f"lockup-{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width + 150:.3f} 160">'
        '<title>SpendSlicer</title>'
        f'<g transform="translate(0 0) scale({160 / 1254})">{symbol}</g>'
        f'<g transform="translate(150 36)">{words}</g></svg>'
    )
    (KIT / f"stacked-{name}.svg").write_text(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.3f} 420">'
        '<title>SpendSlicer</title>'
        f'<g transform="translate({(width - 300) / 2:.3f} 0) scale({300 / 1254})">{symbol}</g>'
        f'<g transform="translate(0 302)">{words}</g></svg>'
    )
print("Built 12 mark and outlined typography files")
