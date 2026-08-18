# PDF thumbnail generation: move off ImageMagick/Ghostscript Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ImageMagick/Ghostscript in the PDF-thumbnail pipeline (`make_thumbnail_from_pdf` and its fallback in `src/documents/parsers.py`) with `pdftoppm` (Poppler, already installed) for rasterization and Pillow (already a dependency) for the alpha-flatten/WebP-encode step, cutting per-thumbnail subprocess calls from up to three down to one, with no new runtime dependencies.

**Architecture:** `make_thumbnail_from_pdf()` calls a new `get_pdf_first_page_size_points()` helper (via `pikepdf`, already a dependency) to compute the render DPI from the page's actual geometry, then a new `rasterize_pdf_page_to_png()` (subprocess: `pdftoppm`, rendered at that computed DPI) then a new `encode_thumbnail_webp()` (in-process: Pillow) instead of `run_convert()`. The fallback, renamed in place from `make_thumbnail_from_pdf_gs_fallback()` to `make_thumbnail_from_pdf_qpdf_fallback()`, repairs the PDF with `qpdf` and retries the same path instead of shelling out to `gs`. `get_default_thumbnail()` remains the final fallback, unchanged. Callers (`tika.py`, `mail.py`, `tesseract.py`, `remote.py`) are unaffected — `make_thumbnail_from_pdf(in_path, temp_dir, logging_group)`'s signature and return type (`Path`) don't change.

**Tech Stack:** Poppler (`pdftoppm`), pikepdf, Pillow (`PIL.Image`), qpdf — all already installed/vendored. ruff, pytest.

**Spec:** `docs/superpowers/specs/2026-08-18-pdf-thumbnail-poppler-migration-design.md`

## Global Constraints

