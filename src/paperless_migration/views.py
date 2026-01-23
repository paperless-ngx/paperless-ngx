import subprocess
import sys
from pathlib import Path

from django.contrib import messages
from django.contrib.auth import authenticate
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.http import StreamingHttpResponse
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
            messages.info(request, "Starting transform… live output below.")
            request.session["start_transform_stream"] = True
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
        "start_stream": request.session.pop("start_transform_stream", False),
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


@login_required
@require_http_methods(["GET"])
def transform_stream(request):
    if not request.session.get("migration_code_ok"):
        return HttpResponseForbidden("Access code required")
    if not request.user.is_superuser:
        return HttpResponseForbidden("Superuser access required")

    input_path = Path(settings.MIGRATION_EXPORT_PATH)
    output_path = Path(settings.MIGRATION_TRANSFORMED_PATH)

    cmd = [
        sys.executable,
        "-m",
        "paperless_migration.scripts.transform",
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]

    def event_stream():
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
        )
        try:
            yield "data: Starting transform...\n\n"
            if process.stdout:
                for line in process.stdout:
                    yield f"data: {line.rstrip()}\n\n"
            process.wait()
            yield f"data: Transform finished with code {process.returncode}\n\n"
        finally:
            if process and process.poll() is None:
                process.kill()

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
