import datetime
import math
import re

try:
    import zoneinfo
except ImportError:
    import backports.zoneinfo as zoneinfo
import magic
from django.conf import settings
from django.utils.text import slugify
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.fields import SerializerMethodField

from . import bulk_edit
from .models import Correspondent
from .models import Document
from .models import DocumentType
from .models import MatchingModel
from .models import PaperlessTask
from .models import SavedView
from .models import SavedViewFilterRule
from .models import StoragePath
from .models import Tag
from .models import UiSettings
from .parsers import is_mime_type_supported


# https://www.django-rest-framework.org/api-guide/serializers/#example
class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    A ModelSerializer that takes an additional `fields` argument that
    controls which fields should be displayed.
    """

    def __init__(self, *args, **kwargs):
        # Don't pass the 'fields' arg up to the superclass
        fields = kwargs.pop("fields", None)

        # Instantiate the superclass normally
        super().__init__(*args, **kwargs)

        if fields is not None:
            # Drop any fields that are not specified in the `fields` argument.
            allowed = set(fields)
            existing = set(self.fields)
            for field_name in existing - allowed:
                self.fields.pop(field_name)


class MatchingModelSerializer(serializers.ModelSerializer):

    document_count = serializers.IntegerField(read_only=True)

    def get_slug(self, obj):
        return slugify(obj.name)

    slug = SerializerMethodField()

    def validate_match(self, match):
        if (
            "matching_algorithm" in self.initial_data
            and self.initial_data["matching_algorithm"] == MatchingModel.MATCH_REGEX
        ):
            try:
                re.compile(match)
            except re.error as e:
                raise serializers.ValidationError(
                    _("Invalid regular expression: %(error)s") % {"error": str(e.msg)},
                )
        return match


class CorrespondentSerializer(MatchingModelSerializer):

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
            "last_correspondence",
        )


class DocumentTypeSerializer(MatchingModelSerializer):
    class Meta:
        model = DocumentType
        fields = (
            "id",
            "slug",
            "name",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "document_count",
        )


class ColorField(serializers.Field):

    COLOURS = (
        (1, "#a6cee3"),
        (2, "#1f78b4"),
        (3, "#b2df8a"),
        (4, "#33a02c"),
        (5, "#fb9a99"),
        (6, "#e31a1c"),
        (7, "#fdbf6f"),
        (8, "#ff7f00"),
        (9, "#cab2d6"),
        (10, "#6a3d9a"),
        (11, "#b15928"),
        (12, "#000000"),
        (13, "#cccccc"),
    )

    def to_internal_value(self, data):
        for id, color in self.COLOURS:
            if id == data:
                return color
        raise serializers.ValidationError()

    def to_representation(self, value):
        for id, color in self.COLOURS:
            if color == value:
                return id
        return 1


class TagSerializerVersion1(MatchingModelSerializer):

    colour = ColorField(source="color", default="#a6cee3")

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
            "document_count",
        )


class TagSerializer(MatchingModelSerializer):
    def get_text_color(self, obj):
        try:
            h = obj.color.lstrip("#")
            rgb = tuple(int(h[i : i + 2], 16) / 256 for i in (0, 2, 4))
            luminance = math.sqrt(
                0.299 * math.pow(rgb[0], 2)
                + 0.587 * math.pow(rgb[1], 2)
                + 0.114 * math.pow(rgb[2], 2),
            )
            return "#ffffff" if luminance < 0.53 else "#000000"
        except ValueError:
            return "#000000"

    text_color = serializers.SerializerMethodField()

    class Meta:
        model = Tag
        fields = (
            "id",
            "slug",
            "name",
            "color",
            "text_color",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "is_inbox_tag",
            "document_count",
        )

    def validate_color(self, color):
        regex = r"#[0-9a-fA-F]{6}"
        if not re.match(regex, color):
            raise serializers.ValidationError(_("Invalid color."))
        return color


class CorrespondentField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Correspondent.objects.all()


class TagsField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return Tag.objects.all()


class DocumentTypeField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return DocumentType.objects.all()


class StoragePathField(serializers.PrimaryKeyRelatedField):
    def get_queryset(self):
        return StoragePath.objects.all()


class DocumentSerializer(DynamicFieldsModelSerializer):

    correspondent = CorrespondentField(allow_null=True)
    tags = TagsField(many=True)
    document_type = DocumentTypeField(allow_null=True)
    storage_path = StoragePathField(allow_null=True)

    original_file_name = SerializerMethodField()
    archived_file_name = SerializerMethodField()
    created_date = serializers.DateField(required=False)

    def get_original_file_name(self, obj):
        return obj.get_public_filename()

    def get_archived_file_name(self, obj):
        if obj.has_archive_version:
            return obj.get_public_filename(archive=True)
        else:
            return None

    def update(self, instance, validated_data):
        if "created_date" in validated_data and "created" not in validated_data:
            new_datetime = datetime.datetime.combine(
                validated_data.get("created_date"),
                datetime.time(0, 0, 0, 0, zoneinfo.ZoneInfo(settings.TIME_ZONE)),
            )
            instance.created = new_datetime
            instance.save()
        validated_data.pop("created_date")
        super().update(instance, validated_data)
        return instance

    class Meta:
        model = Document
        depth = 1
        fields = (
            "id",
            "correspondent",
            "document_type",
            "storage_path",
            "title",
            "content",
            "tags",
            "created",
            "created_date",
            "modified",
            "added",
            "archive_serial_number",
            "original_file_name",
            "archived_file_name",
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
        fields = [
            "id",
            "name",
            "show_on_dashboard",
            "show_in_sidebar",
            "sort_field",
            "sort_reverse",
            "filter_rules",
        ]

    def update(self, instance, validated_data):
        if "filter_rules" in validated_data:
            rules_data = validated_data.pop("filter_rules")
        else:
            rules_data = None
        super().update(instance, validated_data)
        if rules_data is not None:
            SavedViewFilterRule.objects.filter(saved_view=instance).delete()
            for rule_data in rules_data:
                SavedViewFilterRule.objects.create(saved_view=instance, **rule_data)
        return instance

    def create(self, validated_data):
        rules_data = validated_data.pop("filter_rules")
        saved_view = SavedView.objects.create(**validated_data)
        for rule_data in rules_data:
            SavedViewFilterRule.objects.create(saved_view=saved_view, **rule_data)
        return saved_view


class DocumentListSerializer(serializers.Serializer):

    documents = serializers.ListField(
        required=True,
        label="Documents",
        write_only=True,
        child=serializers.IntegerField(),
    )

    def _validate_document_id_list(self, documents, name="documents"):
        if not type(documents) == list:
            raise serializers.ValidationError(f"{name} must be a list")
        if not all([type(i) == int for i in documents]):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        count = Document.objects.filter(id__in=documents).count()
        if not count == len(documents):
            raise serializers.ValidationError(
                f"Some documents in {name} don't exist or were " f"specified twice.",
            )

    def validate_documents(self, documents):
        self._validate_document_id_list(documents)
        return documents


class BulkEditSerializer(DocumentListSerializer):

    method = serializers.ChoiceField(
        choices=[
            "set_correspondent",
            "set_document_type",
            "set_storage_path",
            "add_tag",
            "remove_tag",
            "modify_tags",
            "delete",
            "redo_ocr",
        ],
        label="Method",
        write_only=True,
    )

    parameters = serializers.DictField(allow_empty=True)

    def _validate_tag_id_list(self, tags, name="tags"):
        if not type(tags) == list:
            raise serializers.ValidationError(f"{name} must be a list")
        if not all([type(i) == int for i in tags]):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        count = Tag.objects.filter(id__in=tags).count()
        if not count == len(tags):
            raise serializers.ValidationError(
                f"Some tags in {name} don't exist or were specified twice.",
            )

    def validate_method(self, method):
        if method == "set_correspondent":
            return bulk_edit.set_correspondent
        elif method == "set_document_type":
            return bulk_edit.set_document_type
        elif method == "set_storage_path":
            return bulk_edit.set_storage_path
        elif method == "add_tag":
            return bulk_edit.add_tag
        elif method == "remove_tag":
            return bulk_edit.remove_tag
        elif method == "modify_tags":
            return bulk_edit.modify_tags
        elif method == "delete":
            return bulk_edit.delete
        elif method == "redo_ocr":
            return bulk_edit.redo_ocr
        else:
            raise serializers.ValidationError("Unsupported method.")

    def _validate_parameters_tags(self, parameters):
        if "tag" in parameters:
            tag_id = parameters["tag"]
            try:
                Tag.objects.get(id=tag_id)
            except Tag.DoesNotExist:
                raise serializers.ValidationError("Tag does not exist")
        else:
            raise serializers.ValidationError("tag not specified")

    def _validate_parameters_document_type(self, parameters):
        if "document_type" in parameters:
            document_type_id = parameters["document_type"]
            if document_type_id is None:
                # None is ok
                return
            try:
                DocumentType.objects.get(id=document_type_id)
            except DocumentType.DoesNotExist:
                raise serializers.ValidationError("Document type does not exist")
        else:
            raise serializers.ValidationError("document_type not specified")

    def _validate_parameters_correspondent(self, parameters):
        if "correspondent" in parameters:
            correspondent_id = parameters["correspondent"]
            if correspondent_id is None:
                return
            try:
                Correspondent.objects.get(id=correspondent_id)
            except Correspondent.DoesNotExist:
                raise serializers.ValidationError("Correspondent does not exist")
        else:
            raise serializers.ValidationError("correspondent not specified")

    def _validate_storage_path(self, parameters):
        if "storage_path" in parameters:
            storage_path_id = parameters["storage_path"]
            if storage_path_id is None:
                return
            try:
                StoragePath.objects.get(id=storage_path_id)
            except StoragePath.DoesNotExist:
                raise serializers.ValidationError(
                    "Storage path does not exist",
                )
        else:
            raise serializers.ValidationError("storage path not specified")

    def _validate_parameters_modify_tags(self, parameters):
        if "add_tags" in parameters:
            self._validate_tag_id_list(parameters["add_tags"], "add_tags")
        else:
            raise serializers.ValidationError("add_tags not specified")

        if "remove_tags" in parameters:
            self._validate_tag_id_list(parameters["remove_tags"], "remove_tags")
        else:
            raise serializers.ValidationError("remove_tags not specified")

    def validate(self, attrs):

        method = attrs["method"]
        parameters = attrs["parameters"]

        if method == bulk_edit.set_correspondent:
            self._validate_parameters_correspondent(parameters)
        elif method == bulk_edit.set_document_type:
            self._validate_parameters_document_type(parameters)
        elif method == bulk_edit.add_tag or method == bulk_edit.remove_tag:
            self._validate_parameters_tags(parameters)
        elif method == bulk_edit.modify_tags:
            self._validate_parameters_modify_tags(parameters)
        elif method == bulk_edit.set_storage_path:
            self._validate_storage_path(parameters)

        return attrs


class PostDocumentSerializer(serializers.Serializer):

    created = serializers.DateTimeField(
        label="Created",
        allow_null=True,
        write_only=True,
        required=False,
    )

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
                _("File type %(type)s not supported") % {"type": mime_type},
            )

        return document.name, document_data

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


class BulkDownloadSerializer(DocumentListSerializer):

    content = serializers.ChoiceField(
        choices=["archive", "originals", "both"],
        default="archive",
    )

    compression = serializers.ChoiceField(
        choices=["none", "deflated", "bzip2", "lzma"],
        default="none",
    )

    def validate_compression(self, compression):
        import zipfile

        return {
            "none": zipfile.ZIP_STORED,
            "deflated": zipfile.ZIP_DEFLATED,
            "bzip2": zipfile.ZIP_BZIP2,
            "lzma": zipfile.ZIP_LZMA,
        }[compression]


class StoragePathSerializer(MatchingModelSerializer):
    class Meta:
        model = StoragePath
        fields = (
            "id",
            "slug",
            "name",
            "path",
            "match",
            "matching_algorithm",
            "is_insensitive",
            "document_count",
        )

    def validate_path(self, path):
        try:
            path.format(
                title="title",
                correspondent="correspondent",
                document_type="document_type",
                created="created",
                created_year="created_year",
                created_month="created_month",
                created_day="created_day",
                added="added",
                added_year="added_year",
                added_month="added_month",
                added_day="added_day",
                asn="asn",
                tags="tags",
                tag_list="tag_list",
            )

        except (KeyError):
            raise serializers.ValidationError(_("Invalid variable detected."))

        return path


class UiSettingsViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = UiSettings
        depth = 1
        fields = [
            "id",
            "settings",
        ]

    def create(self, validated_data):
        ui_settings = UiSettings.objects.update_or_create(
            user=validated_data.get("user"),
            defaults={"settings": validated_data.get("settings", None)},
        )
        return ui_settings


class TasksViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperlessTask
        depth = 1
        fields = "__all__"

    type = serializers.SerializerMethodField()

    def get_type(self, obj):
        # just file tasks, for now
        return "file"

    result = serializers.SerializerMethodField()

    def get_result(self, obj):
        result = ""
        if hasattr(obj, "attempted_task") and obj.attempted_task:
            result = obj.attempted_task.result
        return result

    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        if obj.attempted_task is None:
            if obj.started:
                return "started"
            else:
                return "queued"
        elif obj.attempted_task.success:
            return "complete"
        elif not obj.attempted_task.success:
            return "failed"
        else:
            return "unknown"


class AcknowledgeTasksViewSerializer(serializers.Serializer):

    tasks = serializers.ListField(
        required=True,
        label="Tasks",
        write_only=True,
        child=serializers.IntegerField(),
    )

    def _validate_task_id_list(self, tasks, name="tasks"):
        pass
        if not type(tasks) == list:
            raise serializers.ValidationError(f"{name} must be a list")
        if not all([type(i) == int for i in tasks]):
            raise serializers.ValidationError(f"{name} must be a list of integers")
        count = PaperlessTask.objects.filter(id__in=tasks).count()
        if not count == len(tasks):
            raise serializers.ValidationError(
                f"Some tasks in {name} don't exist or were specified twice.",
            )

    def validate_tasks(self, tasks):
        self._validate_task_id_list(tasks)
        return tasks
