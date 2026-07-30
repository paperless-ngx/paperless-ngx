# src/paperless_benchmark/scenarios.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.db.models import QuerySet

    from paperless_benchmark.seeding import SeededData


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    describe: str
    run: Callable[[SeededData], Any]
    queryset_for_explain: Callable[[SeededData], QuerySet] | None = None


_SCENARIOS: dict[str, Scenario] = {}


def register(scenario: Scenario) -> None:
    _SCENARIOS[scenario.name] = scenario


def get(name: str) -> Scenario:
    from django.core.management.base import CommandError

    try:
        return _SCENARIOS[name]
    except KeyError:
        available = ", ".join(sorted(_SCENARIOS)) or "(none registered)"
        raise CommandError(
            f"Unknown benchmark scenario {name!r}. Available: {available}",
        ) from None


def all_scenarios() -> tuple[Scenario, ...]:
    return tuple(_SCENARIOS.values())


def _guardian_visibility_query_run(data: SeededData) -> list[int]:
    from documents.models import Document
    from documents.permissions import get_objects_for_user_owner_aware

    user = data.users[0]
    return list(
        get_objects_for_user_owner_aware(
            user,
            "documents.view_document",
            Document,
        ).values_list("id", flat=True),
    )


def _guardian_visibility_query_queryset(data: SeededData) -> QuerySet:
    from documents.models import Document
    from documents.permissions import get_objects_for_user_owner_aware

    user = data.users[0]
    return get_objects_for_user_owner_aware(user, "documents.view_document", Document)


register(
    Scenario(
        name="guardian_visibility_query",
        describe=(
            "Document-visibility queryset for a user with mixed owned/shared "
            "documents -- exercises documents.permissions."
            "get_objects_for_user_owner_aware's guardian permission join."
        ),
        run=_guardian_visibility_query_run,
        queryset_for_explain=_guardian_visibility_query_queryset,
    ),
)


def _permitted_document_ids_run(data: SeededData) -> list[int]:
    from documents.models import Document
    from documents.permissions import permitted_document_ids

    user = data.users[0]
    return list(
        Document.objects.filter(id__in=permitted_document_ids(user)).values_list(
            "id",
            flat=True,
        ),
    )


def _permitted_document_ids_queryset(data: SeededData) -> QuerySet:
    from documents.models import Document
    from documents.permissions import permitted_document_ids

    user = data.users[0]
    return Document.objects.filter(id__in=permitted_document_ids(user))


register(
    Scenario(
        name="permitted_document_ids",
        describe=(
            "Document-visibility query built from documents.permissions."
            "permitted_document_ids -- the resolved-ID-set alternative to "
            "guardian_visibility_query, for side-by-side comparison."
        ),
        run=_permitted_document_ids_run,
        queryset_for_explain=_permitted_document_ids_queryset,
    ),
)
