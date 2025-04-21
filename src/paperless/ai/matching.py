import difflib
import logging
import re

from documents.models import Correspondent
from documents.models import DocumentType
from documents.models import StoragePath
from documents.models import Tag

MATCH_THRESHOLD = 0.7

logger = logging.getLogger("paperless.ai.matching")


def match_tags_by_name(names: list[str], user) -> list[Tag]:
    queryset = (
        Tag.objects.filter(owner=user) if user.is_authenticated else Tag.objects.all()
    )
    return _match_names_to_queryset(names, queryset, "name")


def match_correspondents_by_name(names: list[str], user) -> list[Correspondent]:
    queryset = (
        Correspondent.objects.filter(owner=user)
        if user.is_authenticated
        else Correspondent.objects.all()
    )
    return _match_names_to_queryset(names, queryset, "name")


def match_document_types_by_name(names: list[str]) -> list[DocumentType]:
    return _match_names_to_queryset(names, DocumentType.objects.all(), "name")


def match_storage_paths_by_name(names: list[str], user) -> list[StoragePath]:
    queryset = (
        StoragePath.objects.filter(owner=user)
        if user.is_authenticated
        else StoragePath.objects.all()
    )
    return _match_names_to_queryset(names, queryset, "name")


def _normalize(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^\w\s]", "", s)  # remove punctuation
    s = s.strip()
    return s


def _match_names_to_queryset(names: list[str], queryset, attr: str):
    results = []
    objects = list(queryset)
    object_names = [getattr(obj, attr) for obj in objects]
    norm_names = [_normalize(name) for name in object_names]

    for name in names:
        if not name:
            continue
        target = _normalize(name)

        # First try exact match
        if target in norm_names:
            index = norm_names.index(target)
            results.append(objects[index])
            continue

        # Fuzzy match fallback
        matches = difflib.get_close_matches(
            target,
            norm_names,
            n=1,
            cutoff=MATCH_THRESHOLD,
        )
        if matches:
            index = norm_names.index(matches[0])
            results.append(objects[index])
        else:
            # Optional: log or store unmatched name
            logging.debug(f"No match for: '{name}' in {attr} list")

    return results


def extract_unmatched_names(
    llm_names: list[str],
    matched_objects: list,
    attr="name",
) -> list[str]:
    matched_names = {getattr(obj, attr).lower() for obj in matched_objects}
    return [name for name in llm_names if name.lower() not in matched_names]
