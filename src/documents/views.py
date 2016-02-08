from django.http import HttpResponse
from django.template.defaultfilters import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import FormView, DetailView

from paperless.db import GnuPG

from .models import Document
from .forms import UploadForm


class PdfView(DetailView):

    model = Document

    def render_to_response(self, context, **response_kwargs):
        """
        Override the default to return the unencrypted PDF as raw data.
        """

        content_types = {
            Document.TYPE_PDF: "application/pdf",
            Document.TYPE_PNG: "image/png",
            Document.TYPE_JPG: "image/jpeg",
            Document.TYPE_GIF: "image/gif",
            Document.TYPE_TIF: "image/tiff",
        }

        response = HttpResponse(
            GnuPG.decrypted(self.object.source_file),
            content_type=content_types[self.object.file_type]
        )
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(
            slugify(str(self.object)) + "." + self.object.file_type)

        return response


class PushView(FormView):
    """
    A crude REST API for creating documents.
    """

    form_class = UploadForm

    @classmethod
    def as_view(cls, **kwargs):
        return csrf_exempt(FormView.as_view(**kwargs))

    def form_valid(self, form):
        return HttpResponse("1")

    def form_invalid(self, form):
        return HttpResponse("0")
