from django.db import models


class Document(models.Model):

    sender = models.CharField(max_length=128, blank=True, db_index=True)
    title = models.CharField(max_length=128, blank=True, db_index=True)
    content = models.TextField(db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
