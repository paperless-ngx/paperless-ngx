from __future__ import annotations

import logging
import re
from fnmatch import fnmatch
from fnmatch import translate as fnmatch_translate
from typing import TYPE_CHECKING

from rest_framework import serializers

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.filters import CustomFieldQueryParser
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowTrigger
from documents.permissions import get_objects_for_user_owner_aware
from documents.regex import safe_regex_search

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from documents.classifier import DocumentClassifier

logger = logging.getLogger("paperless.matching")


def log_reason(
    matching_model: MatchingModel | WorkflowTrigger,
    document: Document,
    reason: str,
) -> None:
    class_name = type(matching_model).__name__
    name = (
        matching_model.name if hasattr(matching_model, "name") else str(matching_model)
    )
    logger.debug(
        f"{class_name} {name} matched on document {document} because {reason}",
    )


def match_correspondents(document: Document, classifier: DocumentClassifier, user=None):
    pred_id = (
        classifier.predict_correspondent(document.suggestion_content)
        if classifier
        else None
    )

    if user is None and document.owner is not None:
        user = document.owner

    if user is not None:
        correspondents = get_objects_for_user_owner_aware(
            user,
            "documents.view_correspondent",
            Correspondent,
        )
    else:
        correspondents = Correspondent.objects.all()

    return list(
        filter(
            lambda o: (
                matches(o, document)
                or (
                    o.pk == pred_id and o.matching_algorithm == MatchingModel.MATCH_AUTO
                )
            ),
            correspondents,
        ),
    )


def match_document_types(document: Document, classifier: DocumentClassifier, user=None):
    pred_id = (
        classifier.predict_document_type(document.suggestion_content)
        if classifier
        else None
    )
    if user is None and document.owner is not None:
        user = document.owner

    if user is not None:
        document_types = get_objects_for_user_owner_aware(
            user,
            "documents.view_documenttype",
            DocumentType,
        )
    else:
        document_types = DocumentType.objects.all()

    return list(
        filter(
            lambda o: (
                matches(o, document)
                or (
                    o.pk == pred_id and o.matching_algorithm == MatchingModel.MATCH_AUTO
                )
            ),
            document_types,
        ),
    )


def match_tags(document: Document, classifier: DocumentClassifier, user=None):
    predicted_tag_ids = (
        classifier.predict_tags(document.suggestion_content) if classifier else []
    )

    if user is None and document.owner is not None:
        user = document.owner

    if user is not None:
        tags = get_objects_for_user_owner_aware(user, "documents.view_tag", Tag)
    else:
        tags = Tag.objects.all()

    return list(
        filter(
            lambda o: (
                matches(o, document)
                or (
                    o.matching_algorithm == MatchingModel.MATCH_AUTO
                    and o.pk in predicted_tag_ids
                )
            ),
            tags,
        ),
    )


def match_storage_paths(document: Document, classifier: DocumentClassifier, user=None):
    pred_id = (
        classifier.predict_storage_path(document.suggestion_content)
        if classifier
        else None
    )

    if user is None and document.owner is not None:
        user = document.owner

    if user is not None:
        storage_paths = get_objects_for_user_owner_aware(
            user,
            "documents.view_storagepath",
            StoragePath,
        )
    else:
        storage_paths = StoragePath.objects.all()

    return list(
        filter(
            lambda o: (
                matches(o, document)
                or (
                    o.pk == pred_id and o.matching_algorithm == MatchingModel.MATCH_AUTO
                )
            ),
            storage_paths,
        ),
    )


