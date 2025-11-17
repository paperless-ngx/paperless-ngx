"""
Unit tests for AI-related permissions.

Tests cover:
- CanViewAISuggestionsPermission
- CanApplyAISuggestionsPermission
- CanApproveDeletionsPermission
- CanConfigureAIPermission
- Role-based access control
- Permission assignment and verification
"""

from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from documents.models import Document
from documents.permissions import CanApplyAISuggestionsPermission
from documents.permissions import CanApproveDeletionsPermission
from documents.permissions import CanConfigureAIPermission
from documents.permissions import CanViewAISuggestionsPermission


class MockView:
    """Mock view for testing permissions."""



class TestCanViewAISuggestionsPermission(TestCase):
    """Test the CanViewAISuggestionsPermission class."""

    def setUp(self):
        """Set up test users and permissions."""
        self.factory = APIRequestFactory()
        self.permission = CanViewAISuggestionsPermission()
        self.view = MockView()

        # Create users
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123",
        )
        self.regular_user = User.objects.create_user(
            username="regular", email="regular@test.com", password="regular123",
        )
        self.permitted_user = User.objects.create_user(
            username="permitted", email="permitted@test.com", password="permitted123",
        )

        # Assign permission to permitted_user
        content_type = ContentType.objects.get_for_model(Document)
        permission, created = Permission.objects.get_or_create(
            codename="can_view_ai_suggestions",
            name="Can view AI suggestions",
            content_type=content_type,
        )
        self.permitted_user.user_permissions.add(permission)

    def test_unauthenticated_user_denied(self):
        """Test that unauthenticated users are denied."""
        request = self.factory.get("/api/ai/suggestions/")
        request.user = None

        result = self.permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_superuser_allowed(self):
        """Test that superusers are always allowed."""
        request = self.factory.get("/api/ai/suggestions/")
        request.user = self.superuser

        result = self.permission.has_permission(request, self.view)

        self.assertTrue(result)

    def test_regular_user_without_permission_denied(self):
        """Test that regular users without permission are denied."""
        request = self.factory.get("/api/ai/suggestions/")
        request.user = self.regular_user

        result = self.permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_user_with_permission_allowed(self):
        """Test that users with permission are allowed."""
        request = self.factory.get("/api/ai/suggestions/")
        request.user = self.permitted_user

        result = self.permission.has_permission(request, self.view)

        self.assertTrue(result)


class TestCanApplyAISuggestionsPermission(TestCase):
    """Test the CanApplyAISuggestionsPermission class."""

    def setUp(self):
        """Set up test users and permissions."""
        self.factory = APIRequestFactory()
        self.permission = CanApplyAISuggestionsPermission()
        self.view = MockView()

        # Create users
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123",
        )
        self.regular_user = User.objects.create_user(
            username="regular", email="regular@test.com", password="regular123",
        )
        self.permitted_user = User.objects.create_user(
            username="permitted", email="permitted@test.com", password="permitted123",
        )

        # Assign permission to permitted_user
        content_type = ContentType.objects.get_for_model(Document)
        permission, created = Permission.objects.get_or_create(
            codename="can_apply_ai_suggestions",
            name="Can apply AI suggestions",
            content_type=content_type,
        )
        self.permitted_user.user_permissions.add(permission)

    def test_unauthenticated_user_denied(self):
        """Test that unauthenticated users are denied."""
        request = self.factory.post("/api/ai/suggestions/apply/")
        request.user = None

        result = self.permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_superuser_allowed(self):
        """Test that superusers are always allowed."""
        request = self.factory.post("/api/ai/suggestions/apply/")
        request.user = self.superuser

        result = self.permission.has_permission(request, self.view)

        self.assertTrue(result)

    def test_regular_user_without_permission_denied(self):
        """Test that regular users without permission are denied."""
        request = self.factory.post("/api/ai/suggestions/apply/")
        request.user = self.regular_user

        result = self.permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_user_with_permission_allowed(self):
        """Test that users with permission are allowed."""
        request = self.factory.post("/api/ai/suggestions/apply/")
        request.user = self.permitted_user

        result = self.permission.has_permission(request, self.view)

        self.assertTrue(result)


