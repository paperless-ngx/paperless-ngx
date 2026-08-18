# PDF thumbnail generation: move off ImageMagick/Ghostscript

## Problem

`make_thumbnail_from_pdf()` (`src/documents/parsers.py`) generates document
thumbnails by handing the uploaded PDF directly to ImageMagick's `convert`
(`run_convert()`, same file), which in turn delegates PDF handling to
Ghostscript. This pulls in two heavyweight, general-purpose tools (an image
manipulation suite and a full PostScript interpreter) for what is
conceptually a narrow task: rasterize page 1 of a PDF to a small preview
image. Two subprocess calls are made per thumbnail today - one to `convert`
to rasterize, and (on the fallback path) another to `convert` again just to
turn a Ghostscript-produced PNG into the final WebP.

paperless already vendors better-scoped tools for each part of this job:
`poppler-utils` (already installed, `Dockerfile:157`, already used for
`pdftotext`) has its own dedicated PDF parser and renderer with no
general-purpose scripting/delegate machinery attached, and Pillow (already a
transitive dependency, already used throughout `src/` for raster image
handling) can do the resize/alpha-flatten/WebP-encode steps in-process
without a second subprocess call at all. Using purpose-built, narrowly-scoped
tools for each step is simpler to reason about and cheaper than routing PDF
thumbnailing through ImageMagick and Ghostscript.

The same reasoning applies a layer down: `make_thumbnail_from_pdf_gs_fallback()`
(same file) invokes `gs` directly as a subprocess when `convert` fails, then
calls `convert` a second time just for the WebP encode. That's three
subprocess calls (`gs`, then `convert` twice across both tiers) to produce
one thumbnail in the worst case.

## Goals

- Use narrowly-scoped, purpose-built tools for each step (PDF rasterization
  vs. raster image post-processing) instead of routing everything through
  ImageMagick/Ghostscript.
- Cut subprocess calls per thumbnail: one rasterize call, everything else
  in-process via Pillow (down from up to three subprocess calls across the
  two tiers today).
- Preserve current thumbnail behavior: ~500px-wide WebP image of page 1,
  alpha-flattened, correctly oriented.
- Preserve the existing two-tier resilience (primary renderer, then a
  fallback for PDFs the primary renderer can't handle).
- No new runtime dependencies - `poppler-utils` and Pillow are already
  installed/vendored (`Dockerfile:157`; Pillow via transitive dependency,
  already used throughout `src/` for raster image handling) and `qpdf` is
  already used elsewhere in consumption (`documents/consumer.py`).

## Non-goals

- Not touching `CONVERT_BINARY`/`run_convert()`/ImageMagick generally.
  `converters.py:convert_from_tiff_to_pdf` and
  `paperless/parsers/tesseract.py:remove_alpha` both still use
  `convert -alpha off` on already-classified raster images (TIFF/PNG/etc.),
  never on PDF bytes - out of scope here.
- Not touching `paperless-policy.xml`.
- Not changing thumbnail generation for non-PDF mime types (images go
  through a separate path already).

## Design

### Primary path: Poppler (`pdftoppm`) + Pillow

Use `pdftoppm` rather than `pdftocairo`. Both ship in the same
`poppler-utils` package already installed (`Dockerfile:157`), so there's no
dependency cost either way, but `pdftoppm` is the better fit: it renders via
Poppler's Splash backend, a single-purpose "rasterize a page" tool whose flag
set maps directly onto what's needed here (`-r` for DPI, `-f`/`-l` for page
range, `-cropbox`, `-png`). `pdftocairo`'s Cairo backend and extra output
formats (SVG/PS/PDF re-export) are aimed at use cases this doesn't have -
the rasterized page goes straight into Pillow for resize/flatten/WebP
encoding either way.

Replace the `run_convert()` call in `make_thumbnail_from_pdf()` with:

