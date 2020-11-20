import os
import tempfile
from datetime import datetime
from time import mktime

from django import forms
from django.conf import settings
from django_q.tasks import async_task
from pathvalidate import validate_filename, ValidationError


class UploadForm(forms.Form):

    document = forms.FileField()

    def clean_document(self):
        try:
            validate_filename(self.cleaned_data.get("document").name)
        except ValidationError:
            raise forms.ValidationError("That filename is suspicious.")
        return self.cleaned_data.get("document")

    def save(self):
        """
        Since the consumer already does a lot of work, it's easier just to save
        to-be-consumed files to the consumption directory rather than have the
        form do that as well.  Think of it as a poor-man's queue server.
        """

        document = self.cleaned_data.get("document").read()
        original_filename = self.cleaned_data.get("document").name

        t = int(mktime(datetime.now().timetuple()))

        os.makedirs(settings.SCRATCH_DIR, exist_ok=True)

        with tempfile.NamedTemporaryFile(prefix="paperless-upload-", dir=settings.SCRATCH_DIR, delete=False) as f:

            f.write(document)
            os.utime(f.name, times=(t, t))

            async_task("documents.tasks.consume_file", f.name, override_filename=original_filename, task_name=os.path.basename(original_filename))
