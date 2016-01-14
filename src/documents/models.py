import os

from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone


class Sender(models.Model):

    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        models.Model.save(self, *args, **kwargs)

    def __str__(self):
        return self.name


class Document(models.Model):

    sender = models.ForeignKey(
        Sender, blank=True, null=True, related_name="documents")
    title = models.CharField(max_length=128, blank=True, db_index=True)
    content = models.TextField(db_index=True)
    created = models.DateTimeField(default=timezone.now, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    class Meta(object):
        ordering = ("sender", "title")

    def __str__(self):
        created = self.created.strftime("%Y-%m-%d")
        if self.sender and self.title:
            return "{}: {}, {}".format(created, self.sender, self.title)
        if self.sender or self.title:
            return "{}: {}".format(created, self.sender or self.title)
        return str(created)

    @property
    def pdf_path(self):
        return os.path.join(
            settings.MEDIA_ROOT,
            "documents",
            "pdf",
            "{:07}.pdf.gpg".format(self.pk)
        )

    @property
    def pdf(self):
        return open(self.pdf_path, "rb")

    @property
    def parseable_file_name(self):
        if self.sender and self.title:
            return "{} - {}.pdf".format(self.sender, self.title)
        return os.path.basename(self.pdf_path)
