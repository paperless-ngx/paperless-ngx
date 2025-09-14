from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from django.conf import settings
from pikepdf import Page
from pikepdf import Pdf

from documents.data_models import ConsumableDocument
from documents.plugins.base import ConsumeTaskPlugin
from documents.plugins.base import StopConsumeTaskError
from documents.plugins.helpers import ProgressStatusOptions
from documents.utils import copy_basic_file_stats
from documents.utils import copy_file_with_basic_stats

logger = logging.getLogger("paperless.split_pages")


class SplitPagesPlugin(ConsumeTaskPlugin):
    NAME = "SplitPagesPlugin"

    @property
    def able_to_run(self) -> bool:
        enabled = (
            self.metadata.split_pdf_on_upload
            if self.metadata.split_pdf_on_upload is not None
            else settings.CONSUMER_SPLIT_PDF_ON_UPLOAD
        )
        return enabled and self.input_doc.mime_type == "application/pdf"

    def setup(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(
            dir=self.base_tmp_dir,
            prefix="split",
        )
        self.pdf_file: Path = self.input_doc.original_file

    def run(self) -> str | None:
        with Pdf.open(self.pdf_file) as pdf:
            num_pages = len(pdf.pages)

        if num_pages <= 1:
            return None

        pages_to_split = {i: True for i in range(1, num_pages)}

        tmp_dir = Path(
            tempfile.mkdtemp(
                dir=settings.SCRATCH_DIR,
                prefix="paperless-split-pages-",
            ),
        ).resolve()

        from documents import tasks

        for new_document in self.separate_pages(pages_to_split):
            copy_file_with_basic_stats(new_document, tmp_dir / new_document.name)
            tasks.consume_file.delay(
                ConsumableDocument(
                    source=self.input_doc.source,
                    mailrule_id=self.input_doc.mailrule_id,
                    original_file=(tmp_dir / new_document.name).resolve(),
                ),
                self.metadata,
            )

        self.input_doc.original_file.unlink()

        msg = "Page splitting complete!"
        self.status_mgr.send_progress(ProgressStatusOptions.SUCCESS, msg, 100, 100)
        raise StopConsumeTaskError(msg)

    def cleanup(self) -> None:
        self.temp_dir.cleanup()

    def separate_pages(self, pages_to_split_on: dict[int, bool]) -> list[Path]:
        document_paths: list[Path] = []
        fname = self.input_doc.original_file.stem
        with Pdf.open(self.pdf_file) as input_pdf:
            current_document: list[Page] = []
            documents: list[list[Page]] = [current_document]

            for idx, page in enumerate(input_pdf.pages):
                if idx not in pages_to_split_on:
                    current_document.append(page)
                    continue

                logger.debug(f"Starting new document at idx {idx}")
                current_document = []
                documents.append(current_document)
                if pages_to_split_on[idx]:
                    current_document.append(page)

            documents = [x for x in documents if len(x)]

            for doc_idx, document in enumerate(documents):
                dst = Pdf.new()
                dst.pages.extend(document)
                output_filename = f"{fname}_document_{doc_idx}.pdf"
                savepath = Path(self.temp_dir.name) / output_filename
                with savepath.open("wb") as out:
                    dst.save(out)
                copy_basic_file_stats(self.input_doc.original_file, savepath)
                document_paths.append(savepath)

        return document_paths
