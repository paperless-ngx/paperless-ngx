"""Tests for the document_sanity_checker management command.

Verifies Rich rendering (table, panel, summary) and end-to-end CLI behavior.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command
from rich.console import Console

from documents.management.commands.document_sanity_checker import Command
from documents.sanity_checker import SanityCheckMessages
from documents.tests.factories import DocumentFactory

if TYPE_CHECKING:
    from documents.models import Document
    from documents.tests.conftest import PaperlessDirs


def _render_to_string(messages: SanityCheckMessages) -> str:
    """Render command output to a plain string for assertion."""
    buf = StringIO()
    cmd = Command()
    cmd.console = Console(file=buf, width=120, no_color=True)
    cmd._render_results(messages)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Rich rendering
# ---------------------------------------------------------------------------


class TestRenderResultsNoIssues:
    """No DB access needed -- renders an empty SanityCheckMessages."""

    def test_shows_panel(self) -> None:
        output = _render_to_string(SanityCheckMessages())
        assert "No issues detected" in output
        assert "Sanity Check" in output


@pytest.mark.django_db
class TestRenderResultsWithIssues:
    def test_error_row(self, sample_doc: Document) -> None:
        msgs = SanityCheckMessages()
        msgs.error(sample_doc.pk, "Original missing")
        output = _render_to_string(msgs)
        assert "Sanity Check Results" in output
        assert "ERROR" in output
        assert "Original missing" in output
        assert f"#{sample_doc.pk}" in output
        assert sample_doc.title in output

    def test_warning_row(self, sample_doc: Document) -> None:
        msgs = SanityCheckMessages()
        msgs.warning(sample_doc.pk, "Suspicious file")
        output = _render_to_string(msgs)
        assert "WARN" in output
        assert "Suspicious file" in output

    def test_info_row(self, sample_doc: Document) -> None:
        msgs = SanityCheckMessages()
        msgs.info(sample_doc.pk, "No OCR data")
        output = _render_to_string(msgs)
        assert "INFO" in output
        assert "No OCR data" in output

    @pytest.mark.usefixtures("_media_settings")
    def test_global_message(self) -> None:
        msgs = SanityCheckMessages()
        msgs.warning(None, "Orphaned file: /tmp/stray.pdf")
        output = _render_to_string(msgs)
        assert "(global)" in output
        assert "Orphaned file" in output

    def test_multiple_messages_same_doc(self, sample_doc: Document) -> None:
        msgs = SanityCheckMessages()
        msgs.error(sample_doc.pk, "Thumbnail missing")
        msgs.error(sample_doc.pk, "Checksum mismatch")
        output = _render_to_string(msgs)
        assert "Thumbnail missing" in output
        assert "Checksum mismatch" in output

    @pytest.mark.usefixtures("_media_settings")
    def test_unknown_doc_pk(self) -> None:
        msgs = SanityCheckMessages()
        msgs.error(99999, "Ghost document")
        output = _render_to_string(msgs)
        assert "#99999" in output
        assert "Unknown" in output


@pytest.mark.django_db
class TestRenderResultsSummary:
    def test_errors_only(self, sample_doc: Document) -> None:
        msgs = SanityCheckMessages()
        msgs.error(sample_doc.pk, "broken")
        output = _render_to_string(msgs)
        assert "errors" in output
        assert "Found 1 document(s)" in output

    def test_warnings_only(self, sample_doc: Document) -> None:
        msgs = SanityCheckMessages()
        msgs.warning(sample_doc.pk, "odd")
        output = _render_to_string(msgs)
        assert "warnings" in output

    def test_errors_and_warnings(self, sample_doc: Document) -> None:
        msgs = SanityCheckMessages()
        msgs.error(sample_doc.pk, "broken")
        msgs.warning(None, "orphan")
        output = _render_to_string(msgs)
        assert "errors" in output
        assert "warnings" in output
        assert "Found 2 document(s)" in output

    def test_infos_only(self, sample_doc: Document) -> None:
        msgs = SanityCheckMessages()
        msgs.info(sample_doc.pk, "no OCR")
        output = _render_to_string(msgs)
        assert "infos" in output


# ---------------------------------------------------------------------------
# End-to-end command execution
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.management
class TestDocumentSanityCheckerCommand:
    def test_no_issues(self, sample_doc: Document) -> None:
        out = StringIO()
        call_command("document_sanity_checker", "--no-progress-bar", stdout=out)
        assert "No issues detected" in out.getvalue()

    @pytest.mark.usefixtures("_media_settings")
    def test_no_issues_empty_archive(self) -> None:
        out = StringIO()
        call_command("document_sanity_checker", "--no-progress-bar", stdout=out)
        assert "No issues detected" in out.getvalue()

    def test_missing_original(self, sample_doc: Document) -> None:
        Path(sample_doc.source_path).unlink()
        out = StringIO()
        call_command("document_sanity_checker", "--no-progress-bar", stdout=out)
        output = out.getvalue()
        assert "ERROR" in output
        assert "Original of document does not exist" in output

    @pytest.mark.usefixtures("_media_settings")
    def test_checksum_mismatch(self, paperless_dirs: PaperlessDirs) -> None:
        """Lightweight document with zero-byte files triggers checksum mismatch."""
        doc = DocumentFactory(
            title="test",
            content="test",
            filename="test.pdf",
            checksum="abc",
        )
        Path(doc.source_path).touch()
        Path(doc.thumbnail_path).touch()

        out = StringIO()
        call_command("document_sanity_checker", "--no-progress-bar", stdout=out)
        output = out.getvalue()
        assert "ERROR" in output
        assert "Checksum mismatch. Stored: abc, actual:" in output
