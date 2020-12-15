import magic
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from .models import Correspondent, Tag, Document, Log, DocumentType, \
    SavedView, SavedViewFilterRule
from .parsers import is_mime_type_supported


class CorrespondentSerializer(serializers.ModelSerializer):

    document_count = serializers.IntegerField(read_only=True)

    last_correspondence = serializers.DateTimeField(read_only=True)

    def get_slug(self, obj):
        return slugify(obj.name)
    slug = SerializerMethodField()

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


class DocumentTypeSerializer(serializers.ModelSerializer):

    document_count = serializers.IntegerField(read_only=True)

    def get_slug(self, obj):
        return slugify(obj.name)
    slug = SerializerMethodField()

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


class TagSerializer(serializers.ModelSerializer):

    document_count = serializers.IntegerField(read_only=True)

    def get_slug(self, obj):
        return slugify(obj.name)
    slug = SerializerMethodField()

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

    correspondent = CorrespondentField(allow_null=True)
    tags = TagsField(many=True)
    document_type = DocumentTypeField(allow_null=True)

    original_file_name = SerializerMethodField()
    archived_file_name = SerializerMethodField()

    def get_original_file_name(self, obj):
        return obj.get_public_filename()

    def get_archived_file_name(self, obj):
        if obj.archive_checksum:
            return obj.get_public_filename(archive=True)
        else:
            return None

    class Meta:
        model = Document
        depth = 1
        fields = (
            "id",
            "correspondent",
            "document_type",
            "title",
            "content",
            "tags",
            "created",
            "modified",
            "added",
            "archive_serial_number",
            "original_file_name",
            "archived_file_name",
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


class SavedViewFilterRuleSerializer(serializers.ModelSerializer):

    class Meta:
        model = SavedViewFilterRule
        fields = ["rule_type", "value"]


class SavedViewSerializer(serializers.ModelSerializer):

    filter_rules = SavedViewFilterRuleSerializer(many=True)

    class Meta:
        model = SavedView
        depth = 1
        fields = ["id", "name", "show_on_dashboard", "show_in_sidebar",
                  "sort_field", "sort_reverse", "filter_rules"]

    def update(self, instance, validated_data):
        if 'filter_rules' in validated_data:
            rules_data = validated_data.pop('filter_rules')
        else:
            rules_data = None
        super(SavedViewSerializer, self).update(instance, validated_data)
        if rules_data:
            SavedViewFilterRule.objects.filter(saved_view=instance).delete()
            for rule_data in rules_data:
                SavedViewFilterRule.objects.create(
                    saved_view=instance, **rule_data)
        return instance

    def create(self, validated_data):
        rules_data = validated_data.pop('filter_rules')
        saved_view = SavedView.objects.create(**validated_data)
        for rule_data in rules_data:
            SavedViewFilterRule.objects.create(
                saved_view=saved_view, **rule_data)
        return saved_view


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

    correspondent = serializers.PrimaryKeyRelatedField(
        queryset=Correspondent.objects.all(),
        label="Correspondent",
        allow_null=True,
        write_only=True,
        required=False,
    )

    document_type = serializers.PrimaryKeyRelatedField(
        queryset=DocumentType.objects.all(),
        label="Document type",
        allow_null=True,
        write_only=True,
        required=False,
    )

    tags = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Tag.objects.all(),
        label="Tags",
        write_only=True,
        required=False,
    )

    def validate_document(self, document):
        document_data = document.file.read()
        mime_type = magic.from_buffer(document_data, mime=True)

        if not is_mime_type_supported(mime_type):
            raise serializers.ValidationError(
                "This file type is not supported.")

        return document.name, document_data

    def validate_title(self, title):
        if title:
            return title
        else:
            # do not return empty strings.
            return None

    def validate_correspondent(self, correspondent):
        if correspondent:
            return correspondent.id
        else:
            return None

    def validate_document_type(self, document_type):
        if document_type:
            return document_type.id
        else:
            return None

    def validate_tags(self, tags):
        if tags:
            return [tag.id for tag in tags]
        else:
            return None