def matches(matching_model: MatchingModel, document: Document):
    search_flags = 0

    document_content = document.content

    # Check that match is not empty
    if not matching_model.match.strip():
        return False

    if matching_model.is_insensitive:
        search_flags = re.IGNORECASE

    if matching_model.matching_algorithm == MatchingModel.MATCH_NONE:
        return False

    elif matching_model.matching_algorithm == MatchingModel.MATCH_ALL:
        for word in _split_match(matching_model):
            search_result = re.search(
                rf"\b{word}\b",
                document_content,
                flags=search_flags,
            )
            if not search_result:
                return False
        log_reason(
            matching_model,
            document,
            f"it contains all of these words: {matching_model.match}",
        )
        return True

    elif matching_model.matching_algorithm == MatchingModel.MATCH_ANY:
        for word in _split_match(matching_model):
            if re.search(rf"\b{word}\b", document_content, flags=search_flags):
                log_reason(matching_model, document, f"it contains this word: {word}")
                return True
        return False

    elif matching_model.matching_algorithm == MatchingModel.MATCH_LITERAL:
        result = bool(
            re.search(
                rf"\b{re.escape(matching_model.match)}\b",
                document_content,
                flags=search_flags,
            ),
        )
        if result:
            log_reason(
                matching_model,
                document,
                f'it contains this string: "{matching_model.match}"',
            )
        return result

    elif matching_model.matching_algorithm == MatchingModel.MATCH_REGEX:
        match = safe_regex_search(
            matching_model.match,
            document_content,
            flags=search_flags,
        )
        if match:
            log_reason(
                matching_model,
                document,
                f"the string {match.group()} matches the regular expression "
                f"{matching_model.match}",
            )
        return bool(match)

    elif matching_model.matching_algorithm == MatchingModel.MATCH_FUZZY:
        from rapidfuzz import fuzz

        match = re.sub(r"[^\w\s]", "", matching_model.match)
        text = re.sub(r"[^\w\s]", "", document_content)
        if matching_model.is_insensitive:
            match = match.lower()
            text = text.lower()
        if fuzz.partial_ratio(match, text, score_cutoff=90):
            # TODO: make this better
            log_reason(
                matching_model,
                document,
                f"parts of the document content somehow match the string "
                f"{matching_model.match}",
            )
            return True
        else:
            return False

    elif matching_model.matching_algorithm == MatchingModel.MATCH_AUTO:
        # this is done elsewhere.
        return False

    else:
        raise NotImplementedError("Unsupported matching algorithm")


def _split_match(matching_model):
    """
    Splits the match to individual keywords, getting rid of unnecessary
    spaces and grouping quoted words together.

    Example:
      '  some random  words "with   quotes  " and   spaces'
        ==>
      ["some", "random", "words", "with+quotes", "and", "spaces"]
    """
    findterms = re.compile(r'"([^"]+)"|(\S+)').findall
    normspace = re.compile(r"\s+").sub
    return [
        # normspace(" ", (t[0] or t[1]).strip()).replace(" ", r"\s+")
        re.escape(normspace(" ", (t[0] or t[1]).strip())).replace(r"\ ", r"\s+")
        for t in findterms(matching_model.match)
    ]


def consumable_document_matches_workflow(
    document: ConsumableDocument,
    trigger: WorkflowTrigger,
) -> tuple[bool, str]:
    """
    Returns True if the ConsumableDocument matches all filters from the workflow trigger,
    False otherwise. Includes a reason if doesn't match
    """

    trigger_matched = True
    reason = ""

    # Document source vs trigger source
    if len(trigger.sources) > 0 and document.source not in [
        int(x) for x in list(trigger.sources)
    ]:
        reason = (
            f"Document source {document.source.name} not in"
            f" {[DocumentSource(int(x)).name for x in trigger.sources]}",
        )
        trigger_matched = False

    # Document mail rule vs trigger mail rule
    if (
        trigger.filter_mailrule is not None
        and document.mailrule_id != trigger.filter_mailrule.pk
    ):
        reason = (
            f"Document mail rule {document.mailrule_id}"
            f" != {trigger.filter_mailrule.pk}",
        )
        trigger_matched = False

    # Document filename vs trigger filename
    if (
        trigger.filter_filename is not None
        and len(trigger.filter_filename) > 0
        and not fnmatch(
            document.original_file.name.lower(),
            trigger.filter_filename.lower(),
        )
    ):
        reason = (
            f"Document filename {document.original_file.name} does not match"
            f" {trigger.filter_filename.lower()}",
        )
        trigger_matched = False

    # Document path vs trigger path

    # Use the original_path if set, else us the original_file
    match_against = (
        document.original_path
        if document.original_path is not None
        else document.original_file
    )

    if (
        trigger.filter_path is not None
        and len(trigger.filter_path) > 0
        and not fnmatch(
            match_against,
            trigger.filter_path,
        )
    ):
        reason = (
            f"Document path {document.original_file}"
            f" does not match {trigger.filter_path}",
        )
        trigger_matched = False

    return (trigger_matched, reason)


