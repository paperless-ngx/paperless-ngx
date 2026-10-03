"""
Tests for documents.pdf_ops.

These use real PDFs from the sample directories. No database, Celery or mocks.
Pages are compared by a hash of their content stream, so page identity and order
are easy to assert.
"""

import ast
import hashlib
from collections.abc import Callable
from pathlib import Path

import pikepdf
import pytest

from documents import pdf_ops
from documents.pdf_ops import PageSpec

SRC_ROOT = Path(__file__).parents[2]
SAMPLES = Path(__file__).parent / "samples"
THREE_PAGES = SAMPLES / "documents" / "originals" / "0000002.pdf"
TWELVE_PAGES = SAMPLES / "barcodes" / "split-by-asn-2.pdf"
ENCRYPTED = SAMPLES / "password-is-test.pdf"
SIGNED = SRC_ROOT / "paperless" / "tests" / "samples" / "tesseract" / "signed.pdf"


def _page_fingerprint(page: pikepdf.Page) -> str:
    contents = page.obj.get("/Contents")
    assert contents is not None, "sample page has no /Contents"
    streams = list(contents) if isinstance(contents, pikepdf.Array) else [contents]
    return hashlib.sha1(b"".join(s.read_bytes() for s in streams)).hexdigest()


def fingerprints(path: Path) -> list[str]:
    with pikepdf.open(path) as pdf:
        return [_page_fingerprint(page) for page in pdf.pages]


def rotations(path: Path) -> list[int]:
    with pikepdf.open(path) as pdf:
        return [int(page.obj.get("/Rotate", 0)) for page in pdf.pages]


def docinfo_keys(path: Path) -> set[str]:
    with pikepdf.open(path) as pdf:
        return set(pdf.docinfo.keys())


def constant(path: Path) -> Callable[[], Path]:
    return lambda: path


@pytest.fixture
def source_fingerprints() -> list[str]:
    fps = fingerprints(THREE_PAGES)
    assert len(set(fps)) == 3, "sample must have three distinct pages"
    return fps


class TestRotatePdf:
    def test_rotation_is_relative_and_applies_to_every_page(self, tmp_path: Path):
        once = tmp_path / "once.pdf"
        twice = tmp_path / "twice.pdf"

        pdf_ops.rotate_pdf(THREE_PAGES, once, 90)
        pdf_ops.rotate_pdf(once, twice, 90)

        assert rotations(once) == [90, 90, 90]
        assert rotations(twice) == [180, 180, 180]
        assert fingerprints(twice) == fingerprints(THREE_PAGES)

    def test_keeps_document_info(self, tmp_path: Path):
        dst = tmp_path / "out.pdf"

        pdf_ops.rotate_pdf(THREE_PAGES, dst, 90)

        assert "/Creator" in docinfo_keys(dst)


class TestRemovePages:
    def test_removes_selected_pages(
        self,
        tmp_path: Path,
        source_fingerprints: list[str],
    ):
        dst = tmp_path / "out.pdf"

        pdf_ops.remove_pages(THREE_PAGES, dst, [2])

        assert fingerprints(dst) == [source_fingerprints[0], source_fingerprints[2]]

    def test_duplicate_page_numbers_remove_the_page_once(
        self,
        tmp_path: Path,
        source_fingerprints: list[str],
    ):
        dst = tmp_path / "out.pdf"

        pdf_ops.remove_pages(THREE_PAGES, dst, [2, 2])

        assert fingerprints(dst) == [source_fingerprints[0], source_fingerprints[2]]

    def test_unordered_pages(self, tmp_path: Path, source_fingerprints: list[str]):
        dst = tmp_path / "out.pdf"

        pdf_ops.remove_pages(THREE_PAGES, dst, [3, 1])

        assert fingerprints(dst) == [source_fingerprints[1]]

    def test_empty_list_keeps_every_page(
        self,
        tmp_path: Path,
        source_fingerprints: list[str],
    ):
        dst = tmp_path / "out.pdf"

        pdf_ops.remove_pages(THREE_PAGES, dst, [])

        assert fingerprints(dst) == source_fingerprints

    def test_removing_every_page_writes_an_empty_pdf(self, tmp_path: Path):
        dst = tmp_path / "out.pdf"

        pdf_ops.remove_pages(THREE_PAGES, dst, [1, 2, 3])

        assert fingerprints(dst) == []

    def test_keeps_document_info(self, tmp_path: Path):
        dst = tmp_path / "out.pdf"

        pdf_ops.remove_pages(THREE_PAGES, dst, [1])

        assert "/Creator" in docinfo_keys(dst)

    @pytest.mark.parametrize("bad_page", [0, -1])
    def test_rejects_pages_below_one(self, tmp_path: Path, bad_page: int):
        dst = tmp_path / "out.pdf"

        with pytest.raises(ValueError, match="start at 1"):
            pdf_ops.remove_pages(THREE_PAGES, dst, [1, bad_page])

        assert not dst.exists()

    def test_page_past_the_end_raises_and_writes_nothing(self, tmp_path: Path):
        dst = tmp_path / "out.pdf"

        with pytest.raises(IndexError):
            pdf_ops.remove_pages(THREE_PAGES, dst, [99])

        assert not dst.exists()