class TestCanApproveDeletionsPermission(TestCase):
    """Test the CanApproveDeletionsPermission class."""

    def setUp(self):
        """Set up test users and permissions."""
        self.factory = APIRequestFactory()
        self.permission = CanApproveDeletionsPermission()
        self.view = MockView()

        # Create users
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123",
        )
        self.regular_user = User.objects.create_user(
            username="regular", email="regular@test.com", password="regular123",
        )
        self.permitted_user = User.objects.create_user(
            username="permitted", email="permitted@test.com", password="permitted123",
        )

        # Assign permission to permitted_user
        content_type = ContentType.objects.get_for_model(Document)
        permission, created = Permission.objects.get_or_create(
            codename="can_approve_deletions",
            name="Can approve AI-recommended deletions",
            content_type=content_type,
        )
        self.permitted_user.user_permissions.add(permission)

    def test_unauthenticated_user_denied(self):
        """Test that unauthenticated users are denied."""
        request = self.factory.post("/api/ai/deletions/approve/")
        request.user = None

        result = self.permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_superuser_allowed(self):
        """Test that superusers are always allowed."""
        request = self.factory.post("/api/ai/deletions/approve/")
        request.user = self.superuser

        result = self.permission.has_permission(request, self.view)

        self.assertTrue(result)

    def test_regular_user_without_permission_denied(self):
        """Test that regular users without permission are denied."""
        request = self.factory.post("/api/ai/deletions/approve/")
        request.user = self.regular_user

        result = self.permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_user_with_permission_allowed(self):
        """Test that users with permission are allowed."""
        request = self.factory.post("/api/ai/deletions/approve/")
        request.user = self.permitted_user

        result = self.permission.has_permission(request, self.view)

        self.assertTrue(result)


class TestCanConfigureAIPermission(TestCase):
    """Test the CanConfigureAIPermission class."""

    def setUp(self):
        """Set up test users and permissions."""
        self.factory = APIRequestFactory()
        self.permission = CanConfigureAIPermission()
        self.view = MockView()

        # Create users
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123",
        )
        self.regular_user = User.objects.create_user(
            username="regular", email="regular@test.com", password="regular123",
        )
        self.permitted_user = User.objects.create_user(
            username="permitted", email="permitted@test.com", password="permitted123",
        )

        # Assign permission to permitted_user
        content_type = ContentType.objects.get_for_model(Document)
        permission, created = Permission.objects.get_or_create(
            codename="can_configure_ai",
            name="Can configure AI settings",
            content_type=content_type,
        )
        self.permitted_user.user_permissions.add(permission)

    def test_unauthenticated_user_denied(self):
        """Test that unauthenticated users are denied."""
        request = self.factory.post("/api/ai/config/")
        request.user = None

        result = self.permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_superuser_allowed(self):
        """Test that superusers are always allowed."""
        request = self.factory.post("/api/ai/config/")
        request.user = self.superuser

        result = self.permission.has_permission(request, self.view)

        self.assertTrue(result)

    def test_regular_user_without_permission_denied(self):
        """Test that regular users without permission are denied."""
        request = self.factory.post("/api/ai/config/")
        request.user = self.regular_user

        result = self.permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_user_with_permission_allowed(self):
        """Test that users with permission are allowed."""
        request = self.factory.post("/api/ai/config/")
        request.user = self.permitted_user

        result = self.permission.has_permission(request, self.view)

        self.assertTrue(result)


