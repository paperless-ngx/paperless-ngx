import magic
import os

from datetime import datetime
from time import mktime

from django import forms
from django.conf import settings

from .models import Document, Correspondent
from .consumer import Consumer


class UploadForm(forms.Form):

    TYPE_LOOKUP = {
        "application/pdf": Document.TYPE_PDF,
        "image/png": Document.TYPE_PNG,
        "image/jpeg": Document.TYPE_JPG,
        "image/gif": Document.TYPE_GIF,
        "image/tiff": Document.TYPE_TIF,
    }

    correspondent = forms.CharField(
        max_length=Correspondent._meta.get_field("name").max_length,
        required=False
    )
    title = forms.CharField(
        max_length=Document._meta.get_field("title").max_length,
        required=False
    )
    document = forms.FileField()

    def __init__(self, *args, **kwargs):
        forms.Form.__init__(self, *args, **kwargs)
        self._file_type = None

    def clean_correspondent(self):
        """
        I suppose it might look cleaner to use .get_or_create() here, but that
        would also allow someone to fill up the db with bogus correspondents
        before all validation was met.
        """

        corresp = self.cleaned_data.get("correspondent")

        if not corresp:
            return None

        if not Correspondent.SAFE_REGEX.match(corresp) or " - " in corresp:
            raise forms.ValidationError(
                "That correspondent name is suspicious.")

        return corresp

    def clean_title(self):

        title = self.cleaned_data.get("title")

        if not title:
            return None

        if not Correspondent.SAFE_REGEX.match(title) or " - " in title:
            raise forms.ValidationError("That title is suspicious.")

        return title

    def clean_document(self):

        document = self.cleaned_data.get("document").read()

        with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
            file_type = m.id_buffer(document)

        if file_type not in self.TYPE_LOOKUP:
            raise forms.ValidationError("The file type is invalid.")

        self._file_type = self.TYPE_LOOKUP[file_type]

        return document

    def save(self):
        """
        Since the consumer already does a lot of work, it's easier just to save
        to-be-consumed files to the consumption directory rather than have the
        form do that as well.  Think of it as a poor-man's queue server.
        """

        correspondent = self.cleaned_data.get("correspondent")
        title = self.cleaned_data.get("title")
        document = self.cleaned_data.get("document")

        t = int(mktime(datetime.now().timetuple()))
        file_name = os.path.join(
            settings.CONSUMPTION_DIR,
            "{} - {}.{}".format(correspondent, title, self._file_type)
        )

        with open(file_name, "wb") as f:
            f.write(document)
            os.utime(file_name, times=(t, t))
