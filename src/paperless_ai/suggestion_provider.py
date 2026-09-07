"""Document-aware HTTP boundary shared by native suggestions and workflows."""

import hashlib
import itertools
import json
import uuid
from datetime import date
from typing import Literal

import httpx
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import ValidationError
from pydantic import field_validator

from documents.classifier import load_classifier
from documents.matching import match_correspondents
from documents.matching import match_document_types
from documents.matching import match_storage_paths
from documents.matching import match_tags
from documents.models import Correspondent
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import restrict_queryset_to_visible
from documents.plugins.date_parsing import get_date_parser
from documents.versioning import get_latest_version_for_root
from paperless.network import create_pinned_httpx_client
from paperless_ai.base_model import ClassificationSuggestions
from paperless_ai.db import db_connection_released
from paperless_ai.exceptions import StaleSuggestions
from paperless_ai.exceptions import SuggestionProviderError
from paperless_ai.exceptions import SuggestionProviderUnavailable


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    existing_ids: list[int] = Field(default_factory=list, max_length=100)
    new_names: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("existing_ids")
    @classmethod
    def positive_ids(cls, values):
        if any(value < 1 for value in values):
            raise ValueError("IDs must be positive")
        return list(dict.fromkeys(values))

    @field_validator("new_names")
    @classmethod
    def valid_names(cls, values):
        if any(not value.strip() or len(value) > 128 for value in values):
            raise ValueError("Names must contain 1 to 128 characters")
        return list(dict.fromkeys(values))


class Suggestions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str = Field(max_length=128)
    tags: Choice
    correspondents: Choice
    document_types: Choice
    storage_paths: Choice
    dates: list[str] = Field(max_length=3)

    @field_validator("dates")
    @classmethod
    def valid_dates(cls, values):
        for value in values:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError("Dates must use YYYY-MM-DD")
        return values


class ProviderResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    protocol_version: Literal[1]
    request_id: str
    context_id: str
    suggestions: Suggestions


TAXONOMY = {
    "tags": (Tag, "view_tag", match_tags),
    "correspondents": (Correspondent, "view_correspondent", match_correspondents),
    "document_types": (DocumentType, "view_documenttype", match_document_types),
    "storage_paths": (StoragePath, "view_storagepath", match_storage_paths),
}


def fingerprint(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, cls=DjangoJSONEncoder).encode(),
    ).hexdigest()


def document_snapshot(document: Document) -> dict:
    """Saved metadata plus the actual source version of the effective Content."""
    source = (
        get_latest_version_for_root(document)
        if document.root_document_id is None
        else document
    )
    snapshot = {
        "id": document.pk,
        "root_document_id": document.root_document_id,
        "owner_id": document.owner_id,
        "modified": document.modified,
        "title": document.title,
        "created": document.created,
        "correspondent": document.correspondent_id,
        "document_type": document.document_type_id,
        "storage_path": document.storage_path_id,
        "archive_serial_number": document.archive_serial_number,
        "tags": sorted(document.tags.values_list("pk", flat=True)),
        "custom_fields": [
            {
                "field": item.field_id,
                "name": item.field.name,
                "data_type": item.field.data_type,
                "value": item.value,
            }
            for item in CustomFieldInstance.objects.filter(document=document)
            .select_related("field")
            .order_by("field_id")
        ],
        "content": source.content,
        "content_version": {
            "id": source.pk,
            "version_index": source.version_index,
            "checksum": source.checksum,
            "archive_checksum": source.archive_checksum,
            "modified": source.modified,
            "mime_type": source.mime_type,
            "original_filename": source.original_filename,
        },
    }
    return json.loads(json.dumps(snapshot, cls=DjangoJSONEncoder))