- No new runtime/OS dependencies — `poppler-utils`, `pikepdf`, Pillow, and `qpdf` are already installed. (spec: Goals)
- `GS_BINARY`/`gs` and the `gs` entry in `paperless/checks.py`'s `binaries_check` are **not removed** — `ocrmypdf` still depends on Ghostscript elsewhere, so it remains a required project dependency regardless of this change.
- `CONVERT_BINARY`/`run_convert()` stay as-is and keep their two existing non-PDF call sites (`documents/converters.py:convert_from_tiff_to_pdf`, `paperless/parsers/tesseract.py:remove_alpha`) — this plan does not touch either.
- No new startup binary check and no new settings entry for `pdftoppm`. `pdftotext` — already shelled out to in `paperless/parsers/utils.py:extract_pdf_text` — has neither a `binaries_check` entry nor a `PAPERLESS_*_BINARY` settings override, so `pdftoppm` follows that same precedent: a hardcoded `"pdftoppm"` literal, nothing else.
- Thumbnail output behavior is unchanged: WebP, page 1 only, cropbox-respecting, alpha-flattened, correctly oriented, fit within 500×5000 shrink-only (matches today's `-scale 500x5000>` — never enlarges a smaller page).
- **DPI resolution:** compute DPI from the first page's actual box (CropBox, falling back to MediaBox) via `pikepdf`, rather than a fixed guess or a downscale-after-render approach — see Task 1. This renders every page at the exact resolution its thumbnail needs in one pass, for both small pages (no upscaling) and large pages (no wasted high-res render followed by a throwaway downscale).
- Backend tests run via `uv run pytest <targets>` from the repo root. `ruff check` / `ruff format` run locally (global binary, not `uv run ruff`).

## Reference: current vs. new behavior in `src/documents/parsers.py`

| Current                                                                                                                   | New                                                                                                                                                                             |
| ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make_thumbnail_from_pdf()` → `run_convert(input_file=f"{in_path}[0]", ...)` at implicit density, then `-scale 500x5000>` | `make_thumbnail_from_pdf()` → `get_pdf_first_page_size_points()` (pikepdf) → `rasterize_pdf_page_to_png()` (pdftoppm, at the computed DPI) → `encode_thumbnail_webp()` (Pillow) |
| On failure → `make_thumbnail_from_pdf_gs_fallback()`: `gs` render to PNG, then `run_convert()` to WebP                    | On failure → `make_thumbnail_from_pdf_qpdf_fallback()`: `qpdf --replace-input` repair, retry the same path                                                                      |
| On fallback failure → `get_default_thumbnail()`                                                                           | unchanged                                                                                                                                                                       |

## Task 1: Implement the Poppler + pikepdf + Pillow primary thumbnail path

**Agent:** python-expert — **Model:** opus (highest-risk task in this plan — every PDF thumbnail in the app is visually affected, existing tests only assert `thumb.is_file()` rather than dimensions/fidelity, and the DPI-from-page-geometry math has several easy-to-get-wrong edge cases: rotated pages, missing CropBox, zero/degenerate page boxes, unreadable/encrypted PDFs — get any of these wrong and it either silently ships blurry/oversized/undersized thumbnails or crashes on a class of real-world files)

**Files:**

- Modify: `src/paperless/parsers/utils.py` (add `get_pdf_first_page_size_points()`)
- Modify: `src/documents/parsers.py` (add `rasterize_pdf_page_to_png()` and `encode_thumbnail_webp()`; rewrite `make_thumbnail_from_pdf()` to use them instead of `run_convert()`)
- Test: `src/paperless/tests/parsers/test_parse_modes.py` or a new test module for `get_pdf_first_page_size_points()` (co-locate with the other `pikepdf`-based helper tests in `paperless/parsers/utils.py` — check for an existing test file covering `is_tagged_pdf`/`get_page_count_for_pdf` first and add alongside them)
- Test: `src/paperless/tests/parsers/test_tesseract_parser.py` (`TestGetThumbnail`, lines 271-311)

**Interfaces:**

- Produces:
  - `get_pdf_first_page_size_points(path: Path, log: logging.Logger | None = None) -> tuple[float, float] | None` in `paperless/parsers/utils.py`, following the exact signature/docstring/exception-handling style of the other helpers already in that file (`is_tagged_pdf`, `get_page_count_for_pdf`).
  - `rasterize_pdf_page_to_png(in_path: Path, out_path: Path, *, dpi: int, use_cropbox: bool = True, logging_group=None) -> None` in `documents/parsers.py` (note: `dpi` is now a required positional-or-keyword arg, not defaulted — Task 1 always computes it explicitly).
  - `encode_thumbnail_webp(png_path: Path, out_path: Path, *, max_width: int = 500, max_height: int = 5000) -> None` in `documents/parsers.py`.
  - All three consumed by Task 2's fallback.

- [ ] **Step 1: Add `get_pdf_first_page_size_points()` to `paperless/parsers/utils.py`**

Follows the same `pikepdf`-open/try-except-log-and-return-fallback style as `is_tagged_pdf` (lines 29-65) and `get_page_count_for_pdf` (lines 236-265) in the same file:

```python
def get_pdf_first_page_size_points(
    path: Path,
    log: logging.Logger | None = None,
) -> tuple[float, float] | None:
    """Return the first page's (width, height) in PDF points, post-rotation.

    Uses ``page.cropbox`` (pikepdf 10.2.0, pinned in uv.lock) — this is a
    read-only property, not a raw dict lookup, and already implements the
    PDF-spec-correct fallback/inheritance to MediaBox when a page has no
    ``/CropBox`` of its own (confirmed against pikepdf's own
    ``_get_cropbox(True, False)`` implementation and by testing against
    `src/documents/tests/samples/simple.pdf`, which has no ``/CropBox`` key
    at all). This must match whatever box the renderer is told to use
    (pdftoppm's ``-cropbox`` flag), or the computed DPI will target the
    wrong box's dimensions. Swaps width/height when ``/Rotate`` is 90 or
    270, since that's the orientation the page will actually be rendered
    in — note ``page.rotate`` is a *mutator* method
    (``rotate(angle, relative) -> None``) in this pikepdf version, not a
    getter; the current rotation must be read via
    ``page.obj.get("/Rotate", 0)`` instead (confirmed: returns ``None``
    cleanly, not an exception, when the key is absent).

    Parameters
    ----------
    path:
        Absolute path to the PDF file.
    log:
        Logger for warnings. Falls back to the module-level logger when omitted.

    Returns
    -------
    tuple[float, float] | None
        (width_points, height_points), or ``None`` if the file can't be
        opened, has no pages, or the page box is missing/degenerate.
    """
    import pikepdf

    _log = log or logger
    try:
        with pikepdf.Pdf.open(path) as pdf:
            if len(pdf.pages) == 0:
                return None
            page = pdf.pages[0]
            llx, lly, urx, ury = (float(v) for v in page.cropbox)
            width = abs(urx - llx)
            height = abs(ury - lly)
            if width <= 0 or height <= 0:
                return None
            rotate = int(page.obj.get("/Rotate", 0)) % 360
            if rotate in (90, 270):
                width, height = height, width
            return width, height
    except Exception:
        _log.warning(
            "Could not determine PDF page size for %s",
            path,
            exc_info=True,
        )
        return None
```

`page.cropbox`/`page.mediabox` returning `pikepdf.Array` (indexable, four numeric elements) and `page.obj.get("/Rotate", 0)` behavior were both confirmed directly against the pinned version rather than assumed — no further verification needed during implementation.

- [ ] **Step 2: Add `rasterize_pdf_page_to_png()` to `documents/parsers.py`**

Follows the same `run_subprocess`/logging pattern as `run_convert()` (`parsers.py:71-120`) and the `pdftotext` invocation in `paperless/parsers/utils.py:extract_pdf_text` (lines 86-103):

```python
def rasterize_pdf_page_to_png(
    in_path: Path,
    out_path: Path,
    *,
    dpi: int,
    use_cropbox: bool = True,
    logging_group=None,
) -> None:
    """
    Rasterizes page 1 of a PDF to a PNG via pdftoppm (Poppler), at the given DPI.
    """
    # pdftoppm normally appends a page-number suffix to the output filename;
    # -singlefile suppresses that so out_path is written exactly as given.
    args = [
        "pdftoppm",
        "-f", "1", "-l", "1",
        "-r", str(dpi),
        "-png",
        "-singlefile",
    ]
    if use_cropbox:
        args.append("-cropbox")
    args += [str(in_path), str(out_path.with_suffix(""))]

    logger.debug("Execute: " + " ".join(args), extra={"group": logging_group})

    try:
        run_subprocess(args, logger=logger)
    except subprocess.CalledProcessError as e:
        raise ParseError(f"pdftoppm failed at {args}") from e
```

Note `-singlefile` plus a target path _without_ extension — `pdftoppm` appends `.png` itself when `-png` is given, so pass `out_path.with_suffix("")` as the output argument and confirm the resulting file is exactly `out_path`.

- [ ] **Step 3: Add `encode_thumbnail_webp()` to `documents/parsers.py`**

```python
def encode_thumbnail_webp(
    png_path: Path,
    out_path: Path,
    *,
    max_width: int = 500,
    max_height: int = 5000,
) -> None:
    """
    Flattens alpha and saves as WebP. max_width/max_height are a safety-net
    clamp only (the render is already sized correctly by rasterize_pdf_page_to_png's
    computed DPI) — this never enlarges, matching ImageMagick's -scale WxH> semantics.
    """
    from PIL import Image

    with Image.open(png_path) as im:
        if im.mode in ("RGBA", "LA"):
            background = Image.new("RGB", im.size, (255, 255, 255))
            background.paste(im, mask=im.split()[-1])
            im = background
        else:
            im = im.convert("RGB")

        im.thumbnail((max_width, max_height))
        im.save(out_path, format="WEBP")
```

- [ ] **Step 4: Rewrite `make_thumbnail_from_pdf()`**

Replace the `run_convert(...)` call (`parsers.py:182-193`) with:

```python
def make_thumbnail_from_pdf(in_path: Path, temp_dir: Path, logging_group=None) -> Path:
    """
    The thumbnail of a PDF is just a 500px wide image of the first page.
    """
    png_path: Path = temp_dir / "page1.png"
    out_path: Path = temp_dir / "convert.webp"

    try:
        dpi = _compute_thumbnail_dpi(in_path, logging_group=logging_group)
        rasterize_pdf_page_to_png(
            in_path,
            png_path,
            dpi=dpi,
            use_cropbox=True,
            logging_group=logging_group,
        )
        encode_thumbnail_webp(png_path, out_path)
    except ParseError as e:
        logger.error(f"Unable to make thumbnail with pdftoppm: {e}")
        out_path = make_thumbnail_from_pdf_qpdf_fallback(in_path, temp_dir, logging_group)

    return out_path
```

Add the small DPI-computation helper alongside it (private to this module — not part of Task 1's public interface list above, it's an implementation detail of `make_thumbnail_from_pdf`/the qpdf fallback):

```python
_THUMBNAIL_MAX_WIDTH = 500
_THUMBNAIL_MAX_HEIGHT = 5000
_THUMBNAIL_FALLBACK_DPI = 150  # used only if page geometry can't be read


def _compute_thumbnail_dpi(in_path: Path, logging_group=None) -> int:
    from paperless.parsers.utils import get_pdf_first_page_size_points

    size = get_pdf_first_page_size_points(in_path)
    if size is None:
        logger.debug(
            "Could not read PDF page size, using fallback DPI",
            extra={"group": logging_group},
        )
        return _THUMBNAIL_FALLBACK_DPI

    width_pts, height_pts = size
    dpi_for_width = _THUMBNAIL_MAX_WIDTH * 72 / width_pts
    dpi_for_height = _THUMBNAIL_MAX_HEIGHT * 72 / height_pts
    # min(72, ...) reproduces "-scale WxH>" shrink-only behavior: never
    # render at higher than natural (72dpi/1px-per-point) resolution for a
    # page already smaller than the target box.
    return max(1, round(min(72, dpi_for_width, dpi_for_height)))
```

(`make_thumbnail_from_pdf_qpdf_fallback` and its call to `_compute_thumbnail_dpi` are added in Task 2 — this task will not compile/pass tests standalone until Task 2 lands; that's expected, do both before running the test suite, or temporarily stub the fallback name to unblock this task's own test run.)

- [ ] **Step 5: Add tests for `get_pdf_first_page_size_points()`**

Cover: a normal PDF (returns expected width/height for a known sample), a PDF with `/Rotate 90` (width/height swapped vs. the unrotated equivalent), and a nonexistent/corrupt path (returns `None`, doesn't raise). Use existing sample PDFs under `src/paperless/tests/parsers/samples/` or `src/documents/tests/samples/` where possible rather than adding new binary fixtures.

- [ ] **Step 6: Add a dimension/format assertion to `TestGetThumbnail`**

The existing tests (`test_tesseract_parser.py:271-311`) only assert `thumb.is_file()`. Add an explicit check that the output is actually a correctly-shaped WebP, e.g.:

```python
def test_thumbnail_is_correct_format_and_size(
    self,
    tesseract_parser: RasterisedDocumentParser,
    tesseract_samples_dir: Path,
) -> None:
    thumb = tesseract_parser.get_thumbnail(
        tesseract_samples_dir / "simple-digital.pdf",
        "application/pdf",
    )
    with Image.open(thumb) as im:
        assert im.format == "WEBP"
        assert im.width <= 500
        assert im.height <= 5000
```

This is the test that would have caught a resize/DPI-math regression in this task — don't skip it.

- [ ] **Step 7: Ruff (syntax only at this point — full run happens after Task 2)**

```bash
ruff check src/documents/parsers.py src/paperless/parsers/utils.py
ruff format src/documents/parsers.py src/paperless/parsers/utils.py
```

- [ ] **Step 8: Commit**

```bash
git add src/documents/parsers.py src/paperless/parsers/utils.py src/paperless/tests/parsers/test_tesseract_parser.py
git commit -m "refactor: rasterize PDF thumbnails with pdftoppm+pikepdf+Pillow instead of ImageMagick"
```

(Full test run deferred to Task 2, since `make_thumbnail_from_pdf`'s exception path references the fallback function that task creates.)

## Task 2: Replace the Ghostscript fallback with qpdf repair-and-retry

**Agent:** python-expert — **Model:** sonnet (follows an existing pattern almost exactly — the `qpdf --replace-input` cleanup already in `documents/consumer.py:441-448` — lower novelty than Task 1)

**Files:**

- Modify: `src/documents/parsers.py` (rename/rewrite `make_thumbnail_from_pdf_gs_fallback()` → `make_thumbnail_from_pdf_qpdf_fallback()`)
- Test: `src/paperless/tests/parsers/test_tesseract_parser.py` (`TestGetThumbnail`)

**Interfaces:**

- Consumes: `rasterize_pdf_page_to_png()`, `encode_thumbnail_webp()`, `_compute_thumbnail_dpi()` (Task 1).
- Produces: `make_thumbnail_from_pdf_qpdf_fallback(in_path: Path, temp_dir: Path, logging_group=None) -> Path`, called from `make_thumbnail_from_pdf()` (Task 1, Step 4).

- [ ] **Step 1: Rewrite the fallback function**

Replace `make_thumbnail_from_pdf_gs_fallback()` (`parsers.py:130-171`) with:

```python
def make_thumbnail_from_pdf_qpdf_fallback(in_path, temp_dir, logging_group=None) -> Path:
    png_path: Path = Path(temp_dir) / "page1_repaired.png"
    out_path: Path = Path(temp_dir) / "convert_qpdf.webp"
    repaired_path: Path = Path(temp_dir) / "repaired.pdf"

    logger.warning(
        "Thumbnail generation with pdftoppm failed, attempting qpdf "
        "repair and retry.",
        extra={"group": logging_group},
    )

    try:
        try:
            shutil.copy(in_path, repaired_path)
            run_subprocess(
                ["qpdf", "--replace-input", str(repaired_path)],
                logger=logger,
            )
        except subprocess.CalledProcessError as e:
            raise ParseError(f"qpdf repair failed for {in_path}") from e

        dpi = _compute_thumbnail_dpi(repaired_path, logging_group=logging_group)
        rasterize_pdf_page_to_png(
            repaired_path,
            png_path,
            dpi=dpi,
            use_cropbox=True,
            logging_group=logging_group,
        )
        encode_thumbnail_webp(png_path, out_path)

        return out_path

    except ParseError as e:
        logger.error(f"Unable to make thumbnail after qpdf repair: {e}")
        # The caller might expect a generated thumbnail that can be moved,
        # so we need to copy it before it gets moved.
        # https://github.com/paperless-ngx/paperless-ngx/issues/3631
        default_thumbnail_path: Path = Path(temp_dir) / "document.webp"
        copy_file_with_basic_stats(get_default_thumbnail(), default_thumbnail_path)
        return default_thumbnail_path
```

Copy `in_path` to a working copy (`repaired_path`) before running `qpdf --replace-input` on it — same reasoning as `consumer.py`'s existing use of the flag: it rewrites in place, and the original uploaded file must not be touched. Add `import shutil` at the top of `parsers.py` if not already present (check first).

- [ ] **Step 2: Confirm `make_thumbnail_from_pdf()`'s reference resolves**

The call added in Task 1 Step 4 (`make_thumbnail_from_pdf_qpdf_fallback(...)`) should now resolve, since this step defines that function.

- [ ] **Step 3: Update the existing fallback test**

`test_thumbnail_fallback_on_convert_error` (`test_tesseract_parser.py:283-300`) currently mocks `documents.parsers.run_convert` to fail on PDF input. Update it to mock the new primary rasterizer instead:

```python
def test_thumbnail_fallback_on_pdftoppm_error(
    self,
    mocker: MockerFixture,
    tesseract_parser: RasterisedDocumentParser,
    tesseract_samples_dir: Path,
) -> None:
    mocker.patch(
        "documents.parsers.rasterize_pdf_page_to_png",
        side_effect=ParseError("Does not compute."),
    )

    thumb = tesseract_parser.get_thumbnail(
        tesseract_samples_dir / "simple-digital.pdf",
        "application/pdf",
    )
    assert thumb.is_file()
```

Note this now exercises the qpdf-repair-and-retry path for a PDF that doesn't actually need repair (qpdf should succeed trivially, then the retried rasterization succeeds) — that's a valid coverage case but not the same as "PDF genuinely needs repair." Add a second, separate test in Task 3 for that.

- [ ] **Step 4: Ruff and the parser test file**

```bash
ruff check src/documents/parsers.py src/paperless/tests/parsers/test_tesseract_parser.py
ruff format src/documents/parsers.py src/paperless/tests/parsers/test_tesseract_parser.py
uv run pytest src/paperless/tests/parsers/test_tesseract_parser.py -v -k Thumbnail
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/documents/parsers.py src/paperless/tests/parsers/test_tesseract_parser.py
git commit -m "refactor: replace Ghostscript thumbnail fallback with qpdf repair-and-retry"
```

## Task 3: Add coverage for the qpdf-repair and double-fallback branches, update remaining tests

**Agent:** python-expert — **Model:** sonnet (adding targeted test cases following established fixtures/patterns in the same test files, not new production logic)

**Files:**

- Test: `src/paperless/tests/parsers/test_tesseract_parser.py`
- Test: `src/documents/tests/test_management_thumbnails.py`
- Test: any other test asserting on `documents.parsers.run_convert` for a PDF-thumbnail scenario specifically (search in Step 1)

**Interfaces:**

- Consumes: everything from Tasks 1-2.

- [ ] **Step 1: Find any remaining PDF-thumbnail tests tied to the old ImageMagick/Ghostscript call shape**

```bash
grep -rn "make_thumbnail_from_pdf_gs_fallback\|run_convert.*pdf\|GS_BINARY" src/documents/tests src/paperless/tests
```

Update or remove anything referencing the now-renamed `make_thumbnail_from_pdf_gs_fallback` (it no longer exists — renamed to `make_thumbnail_from_pdf_qpdf_fallback` in Task 2).

- [ ] **Step 2: Add a qpdf-repair-actually-needed test**

Add a test that produces (or reuses an existing samples-dir fixture for) a PDF `pdftoppm` cannot parse directly but `qpdf --replace-input` can repair, asserting the resulting thumbnail is a real rendered page (not the generic fallback image) — i.e. covers the retry succeeding after a genuine repair, not just qpdf's no-op success case from Task 2 Step 3. Check `src/paperless/tests/parsers/samples/` and `src/documents/tests/samples/documents/` for an existing malformed-but-repairable PDF sample before creating a new one.

- [ ] **Step 3: Add a double-fallback test**

Add a test where both `rasterize_pdf_page_to_png` and the qpdf repair fail (e.g. mock `qpdf`'s subprocess call to raise), asserting the result falls back to `get_default_thumbnail()` — mirrors the existing `test_process_document_password_protected` case in `test_management_thumbnails.py:64-70`, which already exercises this end-to-end for a password-protected PDF (confirm that test still passes unmodified as a real-world instance of this branch; add the more targeted/mocked unit test alongside it, not instead of it).

- [ ] **Step 4: Full parser + thumbnail test run**

```bash
uv run pytest src/paperless/tests/parsers src/documents/tests/test_management_thumbnails.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/paperless/tests/parsers/test_tesseract_parser.py src/documents/tests/test_management_thumbnails.py
git commit -m "test: cover qpdf-repair and double-fallback thumbnail branches"
```

## Task 4: Repo-wide verification sweep

**Agent:** general-purpose — **Model:** sonnet (audit/verification pass: run checks, read output, fix anything found — not novel design work)

**Files:**

- Modify: any file a grep in this task turns up beyond those already handled in Tasks 1-3 (expected: none)
- Test: full backend suite

**Interfaces:**

- Consumes: the finished pipeline from Tasks 1-3.

- [ ] **Step 1: Confirm no remaining reference to the old fallback name or ImageMagick-for-PDF path**

```bash
grep -rn "make_thumbnail_from_pdf_gs_fallback" src/
grep -n "run_convert" src/documents/parsers.py
```

Expected: first command → no output. Second → only the two remaining non-PDF call sites (`convert_from_tiff_to_pdf`, `remove_alpha`) plus `run_convert`'s own definition — no reference inside `make_thumbnail_from_pdf` or the qpdf fallback.

- [ ] **Step 2: Confirm `gs`/`GS_BINARY` still exists and is unmodified in scope**

```bash
grep -rn "GS_BINARY\|settings.GS_BINARY" src/
```

Expected: still present in `settings/__init__.py`, `checks.py`, and wherever `ocrmypdf`/OCR invocation configures it — confirm nothing in `parsers.py`'s thumbnail functions references it anymore.

- [ ] **Step 3: Full ruff pass**

```bash
ruff check src/documents/parsers.py src/paperless/parsers/utils.py src/paperless/tests/parsers/test_tesseract_parser.py src/documents/tests/test_management_thumbnails.py
ruff format --check src/documents/parsers.py src/paperless/parsers/utils.py src/paperless/tests/parsers/test_tesseract_parser.py src/documents/tests/test_management_thumbnails.py
```

Expected: clean.

- [ ] **Step 4: Full backend test suite**

```bash
uv run pytest -v
```

(No path filter — confirms nothing outside the directly-touched files was relying on the old thumbnail call shape, e.g. a management command or mail-parser test mocking at a different layer.)

Expected: PASS.

- [ ] **Step 5: If Steps 1-4 found nothing to fix, commit is a no-op — skip it. If they found strays, fix and commit**

```bash
git add -A
git commit -m "fix: stray references to old PDF thumbnail fallback found in repo sweep"
```
