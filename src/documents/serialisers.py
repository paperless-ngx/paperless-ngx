from rest_framework import serializers

from .models import Sender, Tag, Document


class SenderSerializer(serializers.ModelSerializer):

    class Meta(object):
        model = Sender
        fields = ("id", "slug", "name")


class TagSerializer(serializers.ModelSerializer):

    class Meta(object):
        model = Tag
        fields = ("id", "slug", "name", "colour", "match", "matching_algorithm")


class DocumentSerializer(serializers.ModelSerializer):

    sender = serializers.HyperlinkedModelSerializer(read_only=True)
    tags = serializers.HyperlinkedModelSerializer(read_only=True)

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