def post_provider(payload: dict) -> dict:
    """Bounded, DNS-pinned HTTP call. Redirects and environment proxies are off."""
    headers = (
        {"Authorization": f"Bearer {settings.AI_SUGGESTIONS_API_KEY}"}
        if settings.AI_SUGGESTIONS_API_KEY
        else {}
    )
    try:
        with (
            db_connection_released(),
            create_pinned_httpx_client(
                settings.AI_SUGGESTIONS_ENDPOINT,
                allow_internal=settings.AI_SUGGESTIONS_ALLOW_INTERNAL,
                timeout=settings.AI_SUGGESTIONS_TIMEOUT,
                follow_redirects=False,
                trust_env=False,
            ) as client,
            client.stream(
                "POST",
                settings.AI_SUGGESTIONS_ENDPOINT,
                json=payload,
                headers=headers,
            ) as response,
        ):
            if (
                response.status_code in {408, 409, 425, 429}
                or response.status_code >= 500
            ):
                raise SuggestionProviderUnavailable(
                    "Suggestion provider temporarily unavailable",
                )
            if response.status_code != 200:
                raise SuggestionProviderError(
                    "Suggestion provider rejected the request",
                )
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 1_048_576:
                    raise SuggestionProviderError(
                        "Suggestion provider response exceeds 1 MiB",
                    )
            value = json.loads(body)
            if not isinstance(value, dict):
                raise SuggestionProviderError(
                    "Suggestion provider returned an invalid response",
                )
            return value
    except httpx.TransportError:
        raise SuggestionProviderUnavailable(
            "Suggestion provider connection failed",
        ) from None
    except (ValueError, UnicodeError):
        raise SuggestionProviderError(
            "Invalid suggestion provider configuration or response",
        ) from None


def get_provider_classification(
    document: Document,
    user=None,
    output_language=None,
) -> ClassificationSuggestions:
    document.refresh_from_db()
    snapshot = document_snapshot(document)
    taxonomy = {}
    classic: dict[str, list[int] | list[str]] = {}
    classifier = load_classifier()
    for key, (model, permission, match) in TAXONOMY.items():
        taxonomy[key] = list(
            restrict_queryset_to_visible(
                model.objects.all(),
                user,
                permission,
            )
            .order_by("pk")
            .values("id", "name"),
        )
        allowed = {item["id"] for item in taxonomy[key]}
        classic[key] = [
            item.pk for item in match(document, classifier, user) if item.pk in allowed
        ]
    with get_date_parser() as parser:
        dates = parser.parse(
            snapshot["content_version"]["original_filename"] or "",
            snapshot["content"],
        )
        classic["dates"] = sorted(
            {
                value.strftime("%Y-%m-%d")
                for value in itertools.islice(
                    dates,
                    max(settings.NUMBER_OF_SUGGESTED_DATES, 0),
                )
                if value is not None
            },
        )
    context = {
        "document": snapshot,
        "requester_id": user.pk if user else None,
        "output_language": output_language,
        "taxonomy": taxonomy,
        "classic_suggestions": classic,
    }
    payload = {
        "protocol_version": 1,
        "event": "suggestions.requested",
        "request_id": str(uuid.uuid4()),
        "context_id": fingerprint(context),
        **context,
    }
    try:
        response = ProviderResponse.model_validate(post_provider(payload))
    except ValidationError:
        raise SuggestionProviderError(
            "Suggestion provider returned invalid suggestions",
        ) from None
    if (
        response.request_id != payload["request_id"]
        or response.context_id != payload["context_id"]
    ):
        raise SuggestionProviderError(
            "Suggestion provider response does not match the request",
        )
    try:
        current = document_snapshot(Document.objects.get(pk=document.pk))
    except Document.DoesNotExist:
        raise StaleSuggestions("Document no longer exists") from None
    if fingerprint(current) != fingerprint(snapshot):
        raise StaleSuggestions(
            "Document changed during suggestion generation; request suggestions again",
        )
    for key in TAXONOMY:
        allowed = {item["id"] for item in taxonomy[key]}
        if not set(getattr(response.suggestions, key).existing_ids) <= allowed:
            raise SuggestionProviderError(
                "Suggestion provider returned an ID outside the permitted taxonomy",
            )
    return ClassificationSuggestions(**response.suggestions.model_dump())


def applied_event(
    document_id: int,
    action_id: int,
    changed_fields: list[str],
    task_id: str | None,
) -> dict:
    snapshot = document_snapshot(Document.objects.get(pk=document_id))
    return {
        "protocol_version": 1,
        "event": "suggestions.applied",
        "event_id": task_id or str(uuid.uuid4()),
        "document_id": document_id,
        "content_version_id": snapshot["content_version"]["id"],
        "document_state_id": fingerprint(snapshot),
        "workflow_action_id": action_id,
        "changed_fields": changed_fields,
    }
