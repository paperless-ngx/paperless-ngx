import subprocess
from collections.abc import Generator
from pathlib import Path

import pikepdf
import pytest
from PIL import Image
from pytest_django.fixtures import Settings
from pytest_mock import MockerFixture

from documents.parsers import ParseError
from documents.parsers import _compute_thumbnail_dpi
from documents.parsers import encode_thumbnail_webp
from documents.parsers import get_default_file_extension
from documents.parsers import get_default_thumbnail
from documents.parsers import get_supported_file_extensions
from documents.parsers import is_file_ext_supported
from documents.parsers import make_thumbnail_from_pdf
from documents.parsers import rasterize_pdf_page_to_png
from paperless.parsers.registry import get_parser_registry
from paperless.parsers.registry import reset_parser_registry
from paperless.parsers.tesseract import RasterisedDocumentParser
from paperless.parsers.text import TextDocumentParser
from paperless.parsers.tika import TikaDocumentParser


@pytest.fixture()
def _tika_registry(settings: Settings) -> Generator[None, None, None]:
    """
    Rebuild the parser registry with Tika enabled for the duration of the
    test, then reset on exit so other tests see the default (Tika-disabled)
    registry.
    """
    settings.TIKA_ENABLED = True
    reset_parser_registry()
    yield
    reset_parser_registry()


@pytest.mark.django_db
class TestParserAvailability:
    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param("application/pdf", ".pdf", id="pdf"),
            pytest.param("image/png", ".png", id="png"),
            pytest.param("image/jpeg", ".jpg", id="jpeg"),
            pytest.param("image/tiff", ".tif", id="tiff"),
            pytest.param("image/webp", ".webp", id="webp"),
        ],
    )
    def test_tesseract_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types
        WHEN:
            - The parser class is instantiated
        THEN:
            - The Tesseract based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            RasterisedDocumentParser,
        )

    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param("text/plain", ".txt", id="plain"),
            pytest.param("text/csv", ".csv", id="csv"),
        ],
    )
    def test_text_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types of a text form
        WHEN:
            - The parser class is instantiated
        THEN:
            - The text based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            TextDocumentParser,
        )

    @pytest.mark.usefixtures("_tika_registry")
    @pytest.mark.parametrize(
        ("mime_type", "ext"),
        [
            pytest.param(
                "application/vnd.oasis.opendocument.text",
                ".odt",
                id="odt",
            ),
            pytest.param("text/rtf", ".rtf", id="rtf"),
            pytest.param("application/msword", ".doc", id="doc"),
            pytest.param(
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".docx",
                id="docx",
            ),
        ],
    )
    def test_tika_parser(self, mime_type: str, ext: str) -> None:
        """
        GIVEN:
            - Various mime types of an office document form
        WHEN:
            - The parser class is instantiated
        THEN:
            - The Tika/Gotenberg based parser is returned
        """
        assert ext in get_supported_file_extensions()
        assert get_default_file_extension(mime_type) == ext
        assert isinstance(
            get_parser_registry().get_parser_for_file(mime_type, "")(),
            TikaDocumentParser,
        )

    def test_no_parser_for_mime(self) -> None:
        assert get_parser_registry().get_parser_for_file("text/sdgsdf", "") is None

    def test_default_extension(self) -> None:
        # Test no parser declared still returns an extension
        assert get_default_file_extension("application/zip") == ".zip"

        # Test invalid mimetype returns no extension
        assert get_default_file_extension("aasdasd/dgfgf") == ""

    def test_file_extension_support(self) -> None:
        assert is_file_ext_supported(".pdf")
        assert not is_file_ext_supported(".hsdfh")
        assert not is_file_ext_supported("")


