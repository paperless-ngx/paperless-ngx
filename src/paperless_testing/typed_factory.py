"""
A DjangoModelFactory base whose calls are typed as the model they build.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar

from factory.django import DjangoModelFactory

T = TypeVar("T")


class TypedModelFactory(DjangoModelFactory[T]):
    if TYPE_CHECKING:
        # factory-boy leaves Factory() unannotated, so mypy takes it to build a
        # factory instance. At runtime it builds the model.
        def __new__(cls, *args: Any, **kwargs: Any) -> T: ...  # type: ignore[misc]