class TestRoleBasedAccessControl(TestCase):
    """Test role-based access control for AI permissions."""

    def setUp(self):
        """Set up test groups and permissions."""
        # Create groups
        self.viewer_group = Group.objects.create(name="AI Viewers")
        self.editor_group = Group.objects.create(name="AI Editors")
        self.admin_group = Group.objects.create(name="AI Administrators")

        # Get permissions
        content_type = ContentType.objects.get_for_model(Document)
        self.view_permission, _ = Permission.objects.get_or_create(
            codename="can_view_ai_suggestions",
            name="Can view AI suggestions",
            content_type=content_type,
        )
        self.apply_permission, _ = Permission.objects.get_or_create(
            codename="can_apply_ai_suggestions",
            name="Can apply AI suggestions",
            content_type=content_type,
        )
        self.approve_permission, _ = Permission.objects.get_or_create(
            codename="can_approve_deletions",
            name="Can approve AI-recommended deletions",
            content_type=content_type,
        )
        self.config_permission, _ = Permission.objects.get_or_create(
            codename="can_configure_ai",
            name="Can configure AI settings",
            content_type=content_type,
        )

        # Assign permissions to groups
        # Viewers can only view
        self.viewer_group.permissions.add(self.view_permission)

        # Editors can view and apply
        self.editor_group.permissions.add(self.view_permission, self.apply_permission)

        # Admins can do everything
        self.admin_group.permissions.add(
            self.view_permission,
            self.apply_permission,
            self.approve_permission,
            self.config_permission,
        )

    def test_viewer_role_permissions(self):
        """Test that viewer role has appropriate permissions."""
        user = User.objects.create_user(
            username="viewer", email="viewer@test.com", password="viewer123",
        )
        user.groups.add(self.viewer_group)

        # Refresh user to get updated permissions
        user = User.objects.get(pk=user.pk)

        self.assertTrue(user.has_perm("documents.can_view_ai_suggestions"))
        self.assertFalse(user.has_perm("documents.can_apply_ai_suggestions"))
        self.assertFalse(user.has_perm("documents.can_approve_deletions"))
        self.assertFalse(user.has_perm("documents.can_configure_ai"))

    def test_editor_role_permissions(self):
        """Test that editor role has appropriate permissions."""
        user = User.objects.create_user(
            username="editor", email="editor@test.com", password="editor123",
        )
        user.groups.add(self.editor_group)

        # Refresh user to get updated permissions
        user = User.objects.get(pk=user.pk)

        self.assertTrue(user.has_perm("documents.can_view_ai_suggestions"))
        self.assertTrue(user.has_perm("documents.can_apply_ai_suggestions"))
        self.assertFalse(user.has_perm("documents.can_approve_deletions"))
        self.assertFalse(user.has_perm("documents.can_configure_ai"))

    def test_admin_role_permissions(self):
        """Test that admin role has all permissions."""
        user = User.objects.create_user(
            username="ai_admin", email="ai_admin@test.com", password="admin123",
        )
        user.groups.add(self.admin_group)

        # Refresh user to get updated permissions
        user = User.objects.get(pk=user.pk)

        self.assertTrue(user.has_perm("documents.can_view_ai_suggestions"))
        self.assertTrue(user.has_perm("documents.can_apply_ai_suggestions"))
        self.assertTrue(user.has_perm("documents.can_approve_deletions"))
        self.assertTrue(user.has_perm("documents.can_configure_ai"))

    def test_user_with_multiple_groups(self):
        """Test that user permissions accumulate from multiple groups."""
        user = User.objects.create_user(
            username="multi_role", email="multi@test.com", password="multi123",
        )
        user.groups.add(self.viewer_group, self.editor_group)

        # Refresh user to get updated permissions
        user = User.objects.get(pk=user.pk)

        # Should have both viewer and editor permissions
        self.assertTrue(user.has_perm("documents.can_view_ai_suggestions"))
        self.assertTrue(user.has_perm("documents.can_apply_ai_suggestions"))
        self.assertFalse(user.has_perm("documents.can_approve_deletions"))

    def test_direct_permission_assignment_overrides_group(self):
        """Test that direct permission assignment works alongside group permissions."""
        user = User.objects.create_user(
            username="special", email="special@test.com", password="special123",
        )
        user.groups.add(self.viewer_group)

        # Directly assign approval permission
        user.user_permissions.add(self.approve_permission)

        # Refresh user to get updated permissions
        user = User.objects.get(pk=user.pk)

        # Should have viewer group permissions plus direct permission
        self.assertTrue(user.has_perm("documents.can_view_ai_suggestions"))
        self.assertFalse(user.has_perm("documents.can_apply_ai_suggestions"))
        self.assertTrue(user.has_perm("documents.can_approve_deletions"))
        self.assertFalse(user.has_perm("documents.can_configure_ai"))


