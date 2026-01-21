"""
Tests for TenantManager automatic filtering functionality.

Verifies that the custom TenantManager correctly filters queries by current tenant
and that the all_objects manager bypasses the filter.
"""

import uuid
from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase
from django.db import connection

from documents.models import (
    Tenant,
    Correspondent,
    Document,
    DocumentType,
    Tag,
    StoragePath,
    SavedView,
    PaperlessTask,
    get_current_tenant_id,
    set_current_tenant_id,
)


class TenantManagerTestCase(TransactionTestCase):
    """Test automatic tenant filtering with TenantManager."""

    def setUp(self):
        """Create test tenants and data."""
        # Create tenant A
        self.tenant_a = Tenant.objects.create(
            name="Tenant A",
            subdomain="tenant-a",
            is_active=True,
        )

        # Create tenant B
        self.tenant_b = Tenant.objects.create(
            name="Tenant B",
            subdomain="tenant-b",
            is_active=True,
        )

        # Create users
        self.user_a = User.objects.create_user(username="user_a", password="test")
        self.user_b = User.objects.create_user(username="user_b", password="test")

        # Set tenant context to A and create test data
        set_current_tenant_id(self.tenant_a.id)

        self.correspondent_a = Correspondent.objects.create(
            name="Correspondent A",
            owner=self.user_a,
        )

        self.tag_a = Tag.objects.create(
            name="Tag A",
            owner=self.user_a,
        )

        self.doctype_a = DocumentType.objects.create(
            name="Type A",
            owner=self.user_a,
        )

        self.storage_path_a = StoragePath.objects.create(
            name="Path A",
            path="/path/a",
            owner=self.user_a,
        )

        self.saved_view_a = SavedView.objects.create(
            name="View A",
            show_on_dashboard=True,
            show_in_sidebar=True,
            owner=self.user_a,
        )

        # Set tenant context to B and create test data
        set_current_tenant_id(self.tenant_b.id)

        self.correspondent_b = Correspondent.objects.create(
            name="Correspondent B",
            owner=self.user_b,
        )

        self.tag_b = Tag.objects.create(
            name="Tag B",
            owner=self.user_b,
        )

        self.doctype_b = DocumentType.objects.create(
            name="Type B",
            owner=self.user_b,
        )

        self.storage_path_b = StoragePath.objects.create(
            name="Path B",
            path="/path/b",
            owner=self.user_b,
        )

        self.saved_view_b = SavedView.objects.create(
            name="View B",
            show_on_dashboard=True,
            show_in_sidebar=False,
            owner=self.user_b,
        )

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant_id(None)

    def test_automatic_filtering_tenant_a(self):
        """Test: Set tenant context to tenant-a → objects.all() returns only tenant-a records."""
        set_current_tenant_id(self.tenant_a.id)

        # Test Correspondent
        correspondents = Correspondent.objects.all()
        self.assertEqual(correspondents.count(), 1)
        self.assertEqual(correspondents.first().name, "Correspondent A")
        self.assertEqual(correspondents.first().tenant_id, self.tenant_a.id)

        # Test Tag
        tags = Tag.objects.all()
        self.assertEqual(tags.count(), 1)
        self.assertEqual(tags.first().name, "Tag A")
        self.assertEqual(tags.first().tenant_id, self.tenant_a.id)

        # Test DocumentType
        doc_types = DocumentType.objects.all()
        self.assertEqual(doc_types.count(), 1)
        self.assertEqual(doc_types.first().name, "Type A")
        self.assertEqual(doc_types.first().tenant_id, self.tenant_a.id)

        # Test StoragePath
        storage_paths = StoragePath.objects.all()
        self.assertEqual(storage_paths.count(), 1)
        self.assertEqual(storage_paths.first().name, "Path A")
        self.assertEqual(storage_paths.first().tenant_id, self.tenant_a.id)

        # Test SavedView
        saved_views = SavedView.objects.all()
        self.assertEqual(saved_views.count(), 1)
        self.assertEqual(saved_views.first().name, "View A")
        self.assertEqual(saved_views.first().tenant_id, self.tenant_a.id)

    def test_automatic_filtering_tenant_b(self):
        """Test: Set tenant context to tenant-b → objects.all() returns only tenant-b records."""
        set_current_tenant_id(self.tenant_b.id)

        # Test Correspondent
        correspondents = Correspondent.objects.all()
        self.assertEqual(correspondents.count(), 1)
        self.assertEqual(correspondents.first().name, "Correspondent B")
        self.assertEqual(correspondents.first().tenant_id, self.tenant_b.id)

        # Test Tag
        tags = Tag.objects.all()
        self.assertEqual(tags.count(), 1)
        self.assertEqual(tags.first().name, "Tag B")
        self.assertEqual(tags.first().tenant_id, self.tenant_b.id)

        # Test DocumentType
        doc_types = DocumentType.objects.all()
        self.assertEqual(doc_types.count(), 1)
        self.assertEqual(doc_types.first().name, "Type B")
        self.assertEqual(doc_types.first().tenant_id, self.tenant_b.id)

        # Test StoragePath
        storage_paths = StoragePath.objects.all()
        self.assertEqual(storage_paths.count(), 1)
        self.assertEqual(storage_paths.first().name, "Path B")
        self.assertEqual(storage_paths.first().tenant_id, self.tenant_b.id)

        # Test SavedView
        saved_views = SavedView.objects.all()
        self.assertEqual(saved_views.count(), 1)
        self.assertEqual(saved_views.first().name, "View B")
        self.assertEqual(saved_views.first().tenant_id, self.tenant_b.id)

    def test_all_objects_bypasses_filter(self):
        """Test: all_objects.all() returns records from all tenants."""
        # No tenant context needed for all_objects
        set_current_tenant_id(None)

        # Test Correspondent
        correspondents = Correspondent.all_objects.all()
        self.assertEqual(correspondents.count(), 2)
        names = set(c.name for c in correspondents)
        self.assertEqual(names, {"Correspondent A", "Correspondent B"})

        # Test Tag
        tags = Tag.all_objects.all()
        self.assertEqual(tags.count(), 2)
        names = set(t.name for t in tags)
        self.assertEqual(names, {"Tag A", "Tag B"})

        # Test DocumentType
        doc_types = DocumentType.all_objects.all()
        self.assertEqual(doc_types.count(), 2)
        names = set(dt.name for dt in doc_types)
        self.assertEqual(names, {"Type A", "Type B"})

        # Test StoragePath
        storage_paths = StoragePath.all_objects.all()
        self.assertEqual(storage_paths.count(), 2)
        names = set(sp.name for sp in storage_paths)
        self.assertEqual(names, {"Path A", "Path B"})

        # Test SavedView
        saved_views = SavedView.all_objects.all()
        self.assertEqual(saved_views.count(), 2)
        names = set(sv.name for sv in saved_views)
        self.assertEqual(names, {"View A", "View B"})

    def test_without_tenant_context_returns_empty(self):
        """Test: Without tenant context → queries return empty queryset (security by default)."""
        set_current_tenant_id(None)

        # All queries should return empty querysets
        self.assertEqual(Correspondent.objects.all().count(), 0)
        self.assertEqual(Tag.objects.all().count(), 0)
        self.assertEqual(DocumentType.objects.all().count(), 0)
        self.assertEqual(StoragePath.objects.all().count(), 0)
        self.assertEqual(SavedView.objects.all().count(), 0)

    def test_filter_chaining_with_tenant_filter(self):
        """Test that additional filters work correctly with automatic tenant filtering."""
        set_current_tenant_id(self.tenant_a.id)

        # Create additional correspondent for tenant A
        Correspondent.objects.create(name="Correspondent A2", owner=self.user_a)

        # Filter should only apply to tenant A's records
        correspondents = Correspondent.objects.filter(name__contains="A2")
        self.assertEqual(correspondents.count(), 1)
        self.assertEqual(correspondents.first().name, "Correspondent A2")

        # Switch to tenant B
        set_current_tenant_id(self.tenant_b.id)

        # Same filter should return nothing for tenant B
        correspondents = Correspondent.objects.filter(name__contains="A2")
        self.assertEqual(correspondents.count(), 0)

    def test_get_queries_with_tenant_filter(self):
        """Test that .get() queries respect tenant filtering."""
        set_current_tenant_id(self.tenant_a.id)

        # Should find correspondent A
        correspondent = Correspondent.objects.get(name="Correspondent A")
        self.assertEqual(correspondent.tenant_id, self.tenant_a.id)

        # Should not find correspondent B (different tenant)
        with self.assertRaises(Correspondent.DoesNotExist):
            Correspondent.objects.get(name="Correspondent B")

        # Switch to tenant B
        set_current_tenant_id(self.tenant_b.id)

        # Now should find correspondent B
        correspondent = Correspondent.objects.get(name="Correspondent B")
        self.assertEqual(correspondent.tenant_id, self.tenant_b.id)

        # Should not find correspondent A
        with self.assertRaises(Correspondent.DoesNotExist):
            Correspondent.objects.get(name="Correspondent A")

    def test_count_queries_with_tenant_filter(self):
        """Test that .count() queries respect tenant filtering."""
        set_current_tenant_id(self.tenant_a.id)
        self.assertEqual(Correspondent.objects.count(), 1)
        self.assertEqual(Tag.objects.count(), 1)

        set_current_tenant_id(self.tenant_b.id)
        self.assertEqual(Correspondent.objects.count(), 1)
        self.assertEqual(Tag.objects.count(), 1)

        set_current_tenant_id(None)
        self.assertEqual(Correspondent.objects.count(), 0)
        self.assertEqual(Tag.objects.count(), 0)

        # all_objects should always return full count
        self.assertEqual(Correspondent.all_objects.count(), 2)
        self.assertEqual(Tag.all_objects.count(), 2)

    def test_exists_queries_with_tenant_filter(self):
        """Test that .exists() queries respect tenant filtering."""
        set_current_tenant_id(self.tenant_a.id)
        self.assertTrue(Correspondent.objects.filter(name="Correspondent A").exists())
        self.assertFalse(Correspondent.objects.filter(name="Correspondent B").exists())

        set_current_tenant_id(self.tenant_b.id)
        self.assertFalse(Correspondent.objects.filter(name="Correspondent A").exists())
        self.assertTrue(Correspondent.objects.filter(name="Correspondent B").exists())

    def test_ordering_with_tenant_filter(self):
        """Test that ordering works correctly with tenant filtering."""
        set_current_tenant_id(self.tenant_a.id)

        # Create multiple records
        Correspondent.objects.create(name="A Correspondent", owner=self.user_a)
        Correspondent.objects.create(name="Z Correspondent", owner=self.user_a)

        # Order by name
        correspondents = Correspondent.objects.order_by("name")
        self.assertEqual(correspondents.count(), 3)
        self.assertEqual(correspondents.first().name, "A Correspondent")
        self.assertEqual(correspondents.last().name, "Z Correspondent")

    def test_related_queries_respect_tenant_filter(self):
        """Test: Related queries (e.g., document.tags.all()) also filtered by tenant."""
        set_current_tenant_id(self.tenant_a.id)

        # Create document with tags for tenant A
        doc_a = Document.objects.create(
            title="Document A",
            mime_type="application/pdf",
            checksum="checksum_a",
            owner=self.user_a,
        )
        doc_a.tags.add(self.tag_a)

        # Create another tag for tenant A
        tag_a2 = Tag.objects.create(name="Tag A2", owner=self.user_a)
        doc_a.tags.add(tag_a2)

        # Switch to tenant B and create document with tags
        set_current_tenant_id(self.tenant_b.id)

        doc_b = Document.objects.create(
            title="Document B",
            mime_type="application/pdf",
            checksum="checksum_b",
            owner=self.user_b,
        )
        doc_b.tags.add(self.tag_b)

        # Test related queries with tenant A context
        set_current_tenant_id(self.tenant_a.id)

        # doc_a should only see its own tags (tenant A)
        doc_a_from_db = Document.objects.get(pk=doc_a.pk)
        tags_for_doc_a = doc_a_from_db.tags.all()
        self.assertEqual(tags_for_doc_a.count(), 2)
        tag_names = set(t.name for t in tags_for_doc_a)
        self.assertEqual(tag_names, {"Tag A", "Tag A2"})

        # doc_b should not be accessible from tenant A
        with self.assertRaises(Document.DoesNotExist):
            Document.objects.get(pk=doc_b.pk)

        # Switch to tenant B
        set_current_tenant_id(self.tenant_b.id)

        # doc_b should only see its own tags (tenant B)
        doc_b_from_db = Document.objects.get(pk=doc_b.pk)
        tags_for_doc_b = doc_b_from_db.tags.all()
        self.assertEqual(tags_for_doc_b.count(), 1)
        self.assertEqual(tags_for_doc_b.first().name, "Tag B")

        # doc_a should not be accessible from tenant B
        with self.assertRaises(Document.DoesNotExist):
            Document.objects.get(pk=doc_a.pk)

    def test_reverse_foreign_key_queries_respect_tenant_filter(self):
        """Test that reverse foreign key queries respect tenant filtering."""
        set_current_tenant_id(self.tenant_a.id)

        # Create documents for correspondent A
        doc_a1 = Document.objects.create(
            title="Doc A1",
            mime_type="application/pdf",
            checksum="checksum_a1",
            correspondent=self.correspondent_a,
            owner=self.user_a,
        )

        doc_a2 = Document.objects.create(
            title="Doc A2",
            mime_type="application/pdf",
            checksum="checksum_a2",
            correspondent=self.correspondent_a,
            owner=self.user_a,
        )

        # Switch to tenant B
        set_current_tenant_id(self.tenant_b.id)

        # Create document for correspondent B
        doc_b = Document.objects.create(
            title="Doc B",
            mime_type="application/pdf",
            checksum="checksum_b",
            correspondent=self.correspondent_b,
            owner=self.user_b,
        )

        # Test with tenant A context
        set_current_tenant_id(self.tenant_a.id)

        # correspondent_a.documents should only show tenant A documents
        correspondent_a_from_db = Correspondent.objects.get(pk=self.correspondent_a.pk)
        documents = correspondent_a_from_db.documents.all()
        self.assertEqual(documents.count(), 2)
        doc_titles = set(d.title for d in documents)
        self.assertEqual(doc_titles, {"Doc A1", "Doc A2"})

        # Test with tenant B context
        set_current_tenant_id(self.tenant_b.id)

        # correspondent_b.documents should only show tenant B documents
        correspondent_b_from_db = Correspondent.objects.get(pk=self.correspondent_b.pk)
        documents = correspondent_b_from_db.documents.all()
        self.assertEqual(documents.count(), 1)
        self.assertEqual(documents.first().title, "Doc B")

    def test_all_existing_functionality_works(self):
        """Test: All existing functionality works with automatic filtering."""
        set_current_tenant_id(self.tenant_a.id)

        # Test create
        new_correspondent = Correspondent.objects.create(
            name="New Correspondent",
            owner=self.user_a,
        )
        self.assertEqual(new_correspondent.tenant_id, self.tenant_a.id)

        # Test update
        new_correspondent.name = "Updated Correspondent"
        new_correspondent.save()

        # Test retrieval
        correspondent_from_db = Correspondent.objects.get(pk=new_correspondent.pk)
        self.assertEqual(correspondent_from_db.name, "Updated Correspondent")

        # Test delete
        pk = new_correspondent.pk
        new_correspondent.delete()
        with self.assertRaises(Correspondent.DoesNotExist):
            Correspondent.objects.get(pk=pk)

    def test_bulk_operations_with_tenant_filter(self):
        """Test that bulk operations respect tenant filtering."""
        set_current_tenant_id(self.tenant_a.id)

        # Create multiple correspondents for tenant A
        Correspondent.objects.create(name="Bulk A1", owner=self.user_a)
        Correspondent.objects.create(name="Bulk A2", owner=self.user_a)

        # Bulk update should only affect tenant A
        Correspondent.objects.filter(name__startswith="Bulk").update(match="test")

        # Verify updates
        correspondents = Correspondent.objects.filter(match="test")
        self.assertEqual(correspondents.count(), 2)

        # Switch to tenant B
        set_current_tenant_id(self.tenant_b.id)

        # Tenant B should not see the updated records
        correspondents = Correspondent.objects.filter(match="test")
        self.assertEqual(correspondents.count(), 0)
