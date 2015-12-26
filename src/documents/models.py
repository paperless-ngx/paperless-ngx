from django.db import models
from django.utils import timezone


class Document(models.Model):

    sender = models.CharField(max_length=128, blank=True, db_index=True)
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
            return "{}: {}, {}".format(created, self.sender or self.title)
        return str(created)
