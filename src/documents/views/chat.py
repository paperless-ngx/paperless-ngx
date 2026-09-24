from typing import Any

from django.http import HttpResponseBadRequest
from django.http import HttpResponseForbidden
from django.http import StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import serializers
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated

from documents.models import Document
from documents.permissions import ViewDocumentsPermissions
from documents.permissions import has_perms_owner_aware
from documents.permissions import permitted_document_ids
from documents.permissions import user_is_unrestricted
from paperless.config import AIConfig
from paperless_ai.ai_classifier import get_llm_output_language
from paperless_ai.chat import stream_chat_with_documents


class ChatStreamingSerializer(serializers.Serializer[dict[str, Any]]):
    q = serializers.CharField(required=True, max_length=4000)
    document_id = serializers.IntegerField(required=False, allow_null=True)


@method_decorator(
    [
        ensure_csrf_cookie,
        cache_control(no_cache=True),
    ],
    name="dispatch",
)
class ChatStreamingView(GenericAPIView[Any]):
    permission_classes = (IsAuthenticated, ViewDocumentsPermissions)
    serializer_class = ChatStreamingSerializer

    def post(self, request, *args, **kwargs):
        ai_config = AIConfig()
        if not ai_config.ai_enabled:
            return HttpResponseBadRequest("AI is required for this feature")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = serializer.validated_data["q"]

        doc_id = serializer.validated_data.get("document_id")

        if doc_id:
            try:
                document = Document.objects.get(id=doc_id)
            except Document.DoesNotExist:
                return HttpResponseBadRequest("Document not found")

            if not has_perms_owner_aware(request.user, "view_document", document):
                return HttpResponseForbidden("Insufficient permissions")

            documents = Document.objects.filter(pk=document.pk)
            unrestricted = False
        else:
            documents = Document.objects.filter(
                id__in=permitted_document_ids(request.user),
            )
            unrestricted = user_is_unrestricted(request.user)

        output_language = get_llm_output_language(
            ai_config=ai_config,
            user=request.user,
        )

        response = StreamingHttpResponse(
            stream_chat_with_documents(
                query_str=question,
                documents=documents,
                unrestricted=unrestricted,
                output_language=output_language,
            ),
            content_type="text/event-stream",
        )
        return response
