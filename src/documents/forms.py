import magic
import os

from datetime import datetime
from hashlib import sha256
from time import mktime

from django import forms
from django.conf import settings

from .models import Document, Sender
from .consumer import Consumer


class UploadForm(forms.Form):

    SECRET = settings.UPLOAD_SHARED_SECRET
    TYPE_LOOKUP = {
        "application/pdf": Document.TYPE_PDF,
        "image/png": Document.TYPE_PNG,
        "image/jpeg": Document.TYPE_JPG,
        "image/gif": Document.TYPE_GIF,
        "image/tiff": Document.TYPE_TIF,
    }

    sender = forms.CharField(
        max_length=Sender._meta.get_field("name").max_length, required=False)
    title = forms.CharField(
        max_length=Document._meta.get_field("title").max_length,
        required=False
    )
    document = forms.FileField()
    signature = forms.CharField(max_length=256)

    def clean_sender(self):
        """
        I suppose it might look cleaner to use .get_or_create() here, but that
        would also allow someone to fill up the db with bogus senders before
        all validation was met.
        """
        sender = self.cleaned_data.get("sender")
        if not sender:
            return None
        if not Sender.SAFE_REGEX.match(sender) or " - " in sender:
            raise forms.ValidationError("That sender name is suspicious.")
        return sender

    def clean_title(self):
        title = self.cleaned_data.get("title")
        if not title:
            return None
        if not Sender.SAFE_REGEX.match(title) or " - " in title:
            raise forms.ValidationError("That title is suspicious.")

    def clean_document(self):
        document = self.cleaned_data.get("document").read()
        with magic.Magic(flags=magic.MAGIC_MIME_TYPE) as m:
            file_type = m.id_buffer(document)
        if file_type not in self.TYPE_LOOKUP:
            raise forms.ValidationError("The file type is invalid.")
        return document, self.TYPE_LOOKUP[file_type]

    def clean(self):
        sender = self.clened_data("sender")
        title = self.cleaned_data("title")
        signature = self.cleaned_data("signature")
        if sha256(sender + title + self.SECRET).hexdigest() == signature:
            return True
        return False

    def save(self):
        """
        Since the consumer already does a lot of work, it's easier just to save
        to-be-consumed files to the consumption directory rather than have the
        form do that as well.  Think of it as a poor-man's queue server.
        """

        sender = self.clened_data("sender")
        title = self.cleaned_data("title")
        document, file_type = self.cleaned_data.get("document")

        t = int(mktime(datetime.now()))
        file_name = os.path.join(
            Consumer.CONSUME, "{} - {}.{}".format(sender, title, file_type))

        with open(file_name, "wb") as f:
            f.write(document)
            os.utime(file_name, times=(t, t))
