"""An operation-local snapshot of tag edges, with no persistent derived fields.

Never cache this globally: tasks, bulk updates and other processes can change
parents. Callers traversing multiple tags should share one snapshot.
"""

from collections import defaultdict
from collections.abc import Iterable


class TagHierarchy:
    def __init__(self, edges: Iterable[tuple[int, int | None]]) -> None:
        self.parents = dict(edges)
        self.children: dict[int | None, list[int]] = defaultdict(list)
        for pk, parent in self.parents.items():
            self.children[parent].append(pk)

    def ancestors(self, parent_id: int | None) -> list[int]:
        result = []
        seen = set()
        while parent_id is not None and parent_id not in seen:
            seen.add(parent_id)
            result.append(parent_id)
            parent_id = self.parents.get(parent_id)
        return result[::-1]

    def with_ancestors(self, roots: Iterable[int]) -> set[int]:
        result = set(roots)
        for pk in list(result):
            result.update(self.ancestors(self.parents.get(pk)))
        return result

    def with_descendants(self, roots: Iterable[int]) -> set[int]:
        roots = set(roots)
        return roots | self.descendants(roots)

    def descendants(self, roots: Iterable[int]) -> set[int]:
        roots = {pk for pk in roots if pk is not None}
        seen = set(roots)
        pending = list(roots)
        while pending:
            for child in self.children.get(pending.pop(), ()):
                if child not in seen:
                    seen.add(child)
                    pending.append(child)
        return seen - roots

    def height(self, pk: int | None) -> int:
        if pk is None:
            return 0
        seen = {pk}
        pending = [(pk, 0)]
        height = 0
        while pending:
            parent, depth = pending.pop()
            height = max(height, depth)
            for child in self.children.get(parent, ()):
                if child not in seen:
                    seen.add(child)
                    pending.append((child, depth + 1))
        return height
