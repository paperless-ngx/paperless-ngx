from types import SimpleNamespace

from paperless_ai.taxonomy import TaxonomyHints
from paperless_ai.taxonomy import build_taxonomy_hints_from_nodes
from paperless_ai.taxonomy import format_hints_for_prompt


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


class TestFormatHintsForPrompt:
    def test_all_blocks_present_when_all_categories_nonempty(self) -> None:
        hints: TaxonomyHints = {
            "tags": ["Bloodwork"],
            "document_types": ["Invoice"],
            "correspondents": ["IRS"],
            "storage_paths": ["Financial"],
        }
        result = format_hints_for_prompt(hints)
        assert "Available tags:" in result
        assert "Available document types:" in result
        assert "Available correspondents:" in result
        assert "Available storage paths:" in result
        assert "- Bloodwork" in result

    def test_empty_category_produces_no_block(self) -> None:
        hints: TaxonomyHints = {
            "tags": ["Bloodwork"],
            "document_types": [],
            "correspondents": [],
            "storage_paths": [],
        }
        result = format_hints_for_prompt(hints)
        assert "Available tags:" in result
        assert "Available document types:" not in result
        assert "Available correspondents:" not in result
        assert "Available storage paths:" not in result

    def test_all_empty_produces_empty_string(self) -> None:
        hints: TaxonomyHints = {
            "tags": [],
            "document_types": [],
            "correspondents": [],
            "storage_paths": [],
        }
        assert format_hints_for_prompt(hints) == ""

    def test_instruction_line_appears_once(self) -> None:
        hints: TaxonomyHints = {
            "tags": ["Bloodwork"],
            "document_types": ["Invoice"],
            "correspondents": [],
            "storage_paths": [],
        }
        result = format_hints_for_prompt(hints)
        assert result.count("Prefer existing names from these lists verbatim") == 1
