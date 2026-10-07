"""
Tests for documents.pdf_ops.

These use real PDFs from the sample directories. No database, Celery or mocks.
Pages are compared by a hash of their content stream, so page identity and order
are easy to assert.
"""

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
    return hashlib.sha256(b"".join(s.read_bytes() for s in streams)).hexdigest()


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
    def test_rotation_is_relative_and_applies_to_every_page(
        self,
        tmp_path: Path,
    ) -> None:
        once = tmp_path / "once.pdf"
        twice = tmp_path / "twice.pdf"

        pdf_ops.rotate_pdf(THREE_PAGES, once, 90)
        pdf_ops.rotate_pdf(once, twice, 90)

        assert rotations(once) == [90, 90, 90]
        assert rotations(twice) == [180, 180, 180]
        assert fingerprints(twice) == fingerprints(THREE_PAGES)

    def test_keeps_document_info(self, tmp_path: Path) -> None:
        dst = tmp_path / "out.pdf"

        pdf_ops.rotate_pdf(THREE_PAGES, dst, 90)

        assert "/Creator" in docinfo_keys(dst)


class TestRemovePages:
    @pytest.mark.parametrize(
        ("pages", "kept"),
        [
            pytest.param([2], [0, 2], id="single"),
            pytest.param([3, 1], [1], id="unordered"),
            pytest.param([2, 2], [0, 2], id="duplicates-remove-once"),
            pytest.param([], [0, 1, 2], id="empty-keeps-everything"),
            pytest.param([1, 2, 3], [], id="every-page"),
        ],
    )
    def test_removes_only_the_requested_pages(
        self,
        tmp_path: Path,
        source_fingerprints: list[str],
        pages: list[int],
        kept: list[int],
    ) -> None:
        """
        GIVEN:
            - A three page PDF
        WHEN:
            - Pages are removed, in any order and possibly repeated
        THEN:
            - Exactly the other pages remain, in their original order
        """
        dst = tmp_path / "out.pdf"

        pdf_ops.remove_pages(THREE_PAGES, dst, pages)

        assert fingerprints(dst) == [source_fingerprints[i] for i in kept]

    def test_keeps_document_info(self, tmp_path: Path) -> None:
        dst = tmp_path / "out.pdf"

        pdf_ops.remove_pages(THREE_PAGES, dst, [1])

        assert "/Creator" in docinfo_keys(dst)

    @pytest.mark.parametrize("bad_page", [0, -1])
    def test_rejects_pages_below_one(self, tmp_path: Path, bad_page: int) -> None:
        dst = tmp_path / "out.pdf"

        with pytest.raises(ValueError, match="start at 1"):
            pdf_ops.remove_pages(THREE_PAGES, dst, [1, bad_page])

        assert not dst.exists()


class TestBuildPdfs:
    def test_selects_and_orders_pages(
        self,
        tmp_path: Path,
        source_fingerprints: list[str],
    ) -> None:
        dst = tmp_path / "out.pdf"

        written = pdf_ops.build_pdfs(
            THREE_PAGES,
            [([PageSpec(3), PageSpec(1)], constant(dst))],
        )

        assert written == [dst]
        assert fingerprints(dst) == [source_fingerprints[2], source_fingerprints[0]]

    def test_rotates_only_the_requested_pages(self, tmp_path: Path) -> None:
        dst = tmp_path / "out.pdf"

        pdf_ops.build_pdfs(
            THREE_PAGES,
            [([PageSpec(1), PageSpec(2, 90), PageSpec(3, 180)], constant(dst))],
        )

        assert rotations(dst) == [0, 90, 180]

    def test_writes_one_file_per_output_in_order(self, tmp_path: Path) -> None:
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

    def test_empty_page_list_writes_a_zero_page_file(self, tmp_path: Path) -> None:
        dst = tmp_path / "out.pdf"

        pdf_ops.build_pdfs(THREE_PAGES, [([], constant(dst))])

        assert fingerprints(dst) == []

    def test_destination_is_not_requested_when_a_page_is_out_of_range(
        self,
        tmp_path: Path,
    ) -> None:
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
    ) -> None:
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
    def test_returns_the_output_count(self) -> None:
        operations = [{"page": 1}, {"page": 2}, {"page": 3}]

        assert pdf_ops.validate_page_operations(operations, single_output=True) == 1

    def test_gap_in_output_indices_counts_up_to_the_highest(self) -> None:
        operations = [
            {"page": 1, "doc": 0},
            {"page": 2, "doc": 2},
            {"page": 3, "doc": 0},
        ]

        count = pdf_ops.validate_page_operations(operations, single_output=False)

        assert count == 3

    def test_empty_operations_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="index is out of bounds"):
            pdf_ops.validate_page_operations([], single_output=False)

    def test_multiple_outputs_rejected_when_single_output_required(self) -> None:
        operations = [{"page": 1, "doc": 0}, {"page": 2, "doc": 1}]

        with pytest.raises(ValueError, match="Multiple output documents"):
            pdf_ops.validate_page_operations(operations, single_output=True)

    @pytest.mark.parametrize("doc", [-1, 2, 2**32])
    def test_output_index_out_of_bounds(self, doc: int) -> None:
        operations = [{"page": 1, "doc": 0}, {"page": 2, "doc": doc}]

        with pytest.raises(ValueError, match="index is out of bounds"):
            pdf_ops.validate_page_operations(operations, single_output=False)


class TestDecrypt:
    @pytest.mark.parametrize(
        ("path", "expected"),
        [
            pytest.param(ENCRYPTED, True, id="password-required"),
            pytest.param(SIGNED, True, id="opens-without-password-but-encrypted"),
            pytest.param(THREE_PAGES, False, id="not-encrypted"),
        ],
    )
    def test_needs_decrypt(self, path: Path, *, expected: bool) -> None:
        """
        GIVEN:
            - A PDF that is encrypted, or encrypted but openable, or plain
        WHEN:
            - needs_decrypt is asked about it
        THEN:
            - Only the unencrypted PDF reports False
        """
        assert pdf_ops.needs_decrypt(path) is expected

    def test_decrypt_writes_an_unencrypted_copy(self, tmp_path: Path) -> None:
        dst = tmp_path / "out.pdf"

        result = pdf_ops.decrypt_pdf(ENCRYPTED, constant(dst), "test")

        assert result == dst
        assert pdf_ops.needs_decrypt(dst) is False

    def test_wrong_password_raises_and_never_requests_a_destination(
        self,
        tmp_path: Path,
    ) -> None:
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
    ) -> None:
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
    ) -> None:
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
