import gnupg

from django.conf import settings
from django.http import HttpResponse
from django.template.defaultfilters import slugify
from django.views.generic.detail import DetailView

from .models import Document


class PdfView(DetailView):

    model = Document

    def render_to_response(self, context, **response_kwargs):
        """
        Override the default to return the unencrypted PDF as raw data.
        """

        gpg = gnupg.GPG(gnupghome=settings.GNUPG_HOME)

        response = HttpResponse(gpg.decrypt_file(
            self.object.pdf,
            passphrase=settings.PASSPHRASE,
        ).data, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="{}"'.format(
            slugify(str(self.object)) + ".pdf")

        return response