def existing_document_matches_workflow(
    document: Document,
    trigger: WorkflowTrigger,
) -> tuple[bool, str | None]:
    """
    Returns True if the Document matches all filters from the workflow trigger,
    False otherwise. Includes a reason if doesn't match
    """

    # Check content matching algorithm
    if trigger.matching_algorithm > MatchingModel.MATCH_NONE and not matches(
        trigger,
        document,
    ):
        return (
            False,
            f"Document content matching settings for algorithm '{trigger.matching_algorithm}' did not match",
        )

    # Check if any tag filters exist to determine if we need to load document tags
    trigger_has_tags_qs = trigger.filter_has_tags.all()
    trigger_has_all_tags_qs = trigger.filter_has_all_tags.all()
    trigger_has_not_tags_qs = trigger.filter_has_not_tags.all()

    has_tags_filter = trigger_has_tags_qs.exists()
    has_all_tags_filter = trigger_has_all_tags_qs.exists()
    has_not_tags_filter = trigger_has_not_tags_qs.exists()

    # Load document tags once if any tag filters exist
    document_tag_ids = None
    if has_tags_filter or has_all_tags_filter or has_not_tags_filter:
        document_tag_ids = set(document.tags.values_list("id", flat=True))

    # Document tags vs trigger has_tags (any of)
    if has_tags_filter:
        trigger_has_tag_ids = set(trigger_has_tags_qs.values_list("id", flat=True))
        if not (document_tag_ids & trigger_has_tag_ids):
            # For error message, load the actual tag objects
            return (
                False,
                f"Document tags {list(document.tags.all())} do not include {list(trigger_has_tags_qs)}",
            )

    # Document tags vs trigger has_all_tags (all of)
    if has_all_tags_filter:
        required_tag_ids = set(trigger_has_all_tags_qs.values_list("id", flat=True))
        if not required_tag_ids.issubset(document_tag_ids):
            return (
                False,
                f"Document tags {list(document.tags.all())} do not contain all of {list(trigger_has_all_tags_qs)}",
            )

    # Document tags vs trigger has_not_tags (none of)
    if has_not_tags_filter:
        excluded_tag_ids = set(trigger_has_not_tags_qs.values_list("id", flat=True))
        if document_tag_ids & excluded_tag_ids:
            return (
                False,
                f"Document tags {list(document.tags.all())} include excluded tags {list(trigger_has_not_tags_qs)}",
            )

    allowed_correspondent_ids = set(
        trigger.filter_has_any_correspondents.values_list("id", flat=True),
    )
    if (
        allowed_correspondent_ids
        and document.correspondent_id not in allowed_correspondent_ids
    ):
        return (
            False,
            f"Document correspondent {document.correspondent} is not one of {list(trigger.filter_has_any_correspondents.all())}",
        )

    # Document correspondent vs trigger has_correspondent
    if (
        trigger.filter_has_correspondent_id is not None
        and document.correspondent_id != trigger.filter_has_correspondent_id
    ):
        return (
            False,
            f"Document correspondent {document.correspondent} does not match {trigger.filter_has_correspondent}",
        )

    if (
        document.correspondent_id
        and trigger.filter_has_not_correspondents.filter(
            id=document.correspondent_id,
        ).exists()
    ):
        return (
            False,
            f"Document correspondent {document.correspondent} is excluded by {list(trigger.filter_has_not_correspondents.all())}",
        )

    allowed_document_type_ids = set(
        trigger.filter_has_any_document_types.values_list("id", flat=True),
    )
    if allowed_document_type_ids and (
        document.document_type_id not in allowed_document_type_ids
    ):
        return (
            False,
            f"Document doc type {document.document_type} is not one of {list(trigger.filter_has_any_document_types.all())}",
        )

    # Document document_type vs trigger has_document_type
    if (
        trigger.filter_has_document_type_id is not None
        and document.document_type_id != trigger.filter_has_document_type_id
    ):
        return (
            False,
            f"Document doc type {document.document_type} does not match {trigger.filter_has_document_type}",
        )

    if (
        document.document_type_id
        and trigger.filter_has_not_document_types.filter(
            id=document.document_type_id,
        ).exists()
    ):
        return (
            False,
            f"Document doc type {document.document_type} is excluded by {list(trigger.filter_has_not_document_types.all())}",
        )

    allowed_storage_path_ids = set(
        trigger.filter_has_any_storage_paths.values_list("id", flat=True),
    )
    if allowed_storage_path_ids and (
        document.storage_path_id not in allowed_storage_path_ids
    ):
        return (
            False,
            f"Document storage path {document.storage_path} is not one of {list(trigger.filter_has_any_storage_paths.all())}",
        )

    # Document storage_path vs trigger has_storage_path
    if (
        trigger.filter_has_storage_path_id is not None
        and document.storage_path_id != trigger.filter_has_storage_path_id
    ):
        return (
            False,
            f"Document storage path {document.storage_path} does not match {trigger.filter_has_storage_path}",
        )

    if (
        document.storage_path_id
        and trigger.filter_has_not_storage_paths.filter(
            id=document.storage_path_id,
        ).exists()
    ):
        return (
            False,
            f"Document storage path {document.storage_path} is excluded by {list(trigger.filter_has_not_storage_paths.all())}",
        )

    # Custom field query check
    if trigger.filter_custom_field_query:
        parser = CustomFieldQueryParser("filter_custom_field_query")
        try:
            custom_field_q, annotations = parser.parse(
                trigger.filter_custom_field_query,
            )
        except serializers.ValidationError:
            return (False, "Invalid custom field query configuration")

        qs = (
            Document.objects.filter(id=document.id)
            .annotate(**annotations)
            .filter(custom_field_q)
        )
        if not qs.exists():
            return (
                False,
                "Document custom fields do not match the configured custom field query",
            )

    # Document original_filename vs trigger filename
    if (
        trigger.filter_filename is not None
        and len(trigger.filter_filename) > 0
        and document.original_filename is not None
        and not fnmatch(
            document.original_filename.lower(),
            trigger.filter_filename.lower(),
        )
    ):
        return (
            False,
            f"Document filename {document.original_filename} does not match {trigger.filter_filename.lower()}",
        )

    return (True, None)


