import difflib
import logging
import re

from django.contrib.auth.models import User

from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import get_objects_for_user_owner_aware

MATCH_THRESHOLD = 0.8

logger = logging.getLogger("paperless_ai.matching")


def match_tags_by_name(
    names: list[str],
    user: User,
    hinted_names: set[str] | None = None,
) -> list[Tag]:
    queryset = get_objects_for_user_owner_aware(
        user,
        ["view_tag"],
        Tag,
    )
    return _match_names_to_queryset(names, queryset, "name", hinted_names)


def match_correspondents_by_name(
    names: list[str],
    user: User,
    hinted_names: set[str] | None = None,
) -> list[Correspondent]:
    queryset = get_objects_for_user_owner_aware(
        user,
        ["view_correspondent"],
        Correspondent,
    )
    return _match_names_to_queryset(names, queryset, "name", hinted_names)


def match_document_types_by_name(
    names: list[str],
    user: User,
    hinted_names: set[str] | None = None,
) -> list[DocumentType]:
    queryset = get_objects_for_user_owner_aware(
        user,
        ["view_documenttype"],
        DocumentType,
    )
    return _match_names_to_queryset(names, queryset, "name", hinted_names)


def match_storage_paths_by_name(
    names: list[str],
    user: User,
    hinted_names: set[str] | None = None,
) -> list[StoragePath]:
    queryset = get_objects_for_user_owner_aware(
        user,
        ["view_storagepath"],
        StoragePath,
    )
    return _match_names_to_queryset(names, queryset, "name", hinted_names)


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)  # remove punctuation
    s = s.strip()
    return s


def _match_names_to_queryset(
    names: list[str],
    queryset,
    attr: str,
    hinted_names: set[str] | None = None,
):
    results = []
    objects = list(queryset)
    object_names = [_normalize(getattr(obj, attr)) for obj in objects]
    normalized_hints = (
        {_normalize(name) for name in hinted_names} if hinted_names else set()
    )

    for name in names:
        if not name:
            continue
        target = _normalize(name)

        # First try exact match
        if target in object_names:
            index = object_names.index(target)
            matched = objects.pop(index)
            object_names.pop(index)  # keep object list aligned after removal
            results.append(matched)
            continue

        # A hinted name that didn't exact-match came from existing taxonomy
        # verbatim; do not fuzzy-map it onto a different object.
        if target in normalized_hints:
            continue

        # Fuzzy match fallback
        matches = difflib.get_close_matches(
            target,
            object_names,
            n=1,
            cutoff=MATCH_THRESHOLD,
        )
        if matches:
            index = object_names.index(matches[0])
            matched = objects.pop(index)
            object_names.pop(index)
            results.append(matched)
    return results


def extract_unmatched_names(
    names: list[str],
    matched_objects: list,
    attr="name",
) -> list[str]:
    matched_names = {_normalize(getattr(obj, attr)) for obj in matched_objects}
    return [name for name in names if _normalize(name) not in matched_names]