class TestComputeThumbnailDpi:
    @pytest.mark.parametrize(
        ("size", "expected"),
        [
            pytest.param((612.0, 792.0), (59, 2), id="letter-width-bound"),
            pytest.param((792.0, 612.0), (46, 2), id="landscape-rounded-up"),
            pytest.param((612.0, 100000.0), (4, 2), id="tall-strip-height-bound"),
            pytest.param((200.0, 300.0), (180, 2), id="small-page-width-bound"),
            pytest.param((72.0, 72.0), (300, 2), id="tiny-page-capped-at-300"),
            pytest.param(
                (1000000.0, 1000000.0),
                (1, 1),
                id="huge-page-minimum-one-unsupersampled",
            ),
            pytest.param(None, (150, 1), id="unreadable-geometry-fallback"),
        ],
    )
    def test_dpi_from_page_size(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        size: tuple[float, float] | None,
        expected: tuple[int, int],
    ) -> None:
        """
        GIVEN:
            - A PDF whose first page has the given size in points (or whose
              geometry cannot be read)
        WHEN:
            - The thumbnail DPI is computed
        THEN:
            - The DPI is rounded up so the render reaches 500x5000, is capped
              at 300 and floored at 1, and is supersampled 2x except at the
              1 DPI floor
            - An unknown size gives the plain 150 DPI fallback without
              supersampling
        """
        mocker.patch(
            "paperless.parsers.utils.get_pdf_first_page_size_points",
            return_value=size,
        )
        assert _compute_thumbnail_dpi(tmp_path / "doc.pdf") == expected


class TestMakeThumbnailFromPdf:
    @pytest.fixture
    def work_dir(self, tmp_path: Path) -> Path:
        path = tmp_path / "work"
        path.mkdir()
        return path

    @staticmethod
    def _write_blank_pdf(path: Path, page_size: tuple[int, int] = (612, 792)) -> Path:
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=page_size)
        pdf.save(path, object_stream_mode=pikepdf.ObjectStreamMode.disable)
        return path

    @pytest.mark.parametrize(
        ("size", "expected_dpi", "expected_supersample"),
        [
            pytest.param((612.0, 792.0), 118, 2, id="known-geometry-2x"),
            pytest.param(None, 150, 1, id="unreadable-geometry-plain-fallback"),
        ],
    )
    def test_render_dpi_requested(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        work_dir: Path,
        size: tuple[float, float] | None,
        expected_dpi: int,
        expected_supersample: int,
    ) -> None:
        """
        GIVEN:
            - A PDF whose page geometry is either readable or not
        WHEN:
            - A thumbnail is made from it
        THEN:
            - The page is rasterized at twice the computed DPI when the
              geometry is known, and at the plain 150 DPI fallback otherwise
            - The encode step is told the matching downsample factor
        """
        mocker.patch(
            "paperless.parsers.utils.get_pdf_first_page_size_points",
            return_value=size,
        )
        rasterize = mocker.patch("documents.parsers.rasterize_pdf_page_to_png")
        encode = mocker.patch("documents.parsers.encode_thumbnail_webp")

        make_thumbnail_from_pdf(tmp_path / "in.pdf", work_dir)

        assert rasterize.call_args.kwargs["dpi"] == expected_dpi
        assert encode.call_args.kwargs["supersample"] == expected_supersample

    @pytest.mark.parametrize(
        ("page_size", "expected_width"),
        [
            pytest.param((612, 792), 500, id="letter"),
            pytest.param((792, 612), 500, id="landscape-letter"),
            pytest.param((595, 842), 500, id="a4"),
            pytest.param((200, 300), 500, id="small-page"),
            pytest.param((72, 72), 300, id="tiny-page-capped"),
        ],
    )
    def test_thumbnail_width(
        self,
        tmp_path: Path,
        work_dir: Path,
        page_size: tuple[int, int],
        expected_width: int,
    ) -> None:
        """
        GIVEN:
            - A PDF whose first page has the given size in points
        WHEN:
            - A thumbnail is made from it
        THEN:
            - The WebP thumbnail is exactly 500px wide, unless the page is
              too small to reach that even at 300 DPI
        """
        pdf_path = self._write_blank_pdf(tmp_path / "in.pdf", page_size)

        thumb = make_thumbnail_from_pdf(pdf_path, work_dir)

        assert thumb == work_dir / "convert.webp"
        with Image.open(thumb) as im:
            assert im.format == "WEBP"
            assert im.width == expected_width

    @classmethod
    def _write_pdf_without_xref(cls, path: Path) -> Path:
        """
        Writes a valid one page PDF, then cuts off its cross reference table
        and trailer, which poppler cannot recover from but qpdf can.
        """
        cls._write_blank_pdf(path)
        data = path.read_bytes()
        path.write_bytes(data[: data.rindex(b"\nxref")])
        return path

    def test_qpdf_repair_produces_real_thumbnail(
        self,
        tmp_path: Path,
        work_dir: Path,
    ) -> None:
        """
        GIVEN:
            - A PDF without a cross reference table or trailer, which
              pdftoppm cannot render but qpdf can repair
        WHEN:
            - A thumbnail is made from it
        THEN:
            - The unrepaired file really cannot be rasterized
            - The thumbnail comes from the repaired copy and is a rendered
              500px wide page, not the default placeholder
            - The original file is left untouched
        """
        pdf_path = self._write_pdf_without_xref(tmp_path / "broken.pdf")
        original_bytes = pdf_path.read_bytes()

        with pytest.raises(ParseError):
            rasterize_pdf_page_to_png(pdf_path, work_dir / "probe.png", dpi=50)

        thumb = make_thumbnail_from_pdf(pdf_path, work_dir)

        assert thumb == work_dir / "convert_qpdf.webp"
        with Image.open(thumb) as im:
            assert im.format == "WEBP"
            assert im.width == 500
        assert pdf_path.read_bytes() == original_bytes

    @pytest.mark.parametrize(
        "qpdf_error",
        [
            pytest.param(subprocess.CalledProcessError(2, "qpdf"), id="qpdf-fails"),
            pytest.param(None, id="repaired-still-unrenderable"),
        ],
    )
    def test_double_failure_uses_default_thumbnail(
        self,
        mocker: MockerFixture,
        tmp_path: Path,
        work_dir: Path,
        qpdf_error: subprocess.CalledProcessError | None,
    ) -> None:
        """
        GIVEN:
            - A PDF which cannot be rasterized, either because qpdf cannot
              repair it or because the repaired copy still cannot be rendered
        WHEN:
            - A thumbnail is made from it
        THEN:
            - The result is a copy of the default thumbnail, so the caller
              can move it without consuming the shared resource
        """
        mocker.patch(
            "documents.parsers.rasterize_pdf_page_to_png",
            side_effect=ParseError("Does not compute."),
        )
        if qpdf_error is not None:
            mocker.patch("documents.parsers.run_subprocess", side_effect=qpdf_error)
        pdf_path = self._write_blank_pdf(tmp_path / "in.pdf")

        thumb = make_thumbnail_from_pdf(pdf_path, work_dir)

        assert thumb == work_dir / "document.webp"
        assert thumb.read_bytes() == get_default_thumbnail().read_bytes()


