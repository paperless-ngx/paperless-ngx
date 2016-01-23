import os

from django.conf import settings
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone


class SluggedModel(models.Model):

    name = models.CharField(max_length=128, unique=True)
    slug = models.SlugField(blank=True)

    class Meta(object):
        abstract = True

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        models.Model.save(self, *args, **kwargs)

    def __str__(self):
        return self.name


class Sender(SluggedModel):

    class Meta(object):
        ordering = ("name",)


class Tag(SluggedModel):
    
    COLOURS = (
        (1, "#a6cee3"),
        (2, "#1f78b4"),
        (3, "#b2df8a"),
        (4, "#33a02c"),
        (5, "#fb9a99"),
        (6, "#e31a1c"),
        (7, "#fdbf6f"),
        (8, "#ff7f00"),
        (9, "#cab2d6"),
        (10, "#6a3d9a"),
        (11, "#b15928"),
        (12, "#000000"),
        (13, "#cccccc")
    )
    colour = models.PositiveIntegerField(choices=COLOURS, default=1)


class Document(models.Model):

    sender = models.ForeignKey(
        Sender, blank=True, null=True, related_name="documents")
    title = models.CharField(max_length=128, blank=True, db_index=True)
    content = models.TextField(db_index=True)
    tags = models.ManyToManyField(Tag, related_name="documents")
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
