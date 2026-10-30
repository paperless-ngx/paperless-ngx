# src/paperless_benchmark/scenarios.py
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from django.contrib.auth.models import User
    from django.db.models import QuerySet


@dataclass(frozen=True, slots=True)
class Scenario:
    name: str
    describe: str
    run: Callable[[User], Any]
    queryset_for_explain: Callable[[User], QuerySet] | None = None


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


def _guardian_visibility_query_run(user: User) -> list[int]:
    return list(
        _guardian_visibility_query_queryset(user).values_list("id", flat=True),
    )


def _guardian_visibility_query_queryset(user: User) -> QuerySet:
    from documents.models import Document
    from documents.permissions import restrict_queryset_to_visible

    return restrict_queryset_to_visible(Document.objects.all(), user, "view_document")


register(
    Scenario(
        name="guardian_visibility_query",
        describe=(
            "Document-visibility queryset for a user with mixed owned/shared "
            "documents -- exercises documents.permissions."
            "restrict_queryset_to_visible's permitted_object_ids subquery."
        ),
        run=_guardian_visibility_query_run,
        queryset_for_explain=_guardian_visibility_query_queryset,
    ),
)


def _permitted_document_ids_run(user: User) -> list[int]:
    from documents.models import Document
    from documents.permissions import permitted_document_ids

    return list(
        Document.objects.filter(id__in=permitted_document_ids(user)).values_list(
            "id",
            flat=True,
        ),
    )


def _permitted_document_ids_queryset(user: User) -> QuerySet:
    from documents.models import Document
    from documents.permissions import permitted_document_ids

    return Document.objects.filter(id__in=permitted_document_ids(user))


register(
    Scenario(
        name="permitted_document_ids",
        describe=(
            "Document-visibility query built from documents.permissions."
            "permitted_document_ids -- like guardian_visibility_query, but a "
            "version is authorized by its root document."
        ),
        run=_permitted_document_ids_run,
        queryset_for_explain=_permitted_document_ids_queryset,
    ),
)
