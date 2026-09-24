from pathlib import Path

import magic
from django.conf import settings
from django.http import FileResponse
from django.http import Http404
from django.http import HttpRequest
from django.utils.translation import get_language
from django.views.generic import TemplateView

from paperless.models import ApplicationConfiguration


class IndexView(TemplateView):
    template_name = "index.html"

    def get_frontend_language(self):
        if hasattr(
            self.request.user,
            "ui_settings",
        ) and self.request.user.ui_settings.settings.get("language"):
            lang = self.request.user.ui_settings.settings.get("language")
        else:
            lang = get_language()
        # This is here for the following reason:
        # Django identifies languages in the form "en-us"
        # However, angular generates locales as "en-US".
        # this translates between these two forms.
        if "-" in lang:
            first = lang[: lang.index("-")]
            second = lang[lang.index("-") + 1 :]
            return f"{first}-{second.upper()}"
        return lang

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cookie_prefix"] = settings.COOKIE_PREFIX
        context["username"] = self.request.user.username
        context["full_name"] = self.request.user.get_full_name()
        context["styles_css"] = f"frontend/{self.get_frontend_language()}/styles.css"
        context["polyfills_js"] = (
            f"frontend/{self.get_frontend_language()}/polyfills.js"
        )
        context["main_js"] = f"frontend/{self.get_frontend_language()}/main.js"
        context["webmanifest"] = (
            f"frontend/{self.get_frontend_language()}/manifest.webmanifest"
        )
        context["apple_touch_icon"] = (
            f"frontend/{self.get_frontend_language()}/apple-touch-icon.png"
        )
        return context


def serve_logo(request: HttpRequest, filename: str | None = None) -> FileResponse:
    """
    Serves the configured logo file with Content-Disposition: attachment.
    Prevents inline execution of SVGs. See GHSA-6p53-hqqw-8j62
    """
    config = ApplicationConfiguration.objects.first()
    app_logo = config.app_logo

    if app_logo:
        path = Path(app_logo.path)
        logo_name = app_logo.name
    else:
        if not settings.APP_LOGO:
            raise Http404("No logo configured")

        logo_root = (Path(settings.MEDIA_ROOT) / "logo").resolve()
        path = (Path(settings.MEDIA_ROOT) / settings.APP_LOGO.lstrip("/")).resolve()
        if not path.is_relative_to(logo_root) or not path.is_file():
            raise Http404("Configured logo not found")

        logo_name = path.name

    content_type = magic.from_file(path, mime=True) or "application/octet-stream"
    logo_file = app_logo.open("rb") if app_logo else path.open("rb")

    return FileResponse(
        logo_file,
        content_type=content_type,
        filename=logo_name,
        as_attachment=True,
    )
