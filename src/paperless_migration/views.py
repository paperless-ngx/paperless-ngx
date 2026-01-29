"""Views for migration mode web interface."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

if TYPE_CHECKING:
    from django.http import HttpRequest
    from django.http import HttpResponse


def _check_migration_access(request: HttpRequest) -> HttpResponse | None:
    """Check if user has migration access. Returns error response or None."""
    if not request.session.get("migration_code_ok"):
        return HttpResponseForbidden("Access code required")
    if not request.user.is_superuser:
        return HttpResponseForbidden("Superuser access required")
    return None


@login_required
@require_http_methods(["GET", "POST"])
def migration_home(request: HttpRequest) -> HttpResponse:
    """Main migration dashboard view."""
    error_response = _check_migration_access(request)
    if error_response:
        return error_response

    export_path = Path(settings.MIGRATION_EXPORT_PATH)
    transformed_path = Path(settings.MIGRATION_TRANSFORMED_PATH)
    imported_marker = Path(settings.MIGRATION_IMPORTED_PATH)

    if request.method == "POST":
        action = request.POST.get("action")

        if action == "check":
            messages.success(request, "Checked export paths.")

        elif action == "upload":
            upload = request.FILES.get("export_file")
            if not upload:
                messages.error(request, "No file selected.")
            else:
                try:
                    export_path.parent.mkdir(parents=True, exist_ok=True)
                    with export_path.open("wb") as dest:
                        for chunk in upload.chunks():
                            dest.write(chunk)
                    messages.success(request, f"Uploaded to {export_path}.")
                except Exception as exc:
                    messages.error(request, f"Failed to save file: {exc}")

        elif action == "transform":
            if imported_marker.exists():
                imported_marker.unlink()
            # Signal to start WebSocket connection for transform
            request.session["start_ws_action"] = "transform"
            messages.info(request, "Starting transform via WebSocket...")

        elif action == "import":
            # Signal to start WebSocket connection for import
            request.session["start_ws_action"] = "import"
            messages.info(request, "Starting import via WebSocket...")

        elif action == "reset_transform":
            if transformed_path.exists():
                try:
                    transformed_path.unlink()
                    messages.success(request, "Transformed file deleted.")
                except Exception as exc:
                    messages.error(request, f"Failed to delete transformed file: {exc}")
            if imported_marker.exists():
                try:
                    imported_marker.unlink()
                except Exception:
                    pass

        else:
            messages.error(request, "Unknown action.")

        return redirect("migration_home")

    ws_action = request.session.pop("start_ws_action", None)

    context = {
        "export_path": export_path,
        "export_exists": export_path.exists(),
        "transformed_path": transformed_path,
        "transformed_exists": transformed_path.exists(),
        "imported_exists": imported_marker.exists(),
        "ws_action": ws_action,
    }
    return render(request, "paperless_migration/migration_home.html", context)


@require_http_methods(["GET", "POST"])
def migration_login(request: HttpRequest) -> HttpResponse:
    """Migration-specific login view requiring access code."""
    if request.method == "POST":
        username = request.POST.get("login", "")
        password = request.POST.get("password", "")
        code = request.POST.get("code", "")

        if not code or code != settings.MIGRATION_ACCESS_CODE:
            messages.error(request, "One-time code is required.")
            return redirect("account_login")

        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, "Invalid username or password.")
            return redirect("account_login")

        if not user.is_superuser:
            messages.error(request, "Superuser access required.")
            return redirect("account_login")

        login(request, user)
        request.session["migration_code_ok"] = True
        return redirect(settings.LOGIN_REDIRECT_URL)

    return render(request, "account/login.html")
