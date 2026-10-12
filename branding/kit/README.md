# SpendSlicer · final identity kit

The selected Dollar Slice logo combines an S, a dollar sign, and a diagonal slice.

Open `index.html` for the complete visual guide. Everything works locally.

## Assets

- `mark-ink.png`: approved transparent production silhouette, 1254 × 1254.
- `mark-ui.png`: 128px optimized copy for small interface marks.
- `mark-{ink,white,lime}.svg`: portable recolored symbol containers.
- `wordmark-{ink,white,lime}.svg`: Manrope 800 lettering converted to vector paths.
- `lockup-{ink,white,lime}.svg`: horizontal symbol and wordmark.
- `stacked-{ink,white,lime}.svg`: vertical symbol and wordmark.
- `app-icon.png`, `icon.ico`, `icon.icns`: desktop and browser icon assets.
- `overview.png`: generated presentation board; production files above are authoritative.
- `social-card.png` and `social-card.html`: share artwork and its editable source.
- `approved-reference.png`: the user's chosen shape.
- `fonts/`: locally bundled font files and their SIL Open Font Licenses.

The symbol is raster artwork embedded in the SVG containers, not a traced vector.
The wordmark lettering is fully outlined and does not depend on installed fonts.
All symbol color variants use the same alpha silhouette, preventing geometry drift.

## Theme and typography

Charcoal `#0F1318`, white `#FFFFFF`, cool slate `#E7EAEF`, Slice Lime `#B9F467`.
Use lime only for the identity and marketing action, with charcoal as its text color.
The operational dashboard keeps ink controls and its existing semantic status colors.
Never use lime text on white. Do not use brand lime to classify financial data.

Manrope 800 wordmark, −0.028em tracking; Manrope 800 headings, −0.032em;
Manrope 700 figures; Manrope 400–600 interface text. Tabular numerals for money.
JetBrains Mono 400 for code and literal identifiers only. Fonts remain local.

Clear space: at least one stem-width. Symbol: 24px preferred minimum.
Horizontal lockup: 160px preferred minimum. Never stretch, rotate, add effects,
change the diagonal gap, or substitute a font dollar character.

## Reproduction

From the repository root, run `python branding/build_wordmarks.py` with FontTools
and Brotli installed to regenerate the outlined wordmarks and SVG containers.
Run `python packaging/make_icons.py` with Pillow installed to regenerate desktop
formats from the approved app-icon master on any platform.
The raster masters are committed inputs. No image API is needed to rebuild them.

See `PROMPTS.md` for built-in image_gen provenance. Project artwork is distributed
under the repository's MIT license; bundled fonts retain their own licenses.