def prefilter_documents_by_workflowtrigger(
    documents: QuerySet[Document],
    trigger: WorkflowTrigger,
) -> QuerySet[Document]:
    """
    To prevent scheduled workflows checking every document, we prefilter the
    documents by the workflow trigger filters. This is done before e.g.
    document_matches_workflow in run_workflows
    """

    # Filter for documents that have AT LEAST ONE of the specified tags.
    if trigger.filter_has_tags.exists():
        documents = documents.filter(tags__in=trigger.filter_has_tags.all()).distinct()

    # Filter for documents that have ALL of the specified tags.
    if trigger.filter_has_all_tags.exists():
        for tag in trigger.filter_has_all_tags.all():
            documents = documents.filter(tags=tag)
        # Multiple JOINs can create duplicate results.
        documents = documents.distinct()

    # Exclude documents that have ANY of the specified tags.
    if trigger.filter_has_not_tags.exists():
        documents = documents.exclude(tags__in=trigger.filter_has_not_tags.all())

    # Correspondent, DocumentType, etc. filtering

    if trigger.filter_has_any_correspondents.exists():
        documents = documents.filter(
            correspondent__in=trigger.filter_has_any_correspondents.all(),
        )
    if trigger.filter_has_correspondent is not None:
        documents = documents.filter(
            correspondent=trigger.filter_has_correspondent,
        )
    if trigger.filter_has_not_correspondents.exists():
        documents = documents.exclude(
            correspondent__in=trigger.filter_has_not_correspondents.all(),
        )

    if trigger.filter_has_any_document_types.exists():
        documents = documents.filter(
            document_type__in=trigger.filter_has_any_document_types.all(),
        )
    if trigger.filter_has_document_type is not None:
        documents = documents.filter(
            document_type=trigger.filter_has_document_type,
        )
    if trigger.filter_has_not_document_types.exists():
        documents = documents.exclude(
            document_type__in=trigger.filter_has_not_document_types.all(),
        )

    if trigger.filter_has_any_storage_paths.exists():
        documents = documents.filter(
            storage_path__in=trigger.filter_has_any_storage_paths.all(),
        )
    if trigger.filter_has_storage_path is not None:
        documents = documents.filter(
            storage_path=trigger.filter_has_storage_path,
        )
    if trigger.filter_has_not_storage_paths.exists():
        documents = documents.exclude(
            storage_path__in=trigger.filter_has_not_storage_paths.all(),
        )

    # Custom Field & Filename Filtering

    if trigger.filter_custom_field_query:
        parser = CustomFieldQueryParser("filter_custom_field_query")
        try:
            custom_field_q, annotations = parser.parse(
                trigger.filter_custom_field_query,
            )
        except serializers.ValidationError:
            return documents.none()

        documents = documents.annotate(**annotations).filter(custom_field_q)

    if trigger.filter_filename:
        regex = fnmatch_translate(trigger.filter_filename).lstrip("^").rstrip("$")
        documents = documents.filter(original_filename__iregex=regex)

    return documents


