"""API views for OCR templates."""

import subprocess
import tempfile
from pathlib import Path

from django.conf import settings
from django.http import Http404
from django.http import HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from documents.models import CustomField
from documents.models import Document
from documents.models_ocr_templates import OcrTemplate
from documents.permissions import PaperlessObjectPermissions
from documents.serialisers_ocr_templates import OcrTemplateSerializer
from documents.zone_ocr import run_zone_extraction


class OcrTemplateViewSet(ModelViewSet):
    """CRUD for OCR templates with zone definitions."""

    queryset = OcrTemplate.objects.all().prefetch_related(
        "zones",
        "zones__custom_field",
    ).order_by("name")
    serializer_class = OcrTemplateSerializer
    permission_classes = (IsAuthenticated, PaperlessObjectPermissions)

    @action(
        detail=False,
        methods=["get"],
        url_path=r"document-page-image/(?P<doc_id>[0-9]+)/(?P<page>[0-9]+)",
    )
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

        # Validate page number
        if document.page_count and page_num >= document.page_count:
            raise Http404(
                f"Page {page_num} out of range (document has {document.page_count} pages)"
            )

        doc_path = document.archive_path or document.source_path
        if not doc_path or not Path(doc_path).is_file():
            raise Http404("Document file not found")

        # Check if document is an image (single page, no PDF rendering needed)
        if document.mime_type and document.mime_type.startswith("image/"):
            content = Path(doc_path).read_bytes()
            return HttpResponse(content, content_type=document.mime_type)

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
            except subprocess.CalledProcessError as e:
                raise Http404(
                    f"Failed to render page: {e.stderr.decode(errors='replace')[:200]}"
                )
            except FileNotFoundError:
                raise Http404("pdftoppm not available — is poppler-utils installed?")

            rendered = sorted(Path(tmp_dir).glob("page-*.png"))
            if not rendered:
                raise Http404("No rendered page found")

            content = rendered[0].read_bytes()

        return HttpResponse(content, content_type="image/png")

    @action(
        detail=True,
        methods=["post"],
        url_path=r"test/(?P<doc_id>[0-9]+)",
    )
    def test_extraction(self, request, pk=None, doc_id=None):
        """Run zone extraction on a specific document and return results.

        This writes the extracted values to the document's custom fields
        (via update_or_create) so the results are immediately visible.
        """
        template = self.get_object()

        try:
            document = Document.objects.get(pk=doc_id)
        except Document.DoesNotExist:
            return Response(
                {"error": "Document not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        doc_path = document.archive_path or document.source_path
        if not doc_path or not Path(doc_path).is_file():
            return Response(
                {"error": "Document file not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        run_zone_extraction(document, Path(doc_path))

        # Refresh and return the extracted values
        results = []
        for zone in template.zones.all():
            cf_instance = document.custom_fields.filter(field=zone.custom_field).first()
            results.append({
                "zone": zone.name,
                "custom_field": zone.custom_field.name,
                "custom_field_type": zone.custom_field.data_type,
                "value": cf_instance.value if cf_instance else None,
            })

        return Response({"results": results})

    @action(detail=False, methods=["post"], url_path="quick-create-field")
    def quick_create_field(self, request):
        """Create a custom field inline from the template editor.

        Accepts: {"name": "Invoice Number", "data_type": "string"}
        Returns the created field so the frontend can immediately use it.
        """
        name = request.data.get("name", "").strip()
        data_type = request.data.get("data_type", "").strip()

        if not name:
            return Response(
                {"error": "Field name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_types = {
            CustomField.FieldDataType.STRING,
            CustomField.FieldDataType.URL,
            CustomField.FieldDataType.DATE,
            CustomField.FieldDataType.INT,
            CustomField.FieldDataType.FLOAT,
            CustomField.FieldDataType.MONETARY,
            CustomField.FieldDataType.LONG_TEXT,
            CustomField.FieldDataType.BOOL,
        }
        if data_type not in valid_types:
            return Response(
                {
                    "error": f"Unsupported data type '{data_type}'. "
                    f"Supported: {', '.join(sorted(t.value for t in valid_types))}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if field already exists
        existing = CustomField.objects.filter(name=name).first()
        if existing:
            return Response({
                "id": existing.pk,
                "name": existing.name,
                "data_type": existing.data_type,
                "created": False,
            })

        # Check user has permission to create custom fields
        if not request.user.has_perm("documents.add_customfield"):
            return Response(
                {"error": "You don't have permission to create custom fields"},
                status=status.HTTP_403_FORBIDDEN,
            )

        field = CustomField.objects.create(name=name, data_type=data_type)
        return Response(
            {
                "id": field.pk,
                "name": field.name,
                "data_type": field.data_type,
                "created": True,
            },
            status=status.HTTP_201_CREATED,
        )
