"""
Tests for PostgreSQL Row-Level Security (RLS) tenant isolation.

Verifies that RLS policies correctly enforce tenant isolation at the database level.
"""

import uuid
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, TransactionTestCase
from paperless.models import Tenant
from documents.models import (
    Correspondent,
    Document,
    DocumentType,
    Tag,
    StoragePath,
    Note,
    CustomField,
    CustomFieldInstance,
    SavedView,
    PaperlessTask,
)
from documents.models import set_current_tenant_id


class RLSTenantIsolationTest(TransactionTestCase):
    """
    Test Row-Level Security policies for tenant isolation.

    Uses TransactionTestCase to ensure database transactions are committed,
    allowing RLS policies to take effect.
    """

    def setUp(self):
        """
        Create two tenants and test data for each.
        """
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

        # Create users for each tenant
        self.user_a = User.objects.create_user(username="user_a", password="test")
        self.user_b = User.objects.create_user(username="user_b", password="test")

    def tearDown(self):
        """
        Clean up: reset PostgreSQL session variable.
        """
        with connection.cursor() as cursor:
            cursor.execute("SET app.current_tenant = ''")

    def _set_tenant_context(self, tenant):
        """
        Set tenant context in both thread-local storage and PostgreSQL session.

        Args:
            tenant: Tenant object to set as current
        """
        set_current_tenant_id(tenant.id)
        with connection.cursor() as cursor:
            cursor.execute("SET app.current_tenant = %s", [str(tenant.id)])

    def _verify_rls_active(self, table_name):
        """
        Verify that RLS is enabled and forced for a table.

        Args:
            table_name: Name of the table to check

        Returns:
            tuple: (rls_enabled, rls_forced)
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = %s
            """, [table_name])
            result = cursor.fetchone()
            return result if result else (False, False)

    def _verify_policy_exists(self, table_name, policy_name='tenant_isolation_policy'):
        """
        Verify that a specific RLS policy exists for a table.

        Args:
            table_name: Name of the table to check
            policy_name: Name of the policy to verify

        Returns:
            bool: True if policy exists, False otherwise
        """
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM pg_policies
                WHERE tablename = %s AND policyname = %s
            """, [table_name, policy_name])
            count = cursor.fetchone()[0]
            return count > 0

    def test_rls_enabled_on_all_tables(self):
        """
        Test that RLS is enabled on all tenant-aware tables.
        """
        tables = [
            'documents_document',
            'documents_tag',
            'documents_correspondent',
            'documents_documenttype',
            'documents_savedview',
            'documents_storagepath',
            'documents_note',
            'documents_customfield',
            'documents_customfieldinstance',
            'documents_paperlesstask',
        ]

        for table in tables:
            with self.subTest(table=table):
                rls_enabled, rls_forced = self._verify_rls_active(table)
                self.assertTrue(
                    rls_enabled,
                    f"RLS should be enabled on {table}"
                )
                self.assertTrue(
                    rls_forced,
                    f"RLS should be forced on {table}"
                )

    def test_tenant_isolation_policies_exist(self):
        """
        Test that tenant_isolation_policy exists for all tables.
        """
        tables = [
            'documents_document',
            'documents_tag',
            'documents_correspondent',
            'documents_documenttype',
            'documents_savedview',
            'documents_storagepath',
            'documents_note',
            'documents_customfield',
            'documents_customfieldinstance',
            'documents_paperlesstask',
        ]

        for table in tables:
            with self.subTest(table=table):
                policy_exists = self._verify_policy_exists(table)
                self.assertTrue(
                    policy_exists,
                    f"tenant_isolation_policy should exist on {table}"
                )

    def test_correspondent_tenant_isolation(self):
        """
        Test that Correspondent objects are isolated by tenant.
        """
        # Create correspondent for tenant A
        self._set_tenant_context(self.tenant_a)
        correspondent_a = Correspondent.objects.create(
            name="Correspondent A",
            owner=self.user_a,
            tenant_id=self.tenant_a.id,
        )

        # Create correspondent for tenant B
        self._set_tenant_context(self.tenant_b)
        correspondent_b = Correspondent.objects.create(
            name="Correspondent B",
            owner=self.user_b,
            tenant_id=self.tenant_b.id,
        )

        # Query as tenant A - should only see tenant A's correspondent
        self._set_tenant_context(self.tenant_a)
        results_a = list(Correspondent.objects.all())
        self.assertEqual(len(results_a), 1)
        self.assertEqual(results_a[0].id, correspondent_a.id)
        self.assertEqual(results_a[0].name, "Correspondent A")

        # Query as tenant B - should only see tenant B's correspondent
        self._set_tenant_context(self.tenant_b)
        results_b = list(Correspondent.objects.all())
        self.assertEqual(len(results_b), 1)
        self.assertEqual(results_b[0].id, correspondent_b.id)
        self.assertEqual(results_b[0].name, "Correspondent B")

    def test_tag_tenant_isolation(self):
        """
        Test that Tag objects are isolated by tenant.
        """
        # Create tag for tenant A
        self._set_tenant_context(self.tenant_a)
        tag_a = Tag.objects.create(
            name="Tag A",
            owner=self.user_a,
            tenant_id=self.tenant_a.id,
        )

        # Create tag for tenant B
        self._set_tenant_context(self.tenant_b)
        tag_b = Tag.objects.create(
            name="Tag B",
            owner=self.user_b,
            tenant_id=self.tenant_b.id,
        )

        # Query as tenant A
        self._set_tenant_context(self.tenant_a)
        results_a = list(Tag.objects.all())
        self.assertEqual(len(results_a), 1)
        self.assertEqual(results_a[0].id, tag_a.id)

        # Query as tenant B
        self._set_tenant_context(self.tenant_b)
        results_b = list(Tag.objects.all())
        self.assertEqual(len(results_b), 1)
        self.assertEqual(results_b[0].id, tag_b.id)

    def test_document_type_tenant_isolation(self):
        """
        Test that DocumentType objects are isolated by tenant.
        """
        # Create document type for tenant A
        self._set_tenant_context(self.tenant_a)
        doctype_a = DocumentType.objects.create(
            name="Type A",
            owner=self.user_a,
            tenant_id=self.tenant_a.id,
        )

        # Create document type for tenant B
        self._set_tenant_context(self.tenant_b)
        doctype_b = DocumentType.objects.create(
            name="Type B",
            owner=self.user_b,
            tenant_id=self.tenant_b.id,
        )

        # Query as tenant A
        self._set_tenant_context(self.tenant_a)
        results_a = list(DocumentType.objects.all())
        self.assertEqual(len(results_a), 1)
        self.assertEqual(results_a[0].id, doctype_a.id)

        # Query as tenant B
        self._set_tenant_context(self.tenant_b)
        results_b = list(DocumentType.objects.all())
        self.assertEqual(len(results_b), 1)
        self.assertEqual(results_b[0].id, doctype_b.id)

    def test_storage_path_tenant_isolation(self):
        """
        Test that StoragePath objects are isolated by tenant.
        """
        # Create storage path for tenant A
        self._set_tenant_context(self.tenant_a)
        path_a = StoragePath.objects.create(
            name="Path A",
            path="path/a",
            owner=self.user_a,
            tenant_id=self.tenant_a.id,
        )

        # Create storage path for tenant B
        self._set_tenant_context(self.tenant_b)
        path_b = StoragePath.objects.create(
            name="Path B",
            path="path/b",
            owner=self.user_b,
            tenant_id=self.tenant_b.id,
        )

        # Query as tenant A
        self._set_tenant_context(self.tenant_a)
        results_a = list(StoragePath.objects.all())
        self.assertEqual(len(results_a), 1)
        self.assertEqual(results_a[0].id, path_a.id)

        # Query as tenant B
        self._set_tenant_context(self.tenant_b)
        results_b = list(StoragePath.objects.all())
        self.assertEqual(len(results_b), 1)
        self.assertEqual(results_b[0].id, path_b.id)

    def test_cross_tenant_access_blocked(self):
        """
        Test that cross-tenant access is blocked at the database level.
        """
        # Create correspondent for tenant A
        self._set_tenant_context(self.tenant_a)
        correspondent_a = Correspondent.objects.create(
            name="Correspondent A",
            owner=self.user_a,
            tenant_id=self.tenant_a.id,
        )
        correspondent_a_id = correspondent_a.id

        # Switch to tenant B context
        self._set_tenant_context(self.tenant_b)

        # Try to query tenant A's correspondent by ID
        # Should return empty queryset due to RLS
        try:
            result = Correspondent.objects.get(id=correspondent_a_id)
            self.fail("Should not be able to access tenant A's data from tenant B context")
        except Correspondent.DoesNotExist:
            # Expected - RLS blocks access
            pass

        # Verify that filter also returns no results
        results = Correspondent.objects.filter(id=correspondent_a_id)
        self.assertEqual(len(results), 0, "RLS should block cross-tenant access")

    def test_direct_sql_respects_rls(self):
        """
        Test that direct SQL queries respect RLS policies.
        """
        # Create correspondent for tenant A
        self._set_tenant_context(self.tenant_a)
        correspondent_a = Correspondent.objects.create(
            name="Correspondent A",
            owner=self.user_a,
            tenant_id=self.tenant_a.id,
        )

        # Create correspondent for tenant B
        self._set_tenant_context(self.tenant_b)
        correspondent_b = Correspondent.objects.create(
            name="Correspondent B",
            owner=self.user_b,
            tenant_id=self.tenant_b.id,
        )

        # Set context to tenant A
        self._set_tenant_context(self.tenant_a)

        # Execute direct SQL query
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM documents_correspondent")
            count = cursor.fetchone()[0]

        # Should only see tenant A's correspondent
        self.assertEqual(count, 1, "Direct SQL should respect RLS policies")

        # Switch to tenant B
        self._set_tenant_context(self.tenant_b)

        # Execute direct SQL query
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM documents_correspondent")
            count = cursor.fetchone()[0]

        # Should only see tenant B's correspondent
        self.assertEqual(count, 1, "Direct SQL should respect RLS policies")

    def test_rls_with_multiple_objects(self):
        """
        Test RLS with multiple objects per tenant.
        """
        # Create multiple correspondents for tenant A
        self._set_tenant_context(self.tenant_a)
        for i in range(5):
            Correspondent.objects.create(
                name=f"Correspondent A{i}",
                owner=self.user_a,
                tenant_id=self.tenant_a.id,
            )

        # Create multiple correspondents for tenant B
        self._set_tenant_context(self.tenant_b)
        for i in range(3):
            Correspondent.objects.create(
                name=f"Correspondent B{i}",
                owner=self.user_b,
                tenant_id=self.tenant_b.id,
            )

        # Query as tenant A - should see 5 correspondents
        self._set_tenant_context(self.tenant_a)
        count_a = Correspondent.objects.count()
        self.assertEqual(count_a, 5)

        # Query as tenant B - should see 3 correspondents
        self._set_tenant_context(self.tenant_b)
        count_b = Correspondent.objects.count()
        self.assertEqual(count_b, 3)
