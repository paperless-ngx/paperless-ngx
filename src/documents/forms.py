import os

from datetime import datetime
from time import mktime

from django import forms
from django.conf import settings
from pathvalidate import validate_filename, ValidationError


class UploadForm(forms.Form):

    document = forms.FileField()

    def clean_document(self):
        try:
            validate_filename(self.cleaned_data.get("document").name)
        except ValidationError:
            raise forms.ValidationError("That filename is suspicious.")
        return self.cleaned_data.get("document")

    def get_filename(self, i=None):
        return os.path.join(
            settings.CONSUMPTION_DIR,
            "{}_{}".format(str(i), self.cleaned_data.get("document").name) if i else self.cleaned_data.get("document").name
        )

    def save(self):
        """
        Since the consumer already does a lot of work, it's easier just to save
        to-be-consumed files to the consumption directory rather than have the
        form do that as well.  Think of it as a poor-man's queue server.
        """

        document = self.cleaned_data.get("document").read()

        t = int(mktime(datetime.now().timetuple()))

        file_name = self.get_filename()
        i = 0
        while os.path.exists(file_name):
            i += 1
            file_name = self.get_filename(i)

        with open(file_name, "wb") as f:
            f.write(document)
            os.utime(file_name, times=(t, t))
