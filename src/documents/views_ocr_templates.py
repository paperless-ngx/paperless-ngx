"""API views for OCR templates."""

import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from django.http import Http404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from documents.models import Document
from documents.models_ocr_templates import OcrTemplate
from documents.serialisers_ocr_templates import OcrTemplateSerializer
from documents.zone_ocr import run_zone_extraction


class OcrTemplateViewSet(ModelViewSet):
    """CRUD for OCR templates with zone definitions."""

    queryset = OcrTemplate.objects.all().prefetch_related("zones").order_by("name")
    serializer_class = OcrTemplateSerializer

    @action(detail=False, methods=["get"], url_path="document-page-image/(?P<doc_id>[0-9]+)/(?P<page>[0-9]+)")
    def document_page_image(self, request, doc_id=None, page=None):
        """Render a specific page of a document as a PNG image.

        Used by the frontend template editor to display document pages
        as images that users can draw zones on.
        """
        try:
            document = Document.objects.get(pk=doc_id)
        except Document.DoesNotExist:
            raise Http404("Document not found")

        page_num = int(page)
        doc_path = document.archive_path or document.source_path

        if not doc_path or not Path(doc_path).exists():
            raise Http404("Document file not found")

        with tempfile.TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
            output_prefix = Path(tmp_dir) / "page"
            try:
                subprocess.run(
                    [
                        "pdftoppm",
                        "-png",
                        "-r", "150",  # Lower DPI for preview
                        "-f", str(page_num + 1),
                        "-l", str(page_num + 1),
                        str(doc_path),
                        str(output_prefix),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise Http404("Failed to render page")

            rendered = list(Path(tmp_dir).glob("page-*.png"))
            if not rendered:
                raise Http404("No rendered page found")

            # Read into memory since tmp_dir will be cleaned up
            content = rendered[0].read_bytes()

        response = FileResponse(
            content_type="image/png",
            streaming_content=iter([content]),
        )
        response["Content-Disposition"] = f'inline; filename="page_{page_num}.png"'
        return response

    @action(detail=True, methods=["post"], url_path="test/(?P<doc_id>[0-9]+)")
    def test_extraction(self, request, pk=None, doc_id=None):
        """Run zone extraction on a specific document and return results without saving."""
        template = self.get_object()

        try:
            document = Document.objects.get(pk=doc_id)
        except Document.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        doc_path = document.archive_path or document.source_path
        if not doc_path or not Path(doc_path).exists():
            return Response(
                {"error": "Document file not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Run extraction (this writes to custom fields)
        run_zone_extraction(document, Path(doc_path))

        # Return the extracted values
        results = []
        for zone in template.zones.all():
            cf_instance = document.custom_fields.filter(field=zone.custom_field).first()
            results.append({
                "zone": zone.name,
                "custom_field": zone.custom_field.name,
                "value": cf_instance.value if cf_instance else None,
            })

        return Response({"results": results})