class TestRasterizePdfPageToPng:
    @staticmethod
    def _write_pdf(
        path: Path,
        *,
        crop_box: tuple[float, float, float, float] | None = None,
        rotate: int | None = None,
    ) -> Path:
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(144, 72))
        pdf.add_blank_page(page_size=(300, 300))
        page = pdf.pages[0]
        if crop_box is not None:
            page.obj.CropBox = pikepdf.Array(crop_box)
        if rotate is not None:
            page.obj.Rotate = rotate
        pdf.save(path)
        return path

    @pytest.mark.parametrize(
        ("crop_box", "rotate", "expected_size"),
        [
            pytest.param(None, None, (144, 72), id="plain"),
            pytest.param(None, 90, (72, 144), id="rotated-90"),
            pytest.param((0, 0, 72, 36), None, (72, 36), id="crop-box"),
        ],
    )
    def test_renders_first_page_to_exact_path(
        self,
        tmp_path: Path,
        crop_box: tuple[float, float, float, float] | None,
        rotate: int | None,
        expected_size: tuple[int, int],
    ) -> None:
        """
        GIVEN:
            - A two page PDF whose first page is 144x72 points, optionally
              cropped or rotated
        WHEN:
            - The first page is rasterized at 72 DPI
        THEN:
            - Exactly the requested output path is written, and the image
              matches the first page's cropped, rotated size
        """
        pdf_path = self._write_pdf(
            tmp_path / "in.pdf",
            crop_box=crop_box,
            rotate=rotate,
        )
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        out_path = out_dir / "page1.png"

        rasterize_pdf_page_to_png(pdf_path, out_path, dpi=72)

        assert list(out_dir.iterdir()) == [out_path]
        with Image.open(out_path) as im:
            assert im.format == "PNG"
            assert im.size == expected_size

    def test_failure_raises_parse_error(self, tmp_path: Path) -> None:
        """
        GIVEN:
            - A file that is not a PDF
        WHEN:
            - Rasterization is attempted
        THEN:
            - A ParseError is raised
        """
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"not a pdf")

        with pytest.raises(ParseError):
            rasterize_pdf_page_to_png(bad, tmp_path / "page1.png", dpi=72)


