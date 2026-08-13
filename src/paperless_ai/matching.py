import difflib
import logging
import re
from typing import TypeVar

from django.contrib.auth.models import User
from django.db.models import Model
from django.db.models import QuerySet

from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag
from documents.permissions import get_objects_for_user_owner_aware
from documents.permissions import visible_object_ids_or_none

MATCH_THRESHOLD = 0.8

logger = logging.getLogger("paperless_ai.matching")

ModelT = TypeVar("ModelT", bound=Model)


def _resolve_visible_ids(
    ids: list[int],
    user: User | None,
    model: type[ModelT],
    perm: str,
) -> list[ModelT]:
    """Resolve model-returned IDs against what the user may currently see.
    Invalid, deleted, or now-invisible IDs are silently dropped - the model's
    belief that an ID exists and is visible may be stale by the time the
    response comes back.
    """
    if not ids:
        return []
    visible_ids = visible_object_ids_or_none(user, model, perm)
    queryset = model.objects.filter(pk__in=ids)
    if visible_ids is not None:
        queryset = queryset.filter(pk__in=visible_ids)
    return list(queryset)


def resolve_tag_ids(ids: list[int], user: User | None) -> list[Tag]:
    return _resolve_visible_ids(ids, user, Tag, "view_tag")


def resolve_correspondent_ids(
    ids: list[int],
    user: User | None,
) -> list[Correspondent]:
    return _resolve_visible_ids(ids, user, Correspondent, "view_correspondent")


def resolve_document_type_ids(ids: list[int], user: User | None) -> list[DocumentType]:
    return _resolve_visible_ids(ids, user, DocumentType, "view_documenttype")


def resolve_storage_path_ids(ids: list[int], user: User | None) -> list[StoragePath]:
    return _resolve_visible_ids(ids, user, StoragePath, "view_storagepath")


def _match_by_name(
    names: list[str],
    user: User,
    model: type[ModelT],
    perm: str,
) -> list[ModelT]:
    queryset = get_objects_for_user_owner_aware(user, [perm], model)
    return _match_names_to_queryset(names, queryset)


def match_tags_by_name(names: list[str], user: User) -> list[Tag]:
    return _match_by_name(names, user, Tag, "view_tag")


def match_correspondents_by_name(
    names: list[str],
    user: User,
) -> list[Correspondent]:
    return _match_by_name(names, user, Correspondent, "view_correspondent")


def match_document_types_by_name(names: list[str], user: User) -> list[DocumentType]:
    return _match_by_name(names, user, DocumentType, "view_documenttype")


def match_storage_paths_by_name(names: list[str], user: User) -> list[StoragePath]:
    return _match_by_name(names, user, StoragePath, "view_storagepath")


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)  # remove punctuation
    s = s.strip()
    return s


def _match_names_to_queryset(
    names: list[str],
    queryset: QuerySet[ModelT],
    attr: str = "name",
) -> list[ModelT]:
    """Match each name to at most one object, exactly first and fuzzily as a
    fallback. A matched object is removed from the pool so two names can never
    resolve to the same object; names that match nothing are simply skipped.
    """
    results: list[ModelT] = []
    objects = list(queryset)
    object_names = [_normalize(getattr(obj, attr)) for obj in objects]

    for name in names:
        if not name:
            continue
        target = _normalize(name)

        if target in object_names:
            index = object_names.index(target)
        else:
            matches = difflib.get_close_matches(
                target,
                object_names,
                n=1,
                cutoff=MATCH_THRESHOLD,
            )
            if not matches:
                continue
            index = object_names.index(matches[0])

        object_names.pop(index)  # keep both lists aligned after removal
        results.append(objects.pop(index))
    return results


def extract_unmatched_names(
    names: list[str],
    matched_objects: list,
    attr="name",
) -> list[str]:
    matched_names = {_normalize(getattr(obj, attr)) for obj in matched_objects}
    return [name for name in names if _normalize(name) not in matched_names]
