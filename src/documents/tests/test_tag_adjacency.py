from typing import TYPE_CHECKING

import pytest
from django.core.exceptions import FieldDoesNotExist
from django.db import connection
from django.test.utils import CaptureQueriesContext

from documents.management.commands.document_importer import _deserialize_record
from documents.models import Tag
from documents.tag_hierarchy import TagHierarchy
from paperless_testing.factories import TagFactory
from paperless_testing.migrations import TestMigrations

if TYPE_CHECKING:
    from django.apps.registry import Apps
    from pytest_django.fixtures import DjangoAssertNumQueries


@pytest.mark.django_db
class TestTagAdjacency:
    def test_held_instance_uses_current_parent_edges(self) -> None:
        """Descendant lookups reflect parent changes made after loading a tag."""
        first = TagFactory(name="First")
        second = TagFactory(name="Second")
        child = TagFactory(name="Child", tn_parent=first)
        Tag.objects.filter(pk=child.pk).update(tn_parent=second)
        assert first.get_descendants_pks() == set()
        assert second.get_descendants_pks() == {child.pk}

    def test_queryset_delete_preserves_cascade(self) -> None:
        """Deleting a parent through a queryset deletes only its subtree."""
        root = TagFactory(name="Root")
        child = TagFactory(name="Child", tn_parent=root)
        TagFactory(name="Grandchild", tn_parent=child)
        survivor = TagFactory(name="Other root")
        Tag.objects.filter(pk=root.pk).delete()
        assert list(Tag.objects.values_list("pk", flat=True)) == [survivor.pk]

    def test_flat_writes_do_not_update_other_tags(self) -> None:
        """Creating and renaming flat tags never rewrite unrelated tag rows."""
        TagFactory.create_batch(100)
        with CaptureQueriesContext(connection) as queries:
            new = TagFactory(name="New")
        assert not any(q["sql"].startswith("UPDATE") for q in queries)
        with CaptureQueriesContext(connection) as queries:
            new.name = "Renamed"
            new.save()
        tag_updates = [
            q["sql"] for q in queries if q["sql"].startswith('UPDATE "documents_tag"')
        ]
        assert len(tag_updates) == 1
        assert 'WHERE "documents_tag"."id" =' in tag_updates[0]

    def test_batch_snapshot_is_one_query_and_includes_overlapping_roots(
        self,
        django_assert_num_queries: "DjangoAssertNumQueries",
    ) -> None:
        """One edge query supports multiple traversals with overlapping roots."""
        root = TagFactory(name="Root")
        child = TagFactory(name="Child", tn_parent=root)
        leaf = TagFactory(name="Leaf", tn_parent=child)
        with django_assert_num_queries(1):
            hierarchy = Tag.get_hierarchy()
            assert hierarchy.with_ancestors([leaf.pk]) == {root.pk, child.pk, leaf.pk}
            assert hierarchy.with_descendants([root.pk, child.pk]) == {
                root.pk,
                child.pk,
                leaf.pk,
            }
        assert hierarchy.height(None) == 0

    def test_legacy_export_fields_are_ignored_but_parent_is_preserved(self) -> None:
        """Legacy bookkeeping is ignored while parent links and field checks survive."""
        model, tag, m2m = _deserialize_record(
            {
                "model": "documents.tag",
                "pk": 2,
                "fields": {
                    "name": "Child",
                    "tn_parent": 1,
                    "tn_order": 3,
                    "tn_siblings_pks": "4,5",
                    "tn_descendants_pks": "6",
                },
            },
        )
        assert model is Tag
        assert tag.tn_parent_id == 1
        assert tag.name == "Child"
        assert not m2m
        with pytest.raises(FieldDoesNotExist):
            _deserialize_record(
                {"model": "documents.tag", "pk": 3, "fields": {"tn_typo": "bad"}},
            )

    def test_malformed_cycles_terminate(self) -> None:
        """Traversal terminates even when stored parent edges contain a cycle."""
        hierarchy = TagHierarchy([(1, 2), (2, 1)])
        assert hierarchy.with_descendants([1]) == {1, 2}
        assert set(hierarchy.ancestors(2)) == {1, 2}


class TestTagAdjacencyMigration(TestMigrations):
    migrate_from = "0027_documentbarcode"
    migrate_to = "0028_replace_tag_tree_fields"

    def setUpBeforeMigration(self, apps: "Apps") -> None:
        """Seed parent links using the model from the pre-migration state."""
        tag = apps.get_model("documents", "Tag")
        root = tag.objects.create(name="Root")
        child = tag.objects.create(name="Child", tn_parent=root)
        self.edges = [(root.pk, None), (child.pk, root.pk)]

    def test_parent_edges_survive(self) -> None:
        """Removing derived tree columns preserves the existing parent links."""
        tag = self.apps.get_model("documents", "Tag")
        assert (
            list(tag.objects.order_by("pk").values_list("pk", "tn_parent_id"))
            == self.edges
        )
        assert {
            field.name for field in tag._meta.fields if field.name.startswith("tn_")
        } == {"tn_parent"}
