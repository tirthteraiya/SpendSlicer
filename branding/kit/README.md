# SpendSlicer · final identity kit

The selected Angular Slice logo is a geometric S with a diagonal slice and no
vertical dollar stem. It supplies the first S: **logo + pendSlicer**, with no
extra S beside it. Standalone icons contain the symbol alone.

Open `index.html` for the complete visual guide. Everything works locally.

## Assets

- `mark-ink.png`: approved transparent production silhouette.
- `mark-ui.png`: 128px optimized copy for small interface marks.
- `mark-{ink,white,lime}.svg`: portable recolored symbol containers.
- `wordmark-{ink,white,lime}.svg`: angular S followed by outlined Manrope 800 pendSlicer.
- `lockup-{ink,white,lime}.svg`: aliases of the complete horizontal wordmark.
- `stacked-{ink,white,lime}.svg`: vertical symbol followed by pendSlicer.
- `app-icon.png`, `icon.ico`, `icon.icns`: desktop and browser icon assets.
- `overview.png` and `overview.html`: presentation board and editable source.
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

Clear space: at least one diagonal band-width around standalone marks. Symbol:
24px preferred minimum; integrated interface lettering may use a 22px canvas.
Horizontal lockup: 160px preferred minimum. Never stretch, rotate, add effects,
change the diagonal gap, or add a vertical dollar stem. Do not prepend the symbol
to the full written name. Ordinary prose and accessible names remain SpendSlicer.

Landing motion uses short entrances, staggered service rows, tab-content fades,
and small hover lifts. Content remains visible if animation or observation fails.
All decorative motion is disabled when reduced motion is requested.

## Reproduction

From the repository root, run `python branding/build_wordmarks.py` with FontTools
and Brotli installed to regenerate the outlined wordmarks and SVG containers.
Run `python packaging/make_icons.py` with Pillow installed to regenerate desktop
formats from the approved app-icon master on any platform.
The raster masters are committed inputs. No image API is needed to rebuild them.

See `PROMPTS.md` for built-in image_gen provenance. Project artwork is distributed
under the repository's MIT license; bundled fonts retain their own licenses.
