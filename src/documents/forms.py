import os
import tempfile
from datetime import datetime
from time import mktime

import magic
from django import forms
from django.conf import settings
from django_q.tasks import async_task
from pathvalidate import validate_filename, ValidationError

from documents.parsers import is_mime_type_supported


class UploadForm(forms.Form):

    document = forms.FileField()

    def clean_document(self):
        document_name = self.cleaned_data.get("document").name

        try:
            validate_filename(document_name)
        except ValidationError:
            raise forms.ValidationError("That filename is suspicious.")

        document_data = self.cleaned_data.get("document").read()

        mime_type = magic.from_buffer(document_data, mime=True)

        if not is_mime_type_supported(mime_type):
            raise forms.ValidationError("This mime type is not supported.")

        return document_name, document_data

    def save(self):
        """
        Since the consumer already does a lot of work, it's easier just to save
        to-be-consumed files to the consumption directory rather than have the
        form do that as well.  Think of it as a poor-man's queue server.
        """

        original_filename, data = self.cleaned_data.get("document")

        t = int(mktime(datetime.now().timetuple()))

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)

        with tempfile.NamedTemporaryFile(prefix="paperless-upload-",
                                         dir=settings.SCRATCH_DIR,
                                         delete=False) as f:

            f.write(data)
            os.utime(f.name, times=(t, t))

            async_task("documents.tasks.consume_file",
                       f.name,
                       override_filename=original_filename,
                       task_name=os.path.basename(original_filename)[:100])
