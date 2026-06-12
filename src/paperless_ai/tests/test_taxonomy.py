from types import SimpleNamespace

from paperless_ai.taxonomy import build_taxonomy_hints_from_nodes


def make_node(**metadata: object) -> SimpleNamespace:
    """A stand-in for NodeWithScore: only ``.metadata`` is accessed."""
    return SimpleNamespace(metadata=metadata)


class TestBuildTaxonomyHintsFromNodes:
    def test_returns_all_four_keys(self) -> None:
        hints = build_taxonomy_hints_from_nodes([])
        assert set(hints.keys()) == {
            "tags",
            "document_types",
            "correspondents",
            "storage_paths",
        }

    def test_collects_and_sorts_values(self) -> None:
        nodes = [
            make_node(
                tags=["Taxes", "Bloodwork"],
                document_type="Invoice",
                correspondent="IRS",
                storage_path="Financial",
            ),
        ]
        hints = build_taxonomy_hints_from_nodes(nodes)
        assert hints["tags"] == ["Bloodwork", "Taxes"]
        assert hints["document_types"] == ["Invoice"]
        assert hints["correspondents"] == ["IRS"]
        assert hints["storage_paths"] == ["Financial"]

    def test_deduplicates_across_nodes(self) -> None:
        nodes = [
            make_node(tags=["Taxes"], document_type="Invoice"),
            make_node(tags=["Taxes", "Medical"], document_type="Invoice"),
        ]
        hints = build_taxonomy_hints_from_nodes(nodes)
        assert hints["tags"] == ["Medical", "Taxes"]
        assert hints["document_types"] == ["Invoice"]

    def test_none_values_skipped(self) -> None:
        nodes = [
            make_node(
                tags=["Taxes", None, ""],
                document_type=None,
                correspondent=None,
                storage_path=None,
            ),
        ]
        hints = build_taxonomy_hints_from_nodes(nodes)
        assert hints["tags"] == ["Taxes"]
        assert hints["document_types"] == []
        assert hints["correspondents"] == []
        assert hints["storage_paths"] == []

    def test_missing_storage_path_key_handled(self) -> None:
        # Pre-enrichment nodes have no storage_path key at all.
        nodes = [make_node(tags=["Taxes"], document_type="Invoice")]
        hints = build_taxonomy_hints_from_nodes(nodes)
        assert hints["storage_paths"] == []

    def test_empty_node_list_all_empty(self) -> None:
        hints = build_taxonomy_hints_from_nodes([])
        assert hints == {
            "tags": [],
            "document_types": [],
            "correspondents": [],
            "storage_paths": [],
        }

    def test_output_stable_across_calls(self) -> None:
        nodes = [make_node(tags=["b", "a", "c"])]
        assert build_taxonomy_hints_from_nodes(
            nodes,
        ) == build_taxonomy_hints_from_nodes(nodes)
