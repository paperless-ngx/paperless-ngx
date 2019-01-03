from rest_framework import serializers

from .models import Correspondent, Tag, Document, Log


class CorrespondentSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Correspondent
        fields = ("id", "slug", "name")


class TagSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Tag
        fields = (
            "id", "slug", "name", "colour", "match", "matching_algorithm")


class CorrespondentField(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        return Correspondent.objects.all()


class TagsField(serializers.HyperlinkedRelatedField):
    def get_queryset(self):
        return Tag.objects.all()


class DocumentSerializer(serializers.ModelSerializer):

    correspondent = CorrespondentField(
        view_name="drf:correspondent-detail", allow_null=True)
    tags = TagsField(view_name="drf:tag-detail", many=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "correspondent",
            "title",
            "content",
            "file_type",
            "tags",
            "checksum",
            "created",
            "modified",
            "added",
            "file_name",
            "download_url",
            "thumbnail_url",
        )


class LogSerializer(serializers.ModelSerializer):

    time = serializers.DateTimeField()
    messages = serializers.CharField()

    class Meta:
        model = Log
        fields = (
            "time",
            "messages"
        )
