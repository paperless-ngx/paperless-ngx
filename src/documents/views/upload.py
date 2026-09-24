import os
import tempfile
from datetime import datetime
from pathlib import Path
from time import mktime
from typing import Any
from unicodedata import normalize

import pathvalidate
from django.conf import settings
from django.http import HttpResponseForbidden
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from drf_spectacular.utils import extend_schema_view
from rest_framework import parsers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.data_models import DocumentSource
from documents.models import PaperlessTask
from documents.serialisers.upload import PostDocumentSerializer
from documents.tasks import consume_file


@extend_schema_view(
    post=extend_schema(
        description="Upload a document via the API",
        external_docs={
            "description": "Further documentation",
            "url": "https://docs.paperless-ngx.com/api/#file-uploads",
        },
        responses={
            (200, "application/json"): OpenApiTypes.STR,
        },
    ),
)
class PostDocumentView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated,)
    serializer_class = PostDocumentSerializer
    parser_classes = (parsers.MultiPartParser,)

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("documents.add_document"):
            return HttpResponseForbidden("Insufficient permissions")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        doc_name, doc_data = serializer.validated_data.get("document")
        doc_name = normalize("NFC", doc_name)
        correspondent_id = serializer.validated_data.get("correspondent")
        document_type_id = serializer.validated_data.get("document_type")
        storage_path_id = serializer.validated_data.get("storage_path")
        tag_ids = serializer.validated_data.get("tags")
        title = serializer.validated_data.get("title")
        created = serializer.validated_data.get("created")
        archive_serial_number = serializer.validated_data.get("archive_serial_number")
        cf = serializer.validated_data.get("custom_fields")
        from_webui = serializer.validated_data.get("from_webui")

        t = int(mktime(datetime.now().timetuple()))

        settings.SCRATCH_DIR.mkdir(parents=True, exist_ok=True)

        temp_file_path = Path(tempfile.mkdtemp(dir=settings.SCRATCH_DIR)) / Path(
            pathvalidate.sanitize_filename(doc_name),
        )

        temp_file_path.write_bytes(doc_data)

        os.utime(temp_file_path, times=(t, t))

        input_doc = ConsumableDocument(
            source=DocumentSource.WebUI if from_webui else DocumentSource.ApiUpload,
            original_file=temp_file_path,
        )
        custom_fields = None
        if isinstance(cf, dict) and cf:
            custom_fields = cf
        elif isinstance(cf, list) and cf:
            custom_fields = dict.fromkeys(cf, None)
        input_doc_overrides = DocumentMetadataOverrides(
            filename=doc_name,
            title=title,
            correspondent_id=correspondent_id,
            document_type_id=document_type_id,
            storage_path_id=storage_path_id,
            tag_ids=tag_ids,
            created=created,
            asn=archive_serial_number,
            owner_id=request.user.id,
            custom_fields=custom_fields,
        )

        async_task = consume_file.apply_async(
            kwargs={"input_doc": input_doc, "overrides": input_doc_overrides},
            headers={
                "trigger_source": (
                    PaperlessTask.TriggerSource.WEB_UI
                    if from_webui
                    else PaperlessTask.TriggerSource.API_UPLOAD
                ),
            },
        )

        return Response(async_task.id)
