from django.http import HttpResponse
from django.template.defaultfilters import slugify
from django.views.generic.detail import DetailView

from paperless.db import GnuPG

from .models import Document


class PdfView(DetailView):

    model = Document

    def render_to_response(self, context, **response_kwargs):
        """
        Override the default to return the unencrypted PDF as raw data.
        """

        response = HttpResponse(
            GnuPG.decrypted(self.object.pdf), content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(
            slugify(str(self.object)) + ".pdf")

        return response
