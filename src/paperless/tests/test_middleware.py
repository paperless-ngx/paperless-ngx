from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from rest_framework import status

from paperless.middleware import TenantMiddleware, get_current_tenant, set_current_tenant
from documents.models import Tenant


class TestTenantMiddleware(TestCase):
    """
    Tests for TenantMiddleware subdomain-based tenant resolution.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

        # Create test tenants
        self.tenant_a = Tenant.objects.create(
            name="Tenant A",
            subdomain="tenant-a",
            is_active=True,
        )
        self.tenant_b = Tenant.objects.create(
            name="Tenant B",
            subdomain="tenant-b",
            is_active=True,
        )
        self.inactive_tenant = Tenant.objects.create(
            name="Inactive Tenant",
            subdomain="inactive",
            is_active=False,
        )

        # Create a mock get_response callable
        self.get_response = lambda request: None

        # Instantiate middleware
        self.middleware = TenantMiddleware(self.get_response)

    def tearDown(self):
        """Clean up thread-local storage."""
        set_current_tenant(None)

    def test_resolve_tenant_from_subdomain(self):
        """
        Test that tenant is resolved from subdomain.

        GIVEN: A request with a subdomain
        WHEN: Middleware processes the request
        THEN: Tenant is resolved and set on request
        """
        request = self.factory.get("/", HTTP_HOST="tenant-a.localhost:8000")

        # Mock get_response to return a simple response
        self.middleware.get_response = lambda req: type('obj', (object,), {'status_code': 200})()

        response = self.middleware(request)

        # Verify tenant was resolved
        self.assertIsNotNone(request.tenant)
        self.assertEqual(request.tenant.subdomain, "tenant-a")
        self.assertEqual(request.tenant_id, self.tenant_a.id)
        self.assertEqual(response.status_code, 200)

    def test_resolve_tenant_without_port(self):
        """
        Test that tenant is resolved from subdomain without port.

        GIVEN: A request with a subdomain but no port
        WHEN: Middleware processes the request
        THEN: Tenant is resolved correctly
        """
        request = self.factory.get("/", HTTP_HOST="tenant-b.localhost")

        # Mock get_response to return a simple response
        self.middleware.get_response = lambda req: type('obj', (object,), {'status_code': 200})()

        response = self.middleware(request)

        # Verify tenant was resolved
        self.assertIsNotNone(request.tenant)
        self.assertEqual(request.tenant.subdomain, "tenant-b")
        self.assertEqual(request.tenant_id, self.tenant_b.id)

    def test_invalid_subdomain_returns_403(self):
        """
        Test that invalid subdomain returns 403.

        GIVEN: A request with an invalid subdomain
        WHEN: Middleware processes the request
        THEN: 403 response is returned
        """
        request = self.factory.get("/", HTTP_HOST="invalid.localhost:8000")

        response = self.middleware(request)

        # Verify 403 response
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Tenant not found", response.content)

    def test_inactive_tenant_returns_403(self):
        """
        Test that inactive tenant returns 403.

        GIVEN: A request for an inactive tenant
        WHEN: Middleware processes the request
        THEN: 403 response is returned
        """
        request = self.factory.get("/", HTTP_HOST="inactive.localhost:8000")

        response = self.middleware(request)

        # Verify 403 response
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Tenant is inactive", response.content)

    def test_resolve_tenant_from_header(self):
        """
        Test that tenant is resolved from X-Tenant-ID header.

        GIVEN: A request with X-Tenant-ID header
        WHEN: Middleware processes the request
        THEN: Tenant is resolved from header
        """
        request = self.factory.get(
            "/",
            HTTP_HOST="localhost:8000",
            HTTP_X_TENANT_ID=str(self.tenant_a.id),
        )

        # Mock get_response to return a simple response
        self.middleware.get_response = lambda req: type('obj', (object,), {'status_code': 200})()

        response = self.middleware(request)

        # Verify tenant was resolved
        self.assertIsNotNone(request.tenant)
        self.assertEqual(request.tenant.id, self.tenant_a.id)
        self.assertEqual(request.tenant_id, self.tenant_a.id)

    def test_invalid_header_tenant_id_returns_403(self):
        """
        Test that invalid X-Tenant-ID header returns 403.

        GIVEN: A request with an invalid X-Tenant-ID header
        WHEN: Middleware processes the request
        THEN: 403 response is returned
        """
        request = self.factory.get(
            "/",
            HTTP_HOST="localhost:8000",
            HTTP_X_TENANT_ID="99999",
        )

        response = self.middleware(request)

        # Verify 403 response
        self.assertEqual(response.status_code, 403)
        self.assertIn(b"Tenant not found", response.content)

    def test_no_subdomain_or_header_allows_request(self):
        """
        Test that requests without subdomain or header are allowed.

        GIVEN: A request without subdomain or X-Tenant-ID header
        WHEN: Middleware processes the request
        THEN: Request is allowed (no tenant set)
        """
        request = self.factory.get("/", HTTP_HOST="localhost:8000")

        # Mock get_response to return a simple response
        self.middleware.get_response = lambda req: type('obj', (object,), {'status_code': 200})()

        response = self.middleware(request)

        # Verify no tenant was set but request succeeded
        self.assertIsNone(request.tenant)
        self.assertIsNone(request.tenant_id)
        self.assertEqual(response.status_code, 200)

    def test_thread_local_storage(self):
        """
        Test that thread-local storage is set correctly.

        GIVEN: A request with a valid subdomain
        WHEN: Middleware processes the request
        THEN: Thread-local storage is set with tenant
        """
        request = self.factory.get("/", HTTP_HOST="tenant-a.localhost:8000")

        # Create a get_response that checks thread-local storage
        def check_thread_local(req):
            # Inside the request processing, thread-local should be set
            current_tenant = get_current_tenant()
            self.assertIsNotNone(current_tenant)
            self.assertEqual(current_tenant.subdomain, "tenant-a")
            return type('obj', (object,), {'status_code': 200})()

        self.middleware.get_response = check_thread_local

        response = self.middleware(request)

        # After request processing, thread-local should be cleaned up
        self.assertIsNone(get_current_tenant())

    def test_subdomain_priority_over_header(self):
        """
        Test that subdomain takes priority over X-Tenant-ID header.

        GIVEN: A request with both subdomain and X-Tenant-ID header
        WHEN: Middleware processes the request
        THEN: Subdomain is used to resolve tenant
        """
        request = self.factory.get(
            "/",
            HTTP_HOST="tenant-a.localhost:8000",
            HTTP_X_TENANT_ID=str(self.tenant_b.id),
        )

        # Mock get_response to return a simple response
        self.middleware.get_response = lambda req: type('obj', (object,), {'status_code': 200})()

        response = self.middleware(request)

        # Verify tenant was resolved from subdomain, not header
        self.assertIsNotNone(request.tenant)
        self.assertEqual(request.tenant.subdomain, "tenant-a")
        self.assertEqual(request.tenant_id, self.tenant_a.id)