def document_matches_workflow(
    document: ConsumableDocument | Document,
    workflow: Workflow,
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
) -> bool:
    """
    Returns True if the ConsumableDocument or Document matches all filters and
    settings from the workflow trigger, False otherwise
    """

    triggers_queryset = (
        workflow.triggers.filter(
            type=trigger_type,
        )
        .select_related(
            "filter_mailrule",
            "filter_has_document_type",
            "filter_has_correspondent",
            "filter_has_storage_path",
            "schedule_date_custom_field",
        )
        .prefetch_related(
            "filter_has_tags",
            "filter_has_all_tags",
            "filter_has_not_tags",
            "filter_has_any_document_types",
            "filter_has_not_document_types",
            "filter_has_any_correspondents",
            "filter_has_not_correspondents",
            "filter_has_any_storage_paths",
            "filter_has_not_storage_paths",
        )
    )

    trigger_matched = True
    if not triggers_queryset.exists():
        trigger_matched = False
        logger.info(f"Document did not match {workflow}")
        logger.debug(f"No matching triggers with type {trigger_type} found")
    else:
        for trigger in triggers_queryset:
            if trigger_type == WorkflowTrigger.WorkflowTriggerType.CONSUMPTION:
                trigger_matched, reason = consumable_document_matches_workflow(
                    document,
                    trigger,
                )
            elif (
                trigger_type == WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED
                or trigger_type == WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED
                or trigger_type == WorkflowTrigger.WorkflowTriggerType.SCHEDULED
            ):
                trigger_matched, reason = existing_document_matches_workflow(
                    document,
                    trigger,
                )
            else:
                # New trigger types need to be explicitly checked above
                raise Exception(f"Trigger type {trigger_type} not yet supported")

            if trigger_matched:
                logger.info(f"Document matched {trigger} from {workflow}")
                # matched, bail early
                return True
            else:
                logger.info(f"Document did not match {workflow}")
                logger.debug(reason)

    return trigger_matched
