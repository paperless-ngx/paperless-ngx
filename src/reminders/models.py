from django.db import models


class Reminder(models.Model):

    document = models.ForeignKey("documents.Document",on_delete=models.DO_NOTHING)
    date = models.DateTimeField()
    note = models.TextField(blank=True)
