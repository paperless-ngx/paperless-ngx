from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from paperless_migration import settings


@login_required
@require_http_methods(["GET", "POST"])
def migration_home(request):
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
