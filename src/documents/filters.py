from functools import reduce
from operator import or_

from django.contrib.contenttypes.models import ContentType
from django.db.models import CharField
from django.db.models import Count
from django.db.models import OuterRef
from django.db.models import Q
from django.db.models.functions import Cast
from django_filters import NumberFilter
from django_filters.rest_framework import BooleanFilter
from django_filters.rest_framework import Filter
from django_filters.rest_framework import FilterSet
from guardian.utils import get_group_obj_perms_model
from guardian.utils import get_user_obj_perms_model
from rest_framework.filters import BaseFilterBackend
from rest_framework_guardian.filters import ObjectPermissionsFilter

from documents.models import Approval, Correspondent, Dossier, DossierForm, \
    ArchiveFont, FontLanguage, BackupRecord, EdocTask
from documents.models import CustomField
from documents.models import Document
from documents.models import DocumentType
from documents.models import Folder
from documents.models import Log
from documents.models import ShareLink
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Warehouse
from documents.permissions import get_objects_folder_for_user

CHAR_KWARGS = ["istartswith", "iendswith", "icontains", "iexact"]
ID_KWARGS = ["in", "exact"]
INT_KWARGS = ["exact", "gt", "gte", "lt", "lte", "isnull"]
DATE_KWARGS = ["year", "month", "day", "date__gt", "date__gte", "gt", "gte",
               "date__lt", "date__lte", "lt", "lte"]


class CorrespondentFilterSet(FilterSet):
    class Meta:
        model = Correspondent
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
        }


class TagFilterSet(FilterSet):
    class Meta:
        model = Tag
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
        }


class DocumentTypeFilterSet(FilterSet):
    class Meta:
        model = DocumentType
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
        }

class FontLanguageFilterSet(FilterSet):
    class Meta:
        model = FontLanguage
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
        }


class ArchiveFontFilterSet(FilterSet):
    class Meta:
        model = ArchiveFont
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
        }


class StoragePathFilterSet(FilterSet):
    class Meta:
        model = StoragePath
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
            "path": CHAR_KWARGS,
        }


class ObjectFilter(Filter):
    def __init__(self, exclude=False, in_list=False, field_name=""):
        super().__init__()
        self.exclude = exclude
        self.in_list = in_list
        self.field_name = field_name

    def filter(self, qs, value):
        if not value:
            return qs

        try:
            object_ids = [int(x) for x in value.split(",")]
        except ValueError:
            return qs

        if self.in_list:
            qs = qs.filter(**{f"{self.field_name}__id__in": object_ids}).distinct()
        else:
            for obj_id in object_ids:
                if self.exclude:
                    qs = qs.exclude(**{f"{self.field_name}__id": obj_id})
                else:
                    qs = qs.filter(**{f"{self.field_name}__id": obj_id})
        return qs


class WarehouseFilter(Filter):
    def __init__(self, exclude=False, in_list=False, field_name="",isnull=False):
        super().__init__()
        self.exclude = exclude
        self.in_list = in_list
        self.field_name = field_name
        self.isnull = isnull

    def filter(self, qs, value):
        if not value:
            return qs

        try:
            object_ids = [int(x) for x in value.split(",")]
        except ValueError:
            return qs

        if self.in_list:
            new_list = []
            warehouse_paths = Warehouse.objects.filter(id__in=object_ids).values_list("path", flat=True)
            if warehouse_paths:
                path_conditions = reduce(or_, (Q(path__startswith=item) for item in warehouse_paths))
                list_warehouses = Warehouse.objects.filter(path_conditions).values_list("id")
                new_list = [x[0] for x in list_warehouses]
            qs = qs.filter(**{f"{self.field_name}__id__in": new_list}).distinct()
        else:
            for obj_id in object_ids:
                if self.exclude:
                    new_list = []
                    warehouse_paths = Warehouse.objects.filter(id__in=object_ids).values_list("path", flat=True)
                    if warehouse_paths:
                        path_conditions = reduce(or_, (Q(path__startswith=item) for item in warehouse_paths))
                        list_warehouses = Warehouse.objects.filter(path_conditions).values_list("id")
                        new_list = [x[0] for x in list_warehouses]
                    qs = qs.exclude(**{f"{self.field_name}__id__in": new_list})
                elif self.isnull:
                    qs = qs.filter(**{f"{self.field_name}__isnull": self.isnull})
                else:
                    qs = qs.filter(**{f"{self.field_name}__id": obj_id})
        return qs


