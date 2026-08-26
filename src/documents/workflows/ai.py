import logging
from datetime import date
from datetime import datetime

from django.contrib.auth.models import User

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.models import WorkflowAction
from paperless.config import AIConfig
from paperless_ai.ai_classifier import get_ai_document_classification
from paperless_ai.ai_classifier import get_llm_output_language
from paperless_ai.matching import extract_unmatched_names
from paperless_ai.matching import match_correspondents_by_name
from paperless_ai.matching import match_document_types_by_name
from paperless_ai.matching import match_storage_paths_by_name
from paperless_ai.matching import match_tags_by_name
from paperless_ai.matching import resolve_correspondent_ids
from paperless_ai.matching import resolve_document_type_ids
from paperless_ai.matching import resolve_storage_path_ids
from paperless_ai.matching import resolve_tag_ids

logger = logging.getLogger("paperless.workflows.ai")

AISuggestionField = WorkflowAction.AISuggestionField

# Tags use m2m relation instead
DIRECT_FIELDS: dict[str, str] = {
    AISuggestionField.TITLE: "title",
    AISuggestionField.CORRESPONDENT: "correspondent",
    AISuggestionField.DOCUMENT_TYPE: "document_type",
    AISuggestionField.STORAGE_PATH: "storage_path",
    AISuggestionField.CREATED: "created",
}


def resolve_date(dates: list[str]) -> date | None:
    """
    First usable date out of the suggestions, which are expected as
    YYYY-MM-DD. Document.created is a DateField, so only one can be applied.
    """
    for value in dates:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            logger.debug("Ignoring unparsable suggested date %s", value)
    return None


def resolve_object(
    model,
    names: list[str],
    matched: list,
    *,
    create_missing: bool,
    owner: User | None,
):
    """
    Single object from a suggestion list. The best match if there was one, else
    optionally a newly-created object. StoragePaths are excluded.
    """
    if matched:
        return matched[0]

    if not create_missing or model is StoragePath:
        return None

    unmatched = extract_unmatched_names(names, matched)
    if not unmatched:
        return None

    # (name, owner) is what MatchingModel is unique on
    obj, created = model.objects.get_or_create(
        name=unmatched[0][:128],
        owner=owner,
    )
    if created:
        logger.info("Created %s '%s' from AI suggestion", model.__name__, obj.name)
    return obj


def resolve_tags(
    names: list[str],
    matched: list[Tag],
    *,
    create_missing: bool,
    owner: User | None,
) -> list[Tag]:
    """
    Matched tags, plus newly created ones if create_missing is set.
    """
    tags = list(matched)
    if not create_missing:
        return tags

    for name in extract_unmatched_names(names, matched):
        tag, created = Tag.objects.get_or_create(
            name=name[:128],
            owner=owner,
        )
        if created:
            logger.info("Created tag '%s' from AI suggestion", tag.name)
        tags.append(tag)
    return tags


def apply_ai_suggestions_to_document(
    action: WorkflowAction,
    document: Document,
    logging_group=None,
) -> list[str]:
    """
    Get suggestions about `document` and write the chosen fields.

    Returns the names of the fields that were actually changed.
    """
    selected = set(action.ai_suggestion_fields or [])
    if not selected:
        logger.warning(
            "Workflow action %s has no AI suggestion fields selected, skipping",
            action.pk,
            extra={"group": logging_group},
        )
        return []

    ai_config = AIConfig()
    if not ai_config.ai_enabled:
        logger.error(
            "AI is not enabled, cannot apply AI suggestions for document %s",
            document.pk,
            extra={"group": logging_group},
        )
        return []

    # Workflows run without a user, so we use the document owner
    owner = document.owner

    try:
        suggestions = get_ai_document_classification(
            document,
            owner,
            get_llm_output_language(ai_config, owner),
        )
    except ValueError:
        # A bad AI config will not fix itself, so swallow it rather than
        # letting the caller retry. Timeouts, rate limits, network errors etc
        # propagate so the queued task can back off and try again.
        logger.exception(
            "Invalid AI configuration, cannot get suggestions for document %s",
            document.pk,
            extra={"group": logging_group},
        )
        return []

    overwrite = action.ai_overwrite_existing
    create_missing = action.ai_create_missing
    updated_fields: list[str] = []

    def should_set(field: str) -> bool:
        # The field is selected and (overwrite or it's empty)
        return field in selected and (
            overwrite or getattr(document, DIRECT_FIELDS[field]) in (None, "")
        )

    if should_set(AISuggestionField.TITLE):
        title = suggestions["title"].strip()
        if title:
            # title is capped at 128 characters
            document.title = title[:128]
            updated_fields.append("title")

    if should_set(AISuggestionField.CORRESPONDENT):
        choice = suggestions["correspondents"]
        names = choice["new_names"]
        correspondent = resolve_object(
            Correspondent,
            names,
            resolve_correspondent_ids(choice["existing_ids"], owner)
            + match_correspondents_by_name(names, owner),
            create_missing=create_missing,
            owner=owner,
        )
        if correspondent:
            document.correspondent = correspondent
            updated_fields.append("correspondent")

    if should_set(AISuggestionField.DOCUMENT_TYPE):
        choice = suggestions["document_types"]
        names = choice["new_names"]
        document_type = resolve_object(
            DocumentType,
            names,
            resolve_document_type_ids(choice["existing_ids"], owner)
            + match_document_types_by_name(names, owner),
            create_missing=create_missing,
            owner=owner,
        )
        if document_type:
            document.document_type = document_type
            updated_fields.append("document_type")

    if should_set(AISuggestionField.STORAGE_PATH):
        choice = suggestions["storage_paths"]
        names = choice["new_names"]
        storage_path = resolve_object(
            StoragePath,
            names,
            resolve_storage_path_ids(choice["existing_ids"], owner)
            + match_storage_paths_by_name(names, owner),
            create_missing=create_missing,
            owner=owner,
        )
        if storage_path:
            document.storage_path = storage_path
            updated_fields.append("storage_path")

    if should_set(AISuggestionField.CREATED):
        created = resolve_date(suggestions["dates"])
        if created:
            document.created = created
            updated_fields.append("created")

    if updated_fields:
        # save fields and update modified
        document.save(update_fields=[*updated_fields, "modified"])

    if AISuggestionField.TAGS in selected:
        choice = suggestions["tags"]
        names = choice["new_names"]
        tags = resolve_tags(
            names,
            resolve_tag_ids(choice["existing_ids"], owner)
            + match_tags_by_name(names, owner),
            create_missing=create_missing,
            owner=owner,
        )
        if tags:
            # Suggested tags are always added, so overwrite_existing
            # does not really apply here
            document.add_nested_tags(tags)
            updated_fields.append("tags")

    logger.info(
        "Applied AI suggestions %s to document %s",
        updated_fields or "(none)",
        document.pk,
        extra={"group": logging_group},
    )

    return updated_fields
