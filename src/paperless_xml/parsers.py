import subprocess
from pathlib import Path

from documents.parsers import ParseError
from documents.parsers import make_thumbnail_from_pdf
from paperless_text.parsers import TextDocumentParser


class XMLDocumentParser(TextDocumentParser):
    """
    This parser parses a xml document (.xml)
    """

    logging_name = "paperless.parsing.xml"

    is_invoice = False

    def get_thumbnail(self, document_path: Path, mime_type, file_name=None) -> Path:
        if self.is_invoice:
            return make_thumbnail_from_pdf(
                self.archive_path,
                self.tempdir,
                self.logging_group,
            )
        else:
            return super().get_thumbnail(document_path, mime_type, file_name)

    def xml_to_pdf_mustang(
        self,
        document_path: Path,
        mime_type,
        file_name=None,
    ) -> Path:
        outpdf = Path(self.tempdir, "out.pdf")
        res = subprocess.run(
            [
                "mustang-cli.jar",
                "--action",
                "pdf",
                "--source",
                document_path,
                "--out",
                outpdf,
            ],
            timeout=20,
        )
        if res.returncode != 0:
            raise ParseError("Mustang CLI exited with code: " + str(res.returncode))
        else:
            return outpdf

    def attach_xml_pdf_mustang(self, pdf_path, xml_path) -> Path:
        outpdf = Path(self.tempdir, "combined.pdf")
        res = subprocess.run(
            [
                "mustang-cli.jar",
                "--action",
                "combine",
                "--source",
                pdf_path,
                "--source-xml",
                xml_path,
                "--format",
                "zf",
                "--version",
                "2",
                "--profile",
                "X",
                "--no-additional-attachments",
                "--out",
                outpdf,
            ],
            timeout=20,
        )
        if res.returncode != 0:
            raise ParseError("Mustang CLI exited with code: " + str(res.returncode))
        else:
            return outpdf

    def is_xrechnung_mustang(
        self,
        document_path: Path,
        mime_type,
        file_name=None,
    ) -> bool:
        res = subprocess.run(
            [
                "mustang-cli.jar",
                "--action",
                "validate",
                "--source",
                document_path,
                "--no-notices",
            ],
            timeout=20,
        )
        return res.returncode == 0

    def parse(self, document_path, mime_type, file_name=None):
        super().parse(document_path, mime_type, file_name)
        if self.is_xrechnung_mustang(document_path, mime_type, file_name):
            self.is_invoice = True
            pdfOnly = self.xml_to_pdf_mustang(document_path, mime_type, file_name)
            pdfWith = self.attach_xml_pdf_mustang(pdfOnly, document_path)
            self.archive_path = pdfWith
        else:
            self.is_invoice = False
