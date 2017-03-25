from documents.models import Document
from rest_framework import serializers

from .models import Reminder


class ReminderSerializer(serializers.HyperlinkedModelSerializer):

    document = serializers.HyperlinkedRelatedField(
        view_name="drf:document-detail", queryset=Document.objects)

    class Meta(object):
        model = Reminder
        fields = ("id", "document", "date", "note")
