import magic
from pathvalidate import validate_filename, ValidationError
from rest_framework import serializers

from .models import Correspondent, Tag, Document, Log, DocumentType
from .parsers import is_mime_type_supported


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
            "tags",
            "tags_id",
            "created",
            "modified",
            "added",
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


class PostDocumentSerializer(serializers.Serializer):

    document = serializers.FileField(
        label="Document",
        write_only=True,
    )

    title = serializers.CharField(
        label="Title",
        write_only=True,
        required=False,
    )

    correspondent = serializers.CharField(
        label="Correspondent",
        write_only=True,
        required=False,
    )

    document_type = serializers.CharField(
        label="Document type",
        write_only=True,
        required=False,
    )

    tags = serializers.ListField(
        child=serializers.CharField(),
        label="Tags",
        source="tag",
        write_only=True,
        required=False,
    )

    def validate(self, attrs):
        document = attrs.get('document')

        try:
            validate_filename(document.name)
        except ValidationError:
            raise serializers.ValidationError("Invalid filename.")

        document_data = document.file.read()
        mime_type = magic.from_buffer(document_data, mime=True)

        if not is_mime_type_supported(mime_type):
            raise serializers.ValidationError(
                "This mime type is not supported.")

        attrs['document_data'] = document_data

        title = attrs.get('title')

        if not title:
            attrs['title'] = None

        correspondent = attrs.get('correspondent')
        if correspondent:
            c, _ = Correspondent.objects.get_or_create(name=correspondent)
            attrs['correspondent_id'] = c.id
        else:
            attrs['correspondent_id'] = None

        document_type = attrs.get('document_type')
        if document_type:
            dt, _ = DocumentType.objects.get_or_create(name=document_type)
            attrs['document_type_id'] = dt.id
        else:
            attrs['document_type_id'] = None

        tags = attrs.get('tag')
        if tags:
            tag_ids = []
            for tag in tags:
                tag, _ = Tag.objects.get_or_create(name=tag)
                tag_ids.append(tag.id)
            attrs['tag_ids'] = tag_ids
        else:
            attrs['tag_ids'] = None

        return attrs
