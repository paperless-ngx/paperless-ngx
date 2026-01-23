from pathlib import Path

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from paperless_migration import settings


@login_required
@require_http_methods(["GET", "POST"])
def migration_home(request):
    if not request.session.get("migration_code_ok"):
        return HttpResponseForbidden("Access code required")
    if not request.user.is_superuser:
        return HttpResponseForbidden("Superuser access required")

    export_path = Path(settings.MIGRATION_EXPORT_PATH)
    transformed_path = Path(settings.MIGRATION_TRANSFORMED_PATH)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "check":
            messages.success(request, "Checked export paths.")
        elif action == "transform":
            messages.info(
                request,
                "Transform step is not implemented yet.",
            )
        elif action == "import":
            messages.info(
                request,
                "Import step is not implemented yet.",
            )
        else:
            messages.error(request, "Unknown action.")
        return redirect("migration_home")

    context = {
        "export_path": export_path,
        "export_exists": export_path.exists(),
        "transformed_path": transformed_path,
        "transformed_exists": transformed_path.exists(),
    }
    return render(request, "paperless_migration/migration_home.html", context)


@require_http_methods(["GET", "POST"])
def migration_login(request):
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
