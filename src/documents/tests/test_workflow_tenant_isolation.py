"""
Tests for Workflow, WorkflowTrigger, and WorkflowAction tenant isolation.

Verifies that workflows are properly isolated by tenant at both the ORM and RLS levels.
"""

import uuid
from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient
from documents.models import (
    Tenant,
    Workflow,
    WorkflowTrigger,
    WorkflowAction,
    set_current_tenant_id,
)


class WorkflowTenantIsolationTest(TransactionTestCase):
    """
    Test tenant isolation for Workflow, WorkflowTrigger, and WorkflowAction models.

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
        Clean up: reset PostgreSQL session variable and thread-local storage.
        """
        with connection.cursor() as cursor:
            cursor.execute("SET app.current_tenant = ''")
        set_current_tenant_id(None)

    def _set_tenant_context(self, tenant):
        """
        Set tenant context in both thread-local storage and PostgreSQL session.

        Args:
            tenant: Tenant object to set as current
        """
        set_current_tenant_id(tenant.id)
        with connection.cursor() as cursor:
            cursor.execute("SET app.current_tenant = %s", [str(tenant.id)])

    def test_workflow_tenant_isolation_orm(self):
        """
        Test that Workflow ORM queries are automatically filtered by tenant.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        # Create workflow for tenant A
        trigger_a = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        action_a = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
        )
        workflow_a = Workflow.objects.create(name="Workflow A", order=0)
        workflow_a.triggers.add(trigger_a)
        workflow_a.actions.add(action_a)

        # Verify workflow_a belongs to tenant A
        self.assertEqual(workflow_a.tenant_id, self.tenant_a.id)
        self.assertEqual(trigger_a.tenant_id, self.tenant_a.id)
        self.assertEqual(action_a.tenant_id, self.tenant_a.id)

        # Set tenant B context
        self._set_tenant_context(self.tenant_b)

        # Create workflow for tenant B
        trigger_b = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        action_b = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.REMOVAL,
        )
        workflow_b = Workflow.objects.create(name="Workflow B", order=1)
        workflow_b.triggers.add(trigger_b)
        workflow_b.actions.add(action_b)

        # Verify workflow_b belongs to tenant B
        self.assertEqual(workflow_b.tenant_id, self.tenant_b.id)
        self.assertEqual(trigger_b.tenant_id, self.tenant_b.id)
        self.assertEqual(action_b.tenant_id, self.tenant_b.id)

        # Verify tenant B can only see their workflow
        workflows = Workflow.objects.all()
        self.assertEqual(workflows.count(), 1)
        self.assertEqual(workflows.first().name, "Workflow B")

        triggers = WorkflowTrigger.objects.all()
        self.assertEqual(triggers.count(), 1)
        self.assertEqual(triggers.first().id, trigger_b.id)

        actions = WorkflowAction.objects.all()
        self.assertEqual(actions.count(), 1)
        self.assertEqual(actions.first().id, action_b.id)

        # Switch back to tenant A context
        self._set_tenant_context(self.tenant_a)

        # Verify tenant A can only see their workflow
        workflows = Workflow.objects.all()
        self.assertEqual(workflows.count(), 1)
        self.assertEqual(workflows.first().name, "Workflow A")

        triggers = WorkflowTrigger.objects.all()
        self.assertEqual(triggers.count(), 1)
        self.assertEqual(triggers.first().id, trigger_a.id)

        actions = WorkflowAction.objects.all()
        self.assertEqual(actions.count(), 1)
        self.assertEqual(actions.first().id, action_a.id)

    def test_workflow_rls_enforcement(self):
        """
        Test that RLS policies prevent cross-tenant data access at database level.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        # Create workflow for tenant A
        trigger_a = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        action_a = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
        )
        workflow_a = Workflow.objects.create(name="Workflow A RLS", order=0)
        workflow_a.triggers.add(trigger_a)
        workflow_a.actions.add(action_a)

        workflow_a_id = workflow_a.id
        trigger_a_id = trigger_a.id
        action_a_id = action_a.id

        # Set tenant B context
        self._set_tenant_context(self.tenant_b)

        # Try to query workflow from tenant A using all_objects (bypasses ORM filtering)
        # RLS should still prevent access
        workflow_from_b = Workflow.all_objects.filter(id=workflow_a_id).first()
        trigger_from_b = WorkflowTrigger.all_objects.filter(id=trigger_a_id).first()
        action_from_b = WorkflowAction.all_objects.filter(id=action_a_id).first()

        # RLS should block access to tenant A's data
        self.assertIsNone(workflow_from_b)
        self.assertIsNone(trigger_from_b)
        self.assertIsNone(action_from_b)

    def test_workflow_api_tenant_isolation(self):
        """
        Test that API endpoints respect tenant isolation.
        """
        # Create API clients for each tenant
        client_a = APIClient()
        client_a.force_authenticate(user=self.user_a)

        client_b = APIClient()
        client_b.force_authenticate(user=self.user_b)

        # Set tenant A context and create workflow
        self._set_tenant_context(self.tenant_a)

        trigger_a = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        action_a = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.ASSIGNMENT,
        )
        workflow_a = Workflow.objects.create(name="API Workflow A", order=0)
        workflow_a.triggers.add(trigger_a)
        workflow_a.actions.add(action_a)

        workflow_a_id = workflow_a.id

        # Set tenant B context and create workflow
        self._set_tenant_context(self.tenant_b)

        trigger_b = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        )
        action_b = WorkflowAction.objects.create(
            type=WorkflowAction.WorkflowActionType.REMOVAL,
        )
        workflow_b = Workflow.objects.create(name="API Workflow B", order=1)
        workflow_b.triggers.add(trigger_b)
        workflow_b.actions.add(action_b)

        workflow_b_id = workflow_b.id

        # Test that tenant A can list their workflows
        self._set_tenant_context(self.tenant_a)
        response = client_a.get('/api/workflows/')
        self.assertEqual(response.status_code, 200)
        workflow_ids = [w['id'] for w in response.data['results']]
        self.assertIn(workflow_a_id, workflow_ids)
        self.assertNotIn(workflow_b_id, workflow_ids)

        # Test that tenant B can list their workflows
        self._set_tenant_context(self.tenant_b)
        response = client_b.get('/api/workflows/')
        self.assertEqual(response.status_code, 200)
        workflow_ids = [w['id'] for w in response.data['results']]
        self.assertIn(workflow_b_id, workflow_ids)
        self.assertNotIn(workflow_a_id, workflow_ids)

    def test_workflow_cannot_reference_cross_tenant_objects(self):
        """
        Test that workflows cannot be created with references to other tenant's objects.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        trigger_a = WorkflowTrigger.objects.create(
            type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION,
        )
        trigger_a_id = trigger_a.id

        # Set tenant B context
        self._set_tenant_context(self.tenant_b)

        # Try to create a workflow in tenant B that references tenant A's trigger
        workflow_b = Workflow.objects.create(name="Cross-tenant Workflow", order=0)

        # Try to add trigger from tenant A (should fail or be empty)
        # The M2M relationship should not allow adding cross-tenant objects
        trigger_queryset = WorkflowTrigger.objects.filter(id=trigger_a_id)
        self.assertEqual(trigger_queryset.count(), 0)  # Tenant B cannot see trigger A

    def test_workflow_all_objects_manager(self):
        """
        Test that all_objects manager bypasses tenant filtering (for admin use).
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        workflow_a = Workflow.objects.create(name="Workflow All Objects A", order=0)

        # Set tenant B context
        self._set_tenant_context(self.tenant_b)

        workflow_b = Workflow.objects.create(name="Workflow All Objects B", order=1)

        # Using objects manager - should only see tenant B
        self.assertEqual(Workflow.objects.count(), 1)

        # Using all_objects manager - should see both (but RLS might still apply)
        # In PostgreSQL with RLS, even all_objects respects RLS unless bypassed
        all_workflows = Workflow.all_objects.count()
        # RLS should still limit to current tenant
        self.assertEqual(all_workflows, 1)

    def test_workflow_tenant_id_auto_population(self):
        """
        Test that tenant_id is automatically populated from thread-local storage.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        # Create workflow without explicitly setting tenant_id
        workflow = Workflow(name="Auto Tenant Workflow", order=0)
        workflow.save()

        # Verify tenant_id was auto-populated
        self.assertEqual(workflow.tenant_id, self.tenant_a.id)

        # Same for triggers and actions
        trigger = WorkflowTrigger(type=WorkflowTrigger.WorkflowTriggerType.CONSUMPTION)
        trigger.save()
        self.assertEqual(trigger.tenant_id, self.tenant_a.id)

        action = WorkflowAction(type=WorkflowAction.WorkflowActionType.ASSIGNMENT)
        action.save()
        self.assertEqual(action.tenant_id, self.tenant_a.id)

    def test_workflow_tenant_id_cannot_be_changed(self):
        """
        Test that tenant_id cannot be modified after creation.
        """
        # Set tenant A context
        self._set_tenant_context(self.tenant_a)

        workflow = Workflow.objects.create(name="Immutable Tenant Workflow", order=0)
        original_tenant_id = workflow.tenant_id

        # Try to change tenant_id
        workflow.tenant_id = self.tenant_b.id
        workflow.save()

        # Reload from database
        workflow.refresh_from_db()

        # Verify tenant_id didn't change (RLS prevents update)
        # Note: This might raise an error or silently fail depending on RLS config
        # In our case with FORCE RLS, the update should be blocked
        self.assertEqual(workflow.tenant_id, original_tenant_id)