class TestEncodeThumbnailWebp:
    @pytest.mark.parametrize(
        ("mode", "color"),
        [
            pytest.param("RGBA", (0, 0, 0, 0), id="rgba"),
            pytest.param("LA", (0, 0), id="la"),
        ],
    )
    def test_alpha_flattened_onto_white(
        self,
        tmp_path: Path,
        mode: str,
        color: tuple[int, ...],
    ) -> None:
        """
        GIVEN:
            - A fully transparent PNG with an alpha channel
        WHEN:
            - It is encoded as a thumbnail
        THEN:
            - The WebP output is RGB with the transparency flattened to white
        """
        png_path = tmp_path / "in.png"
        Image.new(mode, (20, 10), color).save(png_path)
        out_path = tmp_path / "out.webp"

        encode_thumbnail_webp(png_path, out_path)

        with Image.open(out_path) as im:
            assert im.format == "WEBP"
            assert im.mode == "RGB"
            assert im.size == (20, 10)
            red, green, blue = im.getpixel((10, 5))
            assert min(red, green, blue) >= 250

    @pytest.mark.parametrize(
        ("in_size", "supersample", "expected_size"),
        [
            pytest.param((1000, 2000), 1, (500, 1000), id="too-wide-shrunk"),
            pytest.param((100, 10000), 1, (50, 5000), id="too-tall-shrunk"),
            pytest.param((100, 200), 1, (100, 200), id="small-not-enlarged"),
            pytest.param((1000, 1400), 2, (500, 700), id="2x-halved"),
            pytest.param((1001, 1401), 2, (500, 700), id="2x-odd-rounded"),
            pytest.param((600, 800), 2, (300, 400), id="2x-small-not-enlarged"),
            pytest.param((900, 1200), 2, (450, 600), id="2x-below-clamp"),
        ],
    )
    def test_size_clamped_and_downsampled(
        self,
        tmp_path: Path,
        in_size: tuple[int, int],
        supersample: int,
        expected_size: tuple[int, int],
    ) -> None:
        """
        GIVEN:
            - A rendered page image of the given size, made at the given
              supersampling factor
        WHEN:
            - It is encoded as a thumbnail with that factor
        THEN:
            - It is downsampled by the factor, then shrunk to fit 500x5000
              keeping aspect ratio, and never enlarged
        """
        png_path = tmp_path / "in.png"
        Image.new("RGB", in_size, (255, 255, 255)).save(png_path)
        out_path = tmp_path / "out.webp"

        encode_thumbnail_webp(png_path, out_path, supersample=supersample)

        with Image.open(out_path) as im:
            assert im.size == expected_size

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(OSError("broken image"), id="os-error"),
            pytest.param(Image.DecompressionBombError("too large"), id="bomb"),
        ],
    )
    def test_decode_failure_raises_parse_error(
        self,
        tmp_path: Path,
        mocker: MockerFixture,
        error: Exception,
    ) -> None:
        """
        GIVEN:
            - Opening the rendered image fails with an OSError or a
              DecompressionBombError
        WHEN:
            - It is encoded as a thumbnail
        THEN:
            - A ParseError is raised so the default thumbnail is used
        """
        png_path = tmp_path / "in.png"
        Image.new("RGB", (10, 10)).save(png_path)
        mocker.patch("PIL.Image.open", side_effect=error)

        with pytest.raises(ParseError):
            encode_thumbnail_webp(png_path, tmp_path / "out.webp")