class FolderFilter(Filter):
    def __init__(self, exclude=False, in_list=False, field_name=""):
        super().__init__()
        self.exclude = exclude
        self.in_list = in_list
        self.field_name = field_name

    def filter(self, qs, value):
        if not value:
            return qs

        try:
            object_ids = [int(x) for x in value.split(",")]
        except ValueError:
            return qs

        if self.in_list:
            folders = Folder.objects.filter(id__in=object_ids)
            folder_paths = []
            for f in folders:
                folder_paths.append(f.path)
                continue
            query = Q()
            for path in folder_paths:
                query |= Q(path__startswith=path)

            list_folders = Folder.objects.filter(query).values_list("id",
                                                                    flat=True)

            qs = qs.filter(
                **{f"{self.field_name}_id__in": list_folders}).distinct()
        else:
            for obj_id in object_ids:
                if self.exclude:
                    qs = qs.exclude(**{f"{self.field_name}__id": obj_id})
                else:
                    qs = qs.filter(**{f"{self.field_name}__id": obj_id})

        return qs

class DossierFilter(Filter):
    def __init__(self, exclude=False, in_list=False, field_name=""):
        super().__init__()
        self.exclude = exclude
        self.in_list = in_list
        self.field_name = field_name

    def filter(self, qs, value):
        if not value:
            return qs

        try:
            object_ids = [int(x) for x in value.split(",")]
        except ValueError:
            return qs

        if self.in_list:
            warehouse_paths = Dossier.objects.filter(id__in=object_ids).values_list("path")
            list_warehouses = Dossier.objects.filter(path__startswith = warehouse_paths).values_list("id")
            new_list = [x[0] for x in list_warehouses]
            qs = qs.filter(**{f"{self.field_name}__id__in": new_list}).distinct()
        else:
            for obj_id in object_ids:
                if self.exclude:
                    qs = qs.exclude(**{f"{self.field_name}__id": obj_id})
                else:
                    qs = qs.filter(**{f"{self.field_name}__id": obj_id})

        return qs

class InboxFilter(Filter):
    def filter(self, qs, value):
        if value == "true":
            return qs.filter(tags__is_inbox_tag=True)
        elif value == "false":
            return qs.exclude(tags__is_inbox_tag=True)
        else:
            return qs


class TitleContentFilter(Filter):
    def filter(self, qs, value):
        if value:
            return qs.filter(Q(title__icontains=value) | Q(content__icontains=value))
        else:
            return qs


class SharedByUser(Filter):
    def filter(self, qs, value):
        ctype = ContentType.objects.get_for_model(self.model)
        UserObjectPermission = get_user_obj_perms_model()
        GroupObjectPermission = get_group_obj_perms_model()
        # to 1 because Postgres doesn't like returning > 1 row, but all we care about is > 0
        return (
            qs.filter(
                owner_id=value,
            )
            .annotate(
                num_shared_users=Count(
                    UserObjectPermission.objects.filter(
                        content_type=ctype,
                        object_pk=Cast(OuterRef("pk"), CharField()),
                    ).values("user_id")[:1],
                ),
            )
            .annotate(
                num_shared_groups=Count(
                    GroupObjectPermission.objects.filter(
                        content_type=ctype,
                        object_pk=Cast(OuterRef("pk"), CharField()),
                    ).values("group_id")[:1],
                ),
            )
            .filter(
                Q(num_shared_users__gt=0) | Q(num_shared_groups__gt=0),
            )
            if value is not None
            else qs
        )


class CustomFieldFilterSet(FilterSet):
    class Meta:
        model = CustomField
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
        }


class CustomFieldsFilter(Filter):
    def filter(self, qs, value):
        if value:
            return (
                qs.filter(custom_fields__field__name__icontains=value)
                | qs.filter(custom_fields__value_text__icontains=value)
                | qs.filter(custom_fields__value_bool__icontains=value)
                | qs.filter(custom_fields__value_int__icontains=value)
                | qs.filter(custom_fields__value_float__icontains=value)
                | qs.filter(custom_fields__value_date__icontains=value)
                | qs.filter(custom_fields__value_url__icontains=value)
                | qs.filter(custom_fields__value_monetary__icontains=value)
                | qs.filter(custom_fields__value_document_ids__icontains=value)
            )
        else:
            return qs


