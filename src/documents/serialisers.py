from rest_framework import serializers

from .models import Correspondent, Tag, Document, Log, DocumentType


class CorrespondentSerializer(serializers.HyperlinkedModelSerializer):

    document_count = serializers.IntegerField(read_only=True)

    last_correspondence = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Correspondent
        fields = (
            "id",
            "slug",
            "name",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "document_count",
            "last_correspondence"
        )


class DocumentTypeSerializer(serializers.HyperlinkedModelSerializer):

    document_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = DocumentType
        fields = (
            "id",
            "slug",
            "name",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "document_count"
        )


class TagSerializer(serializers.HyperlinkedModelSerializer):

    document_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Tag
        fields = (
            "id",
            "slug",
            "name",
            "colour",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "is_inbox_tag",
            "document_count"
        )


class CorrespondentField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Correspondent.objects.all()


class TagsField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Tag.objects.all()


class DocumentTypeField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return DocumentType.objects.all()


class DocumentSerializer(serializers.ModelSerializer):

    correspondent_id = CorrespondentField(
        allow_null=True, source='correspondent')
    tags_id = TagsField(many=True, source='tags')
    document_type_id = DocumentTypeField(
        allow_null=True, source='document_type')

    class Meta:
        model = Document
        depth = 1
        fields = (
            "id",
            "correspondent",
            "correspondent_id",
            "document_type",
            "document_type_id",
            "title",
            "content",
            "mime_type",
            "tags",
            "tags_id",
            "checksum",
            "created",
            "modified",
            "added",
            "file_name",
            "archive_serial_number"
        )


class LogSerializer(serializers.ModelSerializer):

    class Meta:
        model = Log
        fields = (
            "id",
            "created",
            "message",
            "group",
            "level"
        )
