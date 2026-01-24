import os
import shutil
import subprocess
import sys
import tempfile
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
    imported_marker = Path(settings.MIGRATION_IMPORTED_PATH)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "check":
            messages.success(request, "Checked export paths.")
        elif action == "transform":
            messages.info(request, "Starting transform… live output below.")
            request.session["start_stream_action"] = "transform"
            if imported_marker.exists():
                imported_marker.unlink()
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
            messages.info(request, "Starting import… live output below.")
            request.session["start_stream_action"] = "import"
        else:
            messages.error(request, "Unknown action.")
        return redirect("migration_home")

    stream_action = request.session.pop("start_stream_action", None)
    context = {
        "export_path": export_path,
        "export_exists": export_path.exists(),
        "transformed_path": transformed_path,
        "transformed_exists": transformed_path.exists(),
        "imported_exists": imported_marker.exists(),
        "stream_action": stream_action,
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


@login_required
@require_http_methods(["GET"])
def import_stream(request):
    if not request.session.get("migration_code_ok"):
        return HttpResponseForbidden("Access code required")
    if not request.user.is_superuser:
        return HttpResponseForbidden("Superuser access required")

    export_path = Path(settings.MIGRATION_EXPORT_PATH)
    transformed_path = Path(settings.MIGRATION_TRANSFORMED_PATH)
    imported_marker = Path(settings.MIGRATION_IMPORTED_PATH)
    manage_path = Path(settings.BASE_DIR) / "manage.py"
    source_dir = export_path.parent

    cmd = [
        sys.executable,
        str(manage_path),
        "document_importer",
        str(source_dir),
        "--data-only",
    ]

    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = "paperless.settings"
    env["PAPERLESS_MIGRATION_MODE"] = "0"

    def event_stream():
        if not export_path.exists():
            yield "data: Missing export manifest.json; upload or re-check export.\n\n"
            return
        if not transformed_path.exists():
            yield "data: Missing transformed manifest.v3.json; run transform first.\n\n"
            return

        backup_path: Path | None = None
        try:
            backup_fd, backup_name = tempfile.mkstemp(
                prefix="manifest.v2.",
                suffix=".json",
                dir=source_dir,
            )
            os.close(backup_fd)
            backup_path = Path(backup_name)
            shutil.copy2(export_path, backup_path)
            shutil.copy2(transformed_path, export_path)
        except Exception as exc:
            yield f"data: Failed to prepare import manifest: {exc}\n\n"
            return

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env=env,
        )
        try:
            yield "data: Starting import...\n\n"
            if process.stdout:
                for line in process.stdout:
                    yield f"data: {line.rstrip()}\n\n"
            process.wait()
            if process.returncode == 0:
                imported_marker.parent.mkdir(parents=True, exist_ok=True)
                imported_marker.write_text("ok\n", encoding="utf-8")
            yield f"data: Import finished with code {process.returncode}\n\n"
        finally:
            if process and process.poll() is None:
                process.kill()
            if backup_path and backup_path.exists():
                try:
                    shutil.move(backup_path, export_path)
                except Exception:
                    pass

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