class DocumentFilterSet(FilterSet):
    is_tagged = BooleanFilter(
        label="Is tagged",
        field_name="tags",
        lookup_expr="isnull",
        exclude=True,
    )

    tags__id__all = ObjectFilter(field_name="tags")

    tags__id__none = ObjectFilter(field_name="tags", exclude=True)

    tags__id__in = ObjectFilter(field_name="tags", in_list=True)

    correspondent__id__none = ObjectFilter(field_name="correspondent", exclude=True)

    document_type__id__none = ObjectFilter(field_name="document_type", exclude=True)

    archive_font__id__none = ObjectFilter(field_name="archive_font", exclude=True)

    storage_path__id__none = ObjectFilter(field_name="storage_path", exclude=True)

    warehouse__id__none = WarehouseFilter(field_name="warehouse", exclude=True)

    warehouse__id__in = WarehouseFilter(field_name="warehouse", in_list=True)

    warehouse_s__isnull = WarehouseFilter(field_name="warehouse", isnull=True)

    warehouse_s__id__none = WarehouseFilter(field_name="warehouse", exclude=True)

    warehouse_s__id__in = WarehouseFilter(field_name="warehouse", in_list=True)

    warehouse_w__isnull = WarehouseFilter(field_name="warehouse", isnull=True)

    warehouse_w__id__none = WarehouseFilter(field_name="warehouse", exclude=True)

    warehouse_w__id__in = WarehouseFilter(field_name="warehouse", in_list=True)

    folder__id__none = FolderFilter(field_name="folder", exclude=True)

    folder__id__in = FolderFilter(field_name="folder", in_list=True)

    dossier__id__none = DossierFilter(field_name="dossier", exclude=True)

    dossier__id__in = DossierFilter(field_name="dossier", in_list=True)

    is_in_inbox = InboxFilter()

    title_content = TitleContentFilter()

    owner__id__none = ObjectFilter(field_name="owner", exclude=True)

    custom_fields__icontains = CustomFieldsFilter()

    shared_by__id = SharedByUser()


    class Meta:
        model = Document
        fields = {
            "id": ID_KWARGS,
            "title": CHAR_KWARGS,
            "content": CHAR_KWARGS,
            "archive_serial_number": INT_KWARGS,
            "created": DATE_KWARGS,
            "added": DATE_KWARGS,
            "modified": DATE_KWARGS,
            "original_filename": CHAR_KWARGS,
            "checksum": CHAR_KWARGS,
            "correspondent": ["isnull"],
            "correspondent__id": ID_KWARGS,
            "correspondent__name": CHAR_KWARGS,
            "tags__id": ID_KWARGS,
            "tags__name": CHAR_KWARGS,
            "document_type": ["isnull"],
            "document_type__id": ID_KWARGS,
            "document_type__name": CHAR_KWARGS,
            "archive_font": ["isnull"],
            "archive_font__id": ID_KWARGS,
            "archive_font__name": CHAR_KWARGS,
            "storage_path": ["isnull"],
            "storage_path__id": ID_KWARGS,
            "storage_path__name": CHAR_KWARGS,
            "warehouse": ["isnull"],
            "warehouse__id": ID_KWARGS,
            "warehouse__name": CHAR_KWARGS,
            "folder": ["isnull"],
            "folder__id": ID_KWARGS,
            "folder__name": CHAR_KWARGS,
            "owner": ["isnull"],
            "owner__id": ID_KWARGS,
            "custom_fields": ["icontains"],
        }


class LogFilterSet(FilterSet):
    class Meta:
        model = Log
        fields = {"level": INT_KWARGS, "created": DATE_KWARGS, "group": ID_KWARGS}


class ShareLinkFilterSet(FilterSet):
    class Meta:
        model = ShareLink
        fields = {
            "created": DATE_KWARGS,
            "expiration": DATE_KWARGS,
        }


class BackupRecordFilterSet(FilterSet):
    class Meta:
        model = BackupRecord
        fields = {
            "filename": CHAR_KWARGS,
            "created_at": DATE_KWARGS
        }