1. Rasterize page 1 only (`-f 1 -l 1`) of the PDF to PNG via `pdftoppm` at a
   DPI computed from the page's own geometry, rather than a fixed guess.
   - Use `-cropbox` to match the current `use_cropbox=True` behavior.
   - Page rotation is honored automatically from the page's `/Rotate` entry
     - no `-auto-orient` equivalent needed.
   - DPI: read the first page's box (CropBox, falling back to MediaBox) via
     `pikepdf` - already a project dependency, already used in
     `paperless/parsers/utils.py` for exactly this kind of PDF-structure
     inspection (`is_tagged_pdf`, `get_page_count_for_pdf`,
     `extract_pdf_metadata`) - and compute the DPI that renders the page at
     its target box-fit size in one pass: `min(72, target_width_px * 72 /
page_width_pts, target_height_px * 72 / page_height_pts)`, swapping
     width/height first if `/Rotate` is 90 or 270. The `min(72, ...)`
     reproduces the shrink-only behavior of the current `-scale 500x5000>`
     (never enlarge a page smaller than the target box) while rendering
     large pages directly at the resolution their thumbnail needs, instead
     of rendering high and downscaling. If the page box can't be read (e.g.
     a malformed/encrypted PDF pikepdf can't open), fall back to a
     conservative fixed DPI (150) rather than failing outright - the primary
     rasterization step itself may still fail on such a file and hand off to
     the qpdf-retry path below regardless.
2. Open the rendered PNG with Pillow and do the rest in-process instead of a
   second subprocess call:
   - Flatten any alpha onto a background, replacing `-alpha remove`.
   - `.thumbnail((500, 5000))` as a cheap safety-net clamp for any rounding
     in the DPI calculation above - normally a no-op since the render
     already targets the right size.
   - `.save(out_path, format="WEBP")`, replacing the second `convert` call
     that currently produces the `.webp` output.

### Fallback path: qpdf repair-and-retry, not Ghostscript

Replace `make_thumbnail_from_pdf_gs_fallback()`'s direct `gs` invocation with
a repair-and-retry step, keeping the same two-tier shape the code has today:

1. If the primary Poppler rasterization fails, run `qpdf --replace-input` (or
   equivalent, e.g. targeting a working copy so the original upload is
   untouched) to repair/normalize the PDF's structure. This mirrors the
   mime-mismatch cleanup already done in `documents/consumer.py`
   (`CONSUMER_PDF_RECOVERABLE_MIME_TYPES` branch), and is a better fit for
   "PDF failed to parse" than reaching for a full PostScript interpreter -
   qpdf's job is specifically repairing/normalizing PDF structure.
2. Retry the Poppler rasterization once against the repaired copy, then
   Pillow post-processing as in the primary path.
3. If that also fails, fall back to `get_default_thumbnail()`, same as the
   current code's ultimate fallback (`parsers.py:164-171`).

Ghostscript is no longer invoked anywhere in the thumbnail pipeline after
this change, but `GS_BINARY` and the `gs` binary-exists check in
`paperless/checks.py:85` stay as-is - `ocrmypdf` still depends on Ghostscript
for other work, so it remains a real, required dependency of the project
regardless of this change.

## Testing

- Existing thumbnail tests (`documents/tests/test_management_thumbnails.py`
  and thumbnail-related cases in the parser test suites) should continue to
  assert on output dimensions/format rather than exact pixel content, so
  swapping the renderer shouldn't require a wholesale test rewrite - but
  each test that currently mocks `run_convert`/`ImageMagick` invocations for
  thumbnailing needs updating to mock the new Poppler/Pillow calls instead.
- New test: a PDF that fails Poppler rasterization but is repairable by
  `qpdf` produces a thumbnail via the retry path (not just the generic
  fallback image) - covers the qpdf-repair branch specifically.
- New test: a PDF that fails both Poppler and qpdf-repair falls back to
  `get_default_thumbnail()`, matching current fallback-of-last-resort
  behavior.

## Open questions for the implementation plan

- Whether to also migrate `converters.py`/`tesseract.py`'s `convert -alpha
off` raster calls to in-process Pillow, as a follow-up cleanup (not
  required for this change, noted as a related opportunity).
