import logging
import threading

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import HttpResponse

from paperless import version

logger = logging.getLogger("paperless.middleware")

# Thread-local storage for tenant context
_thread_locals = threading.local()


def get_current_tenant():
    """
    Get the current tenant from thread-local storage.
    """
    return getattr(_thread_locals, "tenant", None)


def get_current_tenant_id():
    """
    Get the current tenant ID from thread-local storage.
    """
    return getattr(_thread_locals, "tenant_id", None)


def set_current_tenant(tenant):
    """
    Set the current tenant in thread-local storage.
    """
    _thread_locals.tenant = tenant
    _thread_locals.tenant_id = tenant.id if tenant else None


class TenantMiddleware:
    """
    Middleware to resolve and enforce tenant isolation based on subdomain routing.

    Resolves tenant from:
    1. Subdomain (primary): Extract from request.get_host()
    2. X-Tenant-ID header (fallback): For ingress routing

    Sets:
    - request.tenant: The resolved Tenant object
    - request.tenant_id: The tenant's ID
    - Thread-local storage for ORM filtering
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = None
        subdomain = None

        # Option 1: Extract subdomain from host
        host = request.get_host()
        logger.debug(f"Processing request for host: {host}")

        # Extract subdomain (e.g., "tenant-a.localhost:8000" -> "tenant-a")
        if "." in host:
            # Remove port if present
            host_without_port = host.split(":")[0]

            # Skip subdomain extraction if this is an IP address
            parts = host_without_port.split(".")
            is_ip = all(part.isdigit() and 0 <= int(part) <= 255 for part in parts if part)

            if not is_ip and len(parts) >= 2:
                # Get the subdomain (first part)
                subdomain = parts[0]
                logger.debug(f"Extracted subdomain: {subdomain}")

        # Option 2: Fallback to X-Tenant-ID header
        tenant_id_header = request.META.get("HTTP_X_TENANT_ID")

        # Try to resolve tenant
        if subdomain:
            try:
                from documents.models import Tenant
                tenant = Tenant.objects.get(subdomain=subdomain)
                logger.info(f"Resolved tenant from subdomain '{subdomain}': {tenant.name} (ID: {tenant.id})")
            except Tenant.DoesNotExist:
                logger.warning(f"Tenant not found for subdomain: {subdomain}")
                return HttpResponse("Tenant not found", status=403)
            except Exception as e:
                logger.error(f"Error resolving tenant from subdomain '{subdomain}': {e}")
                return HttpResponse("Internal server error", status=500)

        elif tenant_id_header:
            try:
                from documents.models import Tenant
                tenant = Tenant.objects.get(id=tenant_id_header)
                logger.info(f"Resolved tenant from X-Tenant-ID header: {tenant.name} (ID: {tenant.id})")
            except Tenant.DoesNotExist:
                logger.warning(f"Tenant not found for ID: {tenant_id_header}")
                return HttpResponse("Tenant not found", status=403)
            except Exception as e:
                logger.error(f"Error resolving tenant from X-Tenant-ID header '{tenant_id_header}': {e}")
                return HttpResponse("Internal server error", status=500)

        # If no tenant resolved and we have subdomain/header, return 403
        # (Allow requests without subdomain for non-tenant endpoints like admin)
        if not tenant and (subdomain or tenant_id_header):
            logger.warning("No tenant resolved but subdomain/header present")
            return HttpResponse("Forbidden - Invalid tenant", status=403)

        # Check if tenant is active
        if tenant and not tenant.is_active:
            logger.warning(f"Attempted access to inactive tenant: {tenant.name} (ID: {tenant.id})")
            return HttpResponse("Tenant is inactive", status=403)

        # Set tenant on request
        request.tenant = tenant
        request.tenant_id = tenant.id if tenant else None

        # Set thread-local storage for ORM filtering
        set_current_tenant(tenant)

        # Set PostgreSQL session variable for Row-Level Security
        if tenant:
            with connection.cursor() as cursor:
                cursor.execute("SET app.current_tenant = %s", [str(tenant.id)])
            logger.debug(f"Request processed for tenant: {tenant.name} (ID: {tenant.id})")
        else:
            # Clear the session variable if no tenant
            with connection.cursor() as cursor:
                cursor.execute("SET app.current_tenant = ''")

        # Continue processing request
        response = self.get_response(request)

        # Clean up thread-local storage after request
        set_current_tenant(None)

        return response


class ApiVersionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            versions = settings.REST_FRAMEWORK["ALLOWED_VERSIONS"]
            response["X-Api-Version"] = versions[len(versions) - 1]
            response["X-Version"] = version.__full_version_str__

        return response