class ObjectOwnedOrGrantedPermissionsFilter(ObjectPermissionsFilter):
    """
    A filter backend that limits results to those where the requesting user
    has read object level permissions, owns the objects, or objects without
    an owner (for backwards compat)
    """

    def filter_queryset(self, request, queryset, view):
        objects_with_perms = super().filter_queryset(request, queryset, view)
        objects_owned = queryset.filter(owner=request.user)
        objects_unowned = queryset.filter(owner__isnull=True)
        return objects_with_perms | objects_owned | objects_unowned


class FolderOwnedOrAccessibleFilter(BaseFilterBackend):
    """
    Lọc các thư mục mà người dùng:
    - Là chủ sở hữu.
    - Hoặc có quyền truy cập (bao gồm kế thừa từ thư mục cha).
    - Hoặc chưa có chủ sở hữu.
    """

    def filter_queryset(self, request, queryset, view):
        user = request.user

        # Loại quyền: view_folder (mặc định) hoặc change_folder
        perm = getattr(view, 'permission_required', 'view_folder')

        # Lấy danh sách thư mục mà user có quyền (bao gồm kế thừa và loại trừ bị chặn)
        permitted_folders_qs = get_objects_folder_for_user(user, perm,
                                                           with_group_users=True)

        # Trả về các thư mục thỏa mãn:
        # - Được cấp quyền
        # - Hoặc là chủ sở hữu
        # - Hoặc chưa có chủ sở hữu
        return queryset.filter(
            Q(pk__in=permitted_folders_qs.values_list('pk', flat=True)) |
            Q(owner=user) |
            Q(owner__isnull=True)
        ).distinct()





class WarehouseFilterSet(FilterSet):
    class Meta:
        model = Warehouse
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
            "type": CHAR_KWARGS,
            "parent_warehouse": ID_KWARGS,
        }

# class ApprovalFilterSet(FilterSet):
#     class Meta:
#         model = Approval
#         fields = {
#             "id": ID_KWARGS,
#             "ctype": CHAR_KWARGS,
#             "path": CHAR_KWARGS,
#         }

class EdocTaskFilterSet(FilterSet):
    class Meta:
        model = EdocTask
        fields = {
            "id": ID_KWARGS,
            "status": CHAR_KWARGS,
        }

class FolderFilterSet(FilterSet):
    parent_folder__id__none = ObjectFilter(field_name="parent_folder", exclude=True)
    class Meta:
        model = Folder
        fields = {
            "id": ID_KWARGS,
            "name": CHAR_KWARGS,
            "parent_folder__id": ID_KWARGS,
            "path": CHAR_KWARGS,
            "parent_folder": ["isnull"],
            "type": CHAR_KWARGS
        }

class CustomParentDossierIDFilter(NumberFilter):
    def filter(self, qs, value):
        if value is None:
            return qs
        d = qs.filter(id = value).first()
        qs = qs.filter(path__startswith=str(d.path))
        return qs.exclude(id = d.id)

class ObjectOwnedPermissionsFilter(ObjectPermissionsFilter):
    """
    A filter backend that limits results to those where the requesting user
    owns the objects or objects without an owner (for backwards compat)
    """

    def filter_queryset(self, request, queryset, view):
        if request.user.is_superuser:
            return queryset
        objects_owned = queryset.filter(owner=request.user)
        objects_unowned = queryset.filter(owner__isnull=True)
        return objects_owned | objects_unowned

class DossierFilterSet(FilterSet):
    # parent_dossier__id = CustomParentDossierIDFilter(field_name="parent_dossier__id")

    class Meta:
        model = Dossier
        fields = {
            "id": ["exact", "in"],
            "name": ["exact", "icontains"],
            "parent_dossier__id": ["exact", "isnull"],
            "parent_dossier": ["isnull"],
            "type": ["exact", "isnull"],
        }
class DossierFormFilterSet(FilterSet):
    # parent_dossier__id = CustomParentDossierIDFilter(field_name="parent_dossier__id")
    class Meta:
        model = DossierForm
        fields = {
            "id": ["exact", "in"],
            "name": ["exact", "icontains"],
            "type": ["exact", "isnull"],
        }


class ApprovalFilterSet(FilterSet):
    class Meta:
        model = Approval
        fields = {
            "id": ID_KWARGS,
            "status": CHAR_KWARGS,
        }