class TestPermissionAssignment(TestCase):
    """Test permission assignment and revocation."""

    def setUp(self):
        """Set up test user."""
        self.user = User.objects.create_user(
            username="testuser", email="test@test.com", password="test123",
        )
        content_type = ContentType.objects.get_for_model(Document)
        self.view_permission, _ = Permission.objects.get_or_create(
            codename="can_view_ai_suggestions",
            name="Can view AI suggestions",
            content_type=content_type,
        )

    def test_assign_permission_to_user(self):
        """Test assigning permission to user."""
        self.assertFalse(self.user.has_perm("documents.can_view_ai_suggestions"))

        self.user.user_permissions.add(self.view_permission)
        self.user = User.objects.get(pk=self.user.pk)

        self.assertTrue(self.user.has_perm("documents.can_view_ai_suggestions"))

    def test_revoke_permission_from_user(self):
        """Test revoking permission from user."""
        self.user.user_permissions.add(self.view_permission)
        self.user = User.objects.get(pk=self.user.pk)
        self.assertTrue(self.user.has_perm("documents.can_view_ai_suggestions"))

        self.user.user_permissions.remove(self.view_permission)
        self.user = User.objects.get(pk=self.user.pk)

        self.assertFalse(self.user.has_perm("documents.can_view_ai_suggestions"))

    def test_permission_persistence(self):
        """Test that permissions persist across user retrieval."""
        self.user.user_permissions.add(self.view_permission)

        # Get user from database
        retrieved_user = User.objects.get(username="testuser")

        self.assertTrue(retrieved_user.has_perm("documents.can_view_ai_suggestions"))


class TestPermissionEdgeCases(TestCase):
    """Test edge cases and error conditions for permissions."""

    def setUp(self):
        """Set up test data."""
        self.factory = APIRequestFactory()
        self.view = MockView()

    def test_anonymous_user_request(self):
        """Test handling of anonymous user."""
        from django.contrib.auth.models import AnonymousUser

        permission = CanViewAISuggestionsPermission()
        request = self.factory.get("/api/ai/suggestions/")
        request.user = AnonymousUser()

        result = permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_missing_user_attribute(self):
        """Test handling of request without user attribute."""
        permission = CanViewAISuggestionsPermission()
        request = self.factory.get("/api/ai/suggestions/")
        # Don't set request.user

        result = permission.has_permission(request, self.view)

        self.assertFalse(result)

    def test_inactive_user_with_permission(self):
        """Test that inactive users are denied even with permission."""
        user = User.objects.create_user(
            username="inactive", email="inactive@test.com", password="inactive123",
        )
        user.is_active = False
        user.save()

        # Add permission
        content_type = ContentType.objects.get_for_model(Document)
        permission, _ = Permission.objects.get_or_create(
            codename="can_view_ai_suggestions",
            name="Can view AI suggestions",
            content_type=content_type,
        )
        user.user_permissions.add(permission)

        permission_check = CanViewAISuggestionsPermission()
        request = self.factory.get("/api/ai/suggestions/")
        request.user = user

        # Inactive users should not pass authentication check
        result = permission_check.has_permission(request, self.view)

        self.assertFalse(result)
