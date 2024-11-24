import logging
import re
from fnmatch import fnmatch

from documents.classifier import DocumentClassifier
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentSource
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Workflow
from documents.models import WorkflowTrigger
from documents.permissions import get_objects_for_user_owner_aware

logger = logging.getLogger("paperless.matching")


def log_reason(
    matching_model: MatchingModel | WorkflowTrigger,
    document: Document,
    reason: str,
):
    class_name = type(matching_model).__name__
    name = (
        matching_model.name if hasattr(matching_model, "name") else str(matching_model)
    )
    logger.debug(
        f"{class_name} {name} matched on document {document} because {reason}",
    )


def match_correspondents(document: Document, classifier: DocumentClassifier, user=None):
    pred_id = classifier.predict_correspondent(document.content) if classifier else None

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
            lambda o: matches(o, document)
            or (o.pk == pred_id and o.matching_algorithm == MatchingModel.MATCH_AUTO),
            correspondents,
        ),
    )


def match_document_types(document: Document, classifier: DocumentClassifier, user=None):
    pred_id = classifier.predict_document_type(document.content) if classifier else None

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
            lambda o: matches(o, document)
            or (o.pk == pred_id and o.matching_algorithm == MatchingModel.MATCH_AUTO),
            document_types,
        ),
    )


def match_tags(document: Document, classifier: DocumentClassifier, user=None):
    predicted_tag_ids = classifier.predict_tags(document.content) if classifier else []

    if user is None and document.owner is not None:
        user = document.owner

    if user is not None:
        tags = get_objects_for_user_owner_aware(user, "documents.view_tag", Tag)
    else:
        tags = Tag.objects.all()

    return list(
        filter(
            lambda o: matches(o, document)
            or (
                o.matching_algorithm == MatchingModel.MATCH_AUTO
                and o.pk in predicted_tag_ids
            ),
            tags,
        ),
    )


def match_storage_paths(document: Document, classifier: DocumentClassifier, user=None):
    pred_id = classifier.predict_storage_path(document.content) if classifier else None

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
            lambda o: matches(o, document)
            or (o.pk == pred_id and o.matching_algorithm == MatchingModel.MATCH_AUTO),
            storage_paths,
        ),
    )


def matches(matching_model: MatchingModel, document: Document):
    search_kwargs = {}

    document_content = document.content

    # Check that match is not empty
    if not matching_model.match.strip():
        return False

    if matching_model.is_insensitive:
        search_kwargs = {"flags": re.IGNORECASE}

    if matching_model.matching_algorithm == MatchingModel.MATCH_NONE:
        return False

    elif matching_model.matching_algorithm == MatchingModel.MATCH_ALL:
        for word in _split_match(matching_model):
            search_result = re.search(rf"\b{word}\b", document_content, **search_kwargs)
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
            if re.search(rf"\b{word}\b", document_content, **search_kwargs):
                log_reason(matching_model, document, f"it contains this word: {word}")
                return True
        return False

    elif matching_model.matching_algorithm == MatchingModel.MATCH_LITERAL:
        result = bool(
            re.search(
                rf"\b{re.escape(matching_model.match)}\b",
                document_content,
                **search_kwargs,
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
        try:
            match = re.search(
                re.compile(matching_model.match, **search_kwargs),
                document_content,
            )
        except re.error:
            logger.error(
                f"Error while processing regular expression {matching_model.match}",
            )
            return False
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
    if (
        trigger.filter_path is not None
        and len(trigger.filter_path) > 0
        and not fnmatch(
            document.original_file,
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
) -> tuple[bool, str]:
    """
    Returns True if the Document matches all filters from the workflow trigger,
    False otherwise. Includes a reason if doesn't match
    """

    trigger_matched = True
    reason = ""

    if trigger.matching_algorithm > MatchingModel.MATCH_NONE and not matches(
        trigger,
        document,
    ):
        reason = (
            f"Document content matching settings for algorithm '{trigger.matching_algorithm}' did not match",
        )
        trigger_matched = False

    # Document tags vs trigger has_tags
    if (
        trigger.filter_has_tags.all().count() > 0
        and document.tags.filter(
            id__in=trigger.filter_has_tags.all().values_list("id"),
        ).count()
        == 0
    ):
        reason = (
            f"Document tags {document.tags.all()} do not include"
            f" {trigger.filter_has_tags.all()}",
        )
        trigger_matched = False

    # Document correspondent vs trigger has_correspondent
    if (
        trigger.filter_has_correspondent is not None
        and document.correspondent != trigger.filter_has_correspondent
    ):
        reason = (
            f"Document correspondent {document.correspondent} does not match {trigger.filter_has_correspondent}",
        )
        trigger_matched = False

    # Document document_type vs trigger has_document_type
    if (
        trigger.filter_has_document_type is not None
        and document.document_type != trigger.filter_has_document_type
    ):
        reason = (
            f"Document doc type {document.document_type} does not match {trigger.filter_has_document_type}",
        )
        trigger_matched = False

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
        reason = (
            f"Document filename {document.original_filename} does not match"
            f" {trigger.filter_filename.lower()}",
        )
        trigger_matched = False

    return (trigger_matched, reason)


def document_matches_workflow(
    document: ConsumableDocument | Document,
    workflow: Workflow,
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
) -> bool:
    """
    Returns True if the ConsumableDocument or Document matches all filters and
    settings from the workflow trigger, False otherwise
    """

    trigger_matched = True
    if workflow.triggers.filter(type=trigger_type).count() == 0:
        trigger_matched = False
        logger.info(f"Document did not match {workflow}")
        logger.debug(f"No matching triggers with type {trigger_type} found")
    else:
        for trigger in workflow.triggers.filter(type=trigger_type):
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