class TestBuildPdfs:
    def test_selects_and_orders_pages(
        self,
        tmp_path: Path,
        source_fingerprints: list[str],
    ):
        dst = tmp_path / "out.pdf"

        written = pdf_ops.build_pdfs(
            THREE_PAGES,
            [([PageSpec(3), PageSpec(1)], constant(dst))],
        )

        assert written == [dst]
        assert fingerprints(dst) == [source_fingerprints[2], source_fingerprints[0]]

    def test_rotates_only_the_requested_pages(self, tmp_path: Path):
        dst = tmp_path / "out.pdf"

        pdf_ops.build_pdfs(
            THREE_PAGES,
            [([PageSpec(1), PageSpec(2, 90), PageSpec(3, 180)], constant(dst))],
        )

        assert rotations(dst) == [0, 90, 180]

    def test_writes_one_file_per_output_in_order(self, tmp_path: Path):
        first = tmp_path / "first.pdf"
        second = tmp_path / "second.pdf"
        source = fingerprints(TWELVE_PAGES)

        written = pdf_ops.build_pdfs(
            TWELVE_PAGES,
            [
                ([PageSpec(p) for p in (1, 2, 3)], constant(first)),
                ([PageSpec(p) for p in range(4, 13)], constant(second)),
            ],
        )

        assert written == [first, second]
        assert fingerprints(first) == source[:3]
        assert fingerprints(second) == source[3:]

    def test_empty_page_list_writes_a_zero_page_file(self, tmp_path: Path):
        dst = tmp_path / "out.pdf"

        pdf_ops.build_pdfs(THREE_PAGES, [([], constant(dst))])

        assert fingerprints(dst) == []

    def test_does_not_carry_over_document_info(self, tmp_path: Path):
        dst = tmp_path / "out.pdf"
        assert "/Creator" in docinfo_keys(THREE_PAGES)

        pdf_ops.build_pdfs(THREE_PAGES, [([PageSpec(1)], constant(dst))])

        assert "/Creator" not in docinfo_keys(dst)

    def test_destination_is_not_requested_when_a_page_is_out_of_range(
        self,
        tmp_path: Path,
    ):
        requested: list[Path] = []

        def make_dst() -> Path:
            requested.append(tmp_path / "out.pdf")
            return requested[-1]

        with pytest.raises(IndexError):
            pdf_ops.build_pdfs(THREE_PAGES, [([PageSpec(99)], make_dst)])

        assert requested == []

    @pytest.mark.parametrize("bad_page", [0, -1])
    def test_rejects_pages_below_one_before_opening_anything(
        self,
        tmp_path: Path,
        bad_page: int,
    ):
        requested: list[Path] = []

        def make_dst() -> Path:
            requested.append(tmp_path / "out.pdf")
            return requested[-1]

        with pytest.raises(ValueError, match="start at 1"):
            pdf_ops.build_pdfs(
                THREE_PAGES,
                [([PageSpec(1)], make_dst), ([PageSpec(bad_page)], make_dst)],
            )

        assert requested == []


