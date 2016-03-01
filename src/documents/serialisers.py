from rest_framework import serializers

from .models import Sender, Tag, Document, Log


class SenderSerializer(serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = Sender
        fields = ("id", "slug", "name")


class TagSerializer(serializers.HyperlinkedModelSerializer):

    class Meta(object):
        model = Tag
        fields = (
            "id", "slug", "name", "colour", "match", "matching_algorithm")


class DocumentSerializer(serializers.ModelSerializer):

    sender = serializers.HyperlinkedRelatedField(
        read_only=True, view_name="drf:sender-detail", allow_null=True)
    tags = serializers.HyperlinkedRelatedField(
        read_only=True, view_name="drf:tag-detail", many=True)

    class Meta(object):
        model = Document
        fields = (
            "id",
            "sender",
            "title",
            "content",
            "file_type",
            "tags",
            "created",
            "modified",
            "file_name",
            "download_url"
        )


class LogSerializer(serializers.ModelSerializer):

    time = serializers.DateTimeField()
    messages = serializers.CharField()

    class Meta(object):
        model = Log
        fields = (
            "time",
            "messages"
        )