class TestValidatePageOperations:
    def test_returns_the_output_count(self):
        operations = [{"page": 1}, {"page": 2}, {"page": 3}]

        assert pdf_ops.validate_page_operations(operations, single_output=True) == 1

    def test_gap_in_output_indices_counts_up_to_the_highest(self):
        operations = [
            {"page": 1, "doc": 0},
            {"page": 2, "doc": 2},
            {"page": 3, "doc": 0},
        ]

        count = pdf_ops.validate_page_operations(operations, single_output=False)

        assert count == 3

    def test_empty_operations_are_rejected(self):
        with pytest.raises(ValueError, match="index is out of bounds"):
            pdf_ops.validate_page_operations([], single_output=False)

    def test_multiple_outputs_rejected_when_single_output_required(self):
        operations = [{"page": 1, "doc": 0}, {"page": 2, "doc": 1}]

        with pytest.raises(ValueError, match="Multiple output documents"):
            pdf_ops.validate_page_operations(operations, single_output=True)

    @pytest.mark.parametrize("doc", [-1, 2, 2**32])
    def test_output_index_out_of_bounds(self, doc: int):
        operations = [{"page": 1, "doc": 0}, {"page": 2, "doc": doc}]

        with pytest.raises(ValueError, match="index is out of bounds"):
            pdf_ops.validate_page_operations(operations, single_output=False)


class TestDecrypt:
    def test_needs_decrypt(self):
        assert pdf_ops.needs_decrypt(ENCRYPTED) is True
        assert pdf_ops.needs_decrypt(THREE_PAGES) is False

    def test_pdf_that_opens_without_a_password_but_is_flagged_encrypted(self):
        assert pdf_ops.needs_decrypt(SIGNED) is True

    def test_decrypt_writes_an_unencrypted_copy(self, tmp_path: Path):
        dst = tmp_path / "out.pdf"

        result = pdf_ops.decrypt_pdf(ENCRYPTED, constant(dst), "test")

        assert result == dst
        assert pdf_ops.needs_decrypt(dst) is False

    def test_wrong_password_raises_and_never_requests_a_destination(
        self,
        tmp_path: Path,
    ):
        requested: list[Path] = []

        def make_dst() -> Path:
            requested.append(tmp_path / "out.pdf")
            return requested[-1]

        with pytest.raises(pikepdf.PasswordError):
            pdf_ops.decrypt_pdf(ENCRYPTED, make_dst, "wrong")

        assert requested == []


class TestPdfMerger:
    def test_pages_are_appended_in_the_order_added(
        self,
        tmp_path: Path,
        source_fingerprints: list[str],
    ):
        reordered = tmp_path / "reordered.pdf"
        merged = tmp_path / "merged.pdf"
        pdf_ops.build_pdfs(
            THREE_PAGES,
            [([PageSpec(3), PageSpec(1)], constant(reordered))],
        )

        with pdf_ops.PdfMerger() as merger:
            merger.add(reordered)
            merger.add(THREE_PAGES)
            merger.save(merged)

        assert fingerprints(merged) == [
            source_fingerprints[2],
            source_fingerprints[0],
            *source_fingerprints,
        ]

    def test_output_version_is_at_least_the_highest_source_version(
        self,
        tmp_path: Path,
    ):
        merged = tmp_path / "merged.pdf"
        with pikepdf.open(TWELVE_PAGES) as pdf:
            source_versions = [pdf.pdf_version]
        with pikepdf.open(THREE_PAGES) as pdf:
            source_versions.append(pdf.pdf_version)

        with pdf_ops.PdfMerger() as merger:
            merger.add(TWELVE_PAGES)
            merger.add(THREE_PAGES)
            merger.save(merged)

        with pikepdf.open(merged) as pdf:
            assert pdf.pdf_version >= max(source_versions)

    def test_unreadable_source_raises_so_the_caller_can_skip_it(
        self,
        tmp_path: Path,
    ):
        garbage = tmp_path / "garbage.pdf"
        garbage.write_bytes(b"not a pdf")

        with pdf_ops.PdfMerger() as merger:
            with pytest.raises(pikepdf.PdfError):
                merger.add(garbage)


def test_pdf_ops_imports_only_the_standard_library_and_pikepdf():
    tree = ast.parse(Path(pdf_ops.__file__).read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])

    coupled = imported & {
        "django",
        "celery",
        "documents",
        "paperless",
        "paperless_mail",
        "paperless_ai",
    }
    assert not coupled
