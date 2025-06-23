from itertools import chain

from celery import shared_task
from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from guardian.core import ObjectPermissionChecker
from guardian.models import GroupObjectPermission
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_objects_for_user
from guardian.shortcuts import get_users_with_perms
from guardian.shortcuts import remove_perm
from rest_framework.permissions import BasePermission
from rest_framework.permissions import DjangoObjectPermissions


class EdocObjectPermissions(DjangoObjectPermissions):
    """
    A permissions backend that checks for object-level permissions
    or for ownership.
    """

    perms_map = {
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "POST": ["%(app_label)s.add_%(model_name)s"],
        "PUT": ["%(app_label)s.change_%(model_name)s"],
        "PATCH": ["%(app_label)s.change_%(model_name)s"],
        "DELETE": ["%(app_label)s.delete_%(model_name)s"],
    }

    def has_object_permission(self, request, view, obj):
        print(
            f"Checking object permission for {obj} with request {request.method}")
        if hasattr(obj, "owner") and obj.owner is not None:
            if request.user == obj.owner:
                return True
            else:
                return super().has_object_permission(request, view, obj)
        else:
            return True  # no owner


class EdocAdminPermissions(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff


def get_groups_with_only_permission(obj, codename):
    ctype = ContentType.objects.get_for_model(obj)
    permission = Permission.objects.get(content_type=ctype, codename=codename)
    group_object_perm_group_ids = (
        GroupObjectPermission.objects.filter(
            object_pk=obj.pk,
            content_type=ctype,
        )
        .filter(permission=permission)
        .values_list("group_id")
    )
    return Group.objects.filter(id__in=group_object_perm_group_ids).distinct()


def set_permissions_for_object(permissions: list[str], object, merge: bool = False):
    """
    Set permissions for an object. The permissions are given as a list of strings
    in the format "action_modelname", e.g. "view_document".

    If merge is True, the permissions are merged with the existing permissions and
    no users or groups are removed. If False, the permissions are set to exactly
    the given list of users and groups.
    """

    for action in permissions:
        permission = f"{action}_{object.__class__.__name__.lower()}"
        # users
        users_to_add = User.objects.filter(id__in=permissions[action]["users"])
        users_to_remove = (
            get_users_with_perms(
                object,
                only_with_perms_in=[permission],
                with_group_users=False,
            )
            if not merge
            else User.objects.none()
        )
        if len(users_to_add) > 0 and len(users_to_remove) > 0:
            users_to_remove = users_to_remove.exclude(id__in=users_to_add)
        if len(users_to_remove) > 0:
            for user in users_to_remove:
                remove_perm(permission, user, object)
        if len(users_to_add) > 0:
            for user in users_to_add:
                assign_perm(permission, user, object)
                if action == "change":
                    # change gives view too
                    assign_perm(
                        f"view_{object.__class__.__name__.lower()}",
                        user,
                        object,
                    )
        # groups
        groups_to_add = Group.objects.filter(id__in=permissions[action]["groups"])
        groups_to_remove = (
            get_groups_with_only_permission(
                object,
                permission,
            )
            if not merge
            else Group.objects.none()
        )
        if len(groups_to_add) > 0 and len(groups_to_remove) > 0:
            groups_to_remove = groups_to_remove.exclude(id__in=groups_to_add)
        if len(groups_to_remove) > 0:
            for group in groups_to_remove:
                remove_perm(permission, group, object)
        if len(groups_to_add) > 0:
            for group in groups_to_add:
                assign_perm(permission, group, object)
                if action == "change":
                    # change gives view too
                    assign_perm(
                        f"view_{object.__class__.__name__.lower()}",
                        group,
                        object,
                    )


def get_objects_for_user_owner_aware(user, perms, Model):
    objects_owned = Model.objects.filter(owner=user)
    objects_unowned = Model.objects.filter(owner__isnull=True)
    objects_with_perms = get_objects_for_user(
        user=user,
        perms=perms,
        klass=Model,
        accept_global_perms=False,
    )
    return objects_owned | objects_unowned | objects_with_perms


def has_perms_owner_aware(user, perms, obj):
    checker = ObjectPermissionChecker(user)
    return obj.owner is None or obj.owner == user or checker.has_perm(perms, obj)


def check_user_can_change_folder(user, obj):
    checker = ObjectPermissionChecker(
        user) if user is not None else None
    return (
        obj.owner is None
        or obj.owner == user
        or (
            user is not None
            and checker.has_perm(
            f"change_{obj.__class__.__name__.lower()}", obj)
        )
    )


@shared_task()
def update_view_folder_parent_permissions(folder, permissions):
    from documents.models import Folder
    list_folder_ids = folder.path.rstrip("/").split("/")
    folders_list = Folder.objects.filter(id__in = list_folder_ids)
    permission_copy = permissions
    permission_copy["change"] = {
        "users": [],
        "groups": [],
    }
    for obj in folders_list:
        set_permissions_for_object(
            permissions=permission_copy,
            object=obj,
            merge=True,
        )

def update_view_warehouse_shelf_boxcase_permissions(warehouse, permission_copy):
    from documents.models import Warehouse
    list_warehouse_ids = warehouse.path.split("/")
    warehouses_list = Warehouse.objects.filter(id__in = list_warehouse_ids)


    # Lấy QuerySet từ cả hai quyền
    view_users = permission_copy['view']['users']
    change_users = permission_copy['change']['users']

    # Kết hợp người dùng từ cả hai QuerySet
    # Chuyển đổi thành danh sách và sử dụng chain
    combined_users_list = list(chain(view_users, change_users))

    # Tạo một QuerySet mới từ danh sách đã kết hợp
    combined_users_queryset = User.objects.filter(
        id__in=[user.id for user in combined_users_list])
    permission_copy["view"]["users"]=combined_users_queryset
    view_users = permission_copy['view']['users']
    change_users = permission_copy['change']['users']

    # Kết hợp người dùng từ cả hai QuerySet
    # Chuyển đổi thành danh sách và sử dụng chain
    combined_users_list = list(chain(view_users, change_users))

    # Tạo một QuerySet mới từ danh sách đã kết hợp
    combined_users_queryset = User.objects.filter(
        id__in=[user.id for user in combined_users_list])
    permission_copy["view"]["users"] = combined_users_queryset

    # -----------------------------------------
    view_groups = permission_copy['view']['groups']
    change_groups = permission_copy['change']['groups']

    # Kết hợp nhóm từ cả hai QuerySet
    # Chuyển đổi thành danh sách và sử dụng chain
    combined_groups_list = list(chain(view_groups, change_groups))

    # Tạo một QuerySet mới từ danh sách đã kết hợp
    combined_groups_queryset = Group.objects.filter(
        id__in=[group.id for group in combined_groups_list])

    # Cập nhật lại permission_copy
    permission_copy['view']['groups'] = combined_groups_queryset

    permission_copy["change"] = {
        "users": [],
        "groups": [],
    }


    for obj in warehouses_list:
        set_permissions_for_object(
            permissions=permission_copy,
            object=obj,
            merge=True,
        )


def get_permissions(obj):
    view_codename = f"view_{obj.__class__.__name__.lower()}"
    change_codename = f"change_{obj.__class__.__name__.lower()}"

    return {
        "view": {
            "users": get_users_with_perms(
                obj,
                only_with_perms_in=[view_codename],
                with_group_users=False,
            ).values_list("id", flat=True),
            "groups": get_groups_with_only_permission(
                obj,
                codename=view_codename,
            ).values_list("id", flat=True),
        },
        "change": {
            "users": get_users_with_perms(
                obj,
                only_with_perms_in=[change_codename],
                with_group_users=False,
            ).values_list("id", flat=True),
            "groups": get_groups_with_only_permission(
                obj,
                codename=change_codename,
            ).values_list("id", flat=True),
        },
    }


def set_permissions(permissions, object):
    set_permissions_for_object(permissions, object)


from django.core.cache import cache
from django.db.models import Q

# Constants cho cache
CACHE_TIMEOUT = 60  # thời gian cache (giây)
CACHE_KEYS_KEY = "my_cached_keys"  # key dùng để lưu danh sách các key cache đã set


# --- Các hàm hỗ trợ quản lý key cache ----

def add_cache_key(key):
    """
    Thêm key vào danh sách các key cache được quản lý.
    """
    keys = cache.get(CACHE_KEYS_KEY)
    if keys is None:
        keys = set()
    else:
        # Nếu lưu dưới dạng list, chuyển về set để thao tác
        keys = set(keys)
    keys.add(key)
    # Lưu lại dưới dạng list (vì serialization của cache thường dùng list)
    cache.set(CACHE_KEYS_KEY, list(keys), timeout=CACHE_TIMEOUT)


def set_cache_value(key, value, timeout=CACHE_TIMEOUT):
    """
    Lưu giá trị vào cache với key truyền vào và ghi nhận key đó trong danh sách quản lý.
    """
    cache.set(key, value, timeout=timeout)
    add_cache_key(key)


def get_cache_value(key):
    """
    Lấy giá trị từ cache theo key.
    """
    return cache.get(key)


def delete_cache_pattern(pattern):
    """
    Xóa các key cache mà chứa chuỗi 'pattern', dựa vào danh sách key được quản lý.
    """
    keys = cache.get(CACHE_KEYS_KEY) or []
    # Lọc các key thỏa mãn điều kiện (ở đây đơn giản là kiểm tra xem pattern có trong key hay không)
    keys_to_delete = [k for k in keys if pattern in k]
    for key in keys_to_delete:
        cache.delete(key)
    # Cập nhật lại danh sách key
    remaining_keys = [k for k in keys if k not in keys_to_delete]
    cache.set(CACHE_KEYS_KEY, remaining_keys, timeout=CACHE_TIMEOUT)


# --- Các hàm nghiệp vụ phân quyền (có cache cho query DB) ----

def _get_invalid_paths():
    """
    Query DB lấy danh sách các path của FolderPermission mà các quyền (view, edit, delete, download)
    đều False. Kết quả được cache với key "invalid_folder_paths".
    """
    key = "invalid_folder_paths"
    cached = get_cache_value(key)
    if cached is not None:
        return cached

    from documents.models import FolderPermission
    invalid_paths = list(
        FolderPermission.objects.filter(
            view=False, edit=False, delete=False, download=False
        ).values_list("path", flat=True)
    )
    set_cache_value(key, invalid_paths, timeout=CACHE_TIMEOUT)
    return invalid_paths


def _exclude_invalid_paths_q(invalid_paths):
    """
    Xây dựng Q object để loại trừ các folder có path bắt đầu bởi bất kỳ đường dẫn nào trong invalid_paths.
    """
    q = Q()
    for p in invalid_paths:
        q |= Q(path__startswith=p)
    return q


def get_users_with_perms_folder(obj, perm, with_group_users=False):
    """
    Lấy tập hợp user có quyền (view hoặc edit, tùy biến theo perm) cho folder (obj).
    Ưu tiên lấy quyền từ folder cha gần nhất.

    Nếu with_group_users=True, ngoài user trực tiếp còn lấy user thuộc group có quyền.
    Kết quả được cache theo key dựa trên obj.path, perm và with_group_users.
    """
    from documents.models import FolderPermission
    if perm not in ["view_folder", "change_folder"]:
        raise ValueError("Perm must be 'view_folder' or 'change_folder'.")

    cache_key = f"get_users_with_perms_folder::{obj.path}::{perm}::{with_group_users}"
    cached = get_cache_value(cache_key)
    if cached is not None:
        return cached

    perm_field = "view" if perm == "view_folder" else "edit"
    parts = obj.path.rstrip("/").split("/")
    all_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)]

    invalid_paths = _get_invalid_paths()
    exclude_q = _exclude_invalid_paths_q(invalid_paths)

    fps = FolderPermission.objects.filter(path__in=all_paths).exclude(
        exclude_q)
    # Gom nhóm các bản ghi theo path
    fp_dict = {}
    for fp in fps:
        fp_dict.setdefault(fp.path, []).append(fp)

    users = set()
    for path in all_paths:
        fps_at_path = fp_dict.get(path, [])
        for fp in fps_at_path:
            if fp.user and getattr(fp, perm_field):
                users.add(fp.user)
            if with_group_users and fp.group and getattr(fp, perm_field):
                users.update(fp.group.user_set.all())
        if fps_at_path:
            # Nếu có bản ghi tại một folder, ưu tiên lấy quyền từ đó
            break

    set_cache_value(cache_key, users, timeout=CACHE_TIMEOUT)
    return users


def get_permission_folder(obj):
    """
    Hợp nhất quyền view và edit cho folder (obj) (edit ngụ ý view).
    Kết quả trả về là dict gồm danh sách user và group có quyền.
    Cache kết quả theo key "get_permission_folder::{obj.path}".
    """
    from documents.models import FolderPermission
    cache_key = f"get_permission_folder::{obj.path}"
    cached = get_cache_value(cache_key)
    if cached is not None:
        return cached

    permissions = {
        "view": {"users": set(), "groups": set()},
        "change": {"users": set(), "groups": set()}
    }
    parts = obj.path.rstrip("/").split("/")
    all_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)]

    invalid_paths = _get_invalid_paths()
    exclude_q = _exclude_invalid_paths_q(invalid_paths)

    fps = FolderPermission.objects.filter(path__in=all_paths).exclude(
        exclude_q)
    for fp in fps:
        if fp.user:
            if fp.view:
                permissions["view"]["users"].add(fp.user.id)
            if fp.edit:
                permissions["change"]["users"].add(fp.user.id)
        if fp.group:
            if fp.view:
                permissions["view"]["groups"].add(fp.group.id)
            if fp.edit:
                permissions["change"]["groups"].add(fp.group.id)

    # Edit always implies view permission
    permissions["view"]["users"].update(permissions["change"]["users"])
    permissions["view"]["groups"].update(permissions["change"]["groups"])

    result = {
        "view": {
            "users": list(permissions["view"]["users"]),
            "groups": list(permissions["view"]["groups"])
        },
        "change": {
            "users": list(permissions["change"]["users"]),
            "groups": list(permissions["change"]["groups"])
        }
    }
    set_cache_value(cache_key, result, timeout=CACHE_TIMEOUT)
    print(result)
    return result


def get_permission_folder_for_index(obj):
    """
    Lấy quyền view/edit cho folder (obj) bằng cách tổng hợp quyền từ các folder cha,
    loại trừ các folder không hợp lệ (những folder có tất cả quyền = False) và thêm owner
    của các folder cha vào quyền edit.
    Cache kết quả theo key "get_permission_folder_for_index::{obj.path}".
    """
    from documents.models import Folder, FolderPermission

    cache_key = f"get_permission_folder_for_index::{obj.path}"
    cached = get_cache_value(cache_key)
    if cached is not None:
        return cached

    permissions = {
        "view": {"users": set(), "groups": set()},
        "change": {"users": set(), "groups": set()}
    }
    parts = obj.path.rstrip("/").split("/")
    folder_ids = [int(id_p) for id_p in parts if id_p.isdigit()]
    all_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)]

    invalid_paths = _get_invalid_paths()
    exclude_q = Q()
    for p in invalid_paths:
        exclude_q |= Q(path__startswith=p)

    fps = FolderPermission.objects.filter(path__in=all_paths).exclude(
        exclude_q)
    # Thêm owner của các folder cha vào quyền edit
    owners = Folder.objects.filter(id__in=folder_ids).values_list("owner_id",
                                                                  flat=True)
    permissions["change"]["users"].update(owners)

    for fp in fps:
        if fp.user:
            if fp.view:
                permissions["view"]["users"].add(fp.user.id)
            if fp.edit:
                permissions["change"]["users"].add(fp.user.id)
        if fp.group:
            if fp.view:
                permissions["view"]["groups"].add(fp.group.id)
            if fp.edit:
                permissions["change"]["groups"].add(fp.group.id)

    permissions["view"]["users"].update(permissions["change"]["users"])
    permissions["view"]["groups"].update(permissions["change"]["groups"])

    result = {
        "view": {
            "users": list(permissions["view"]["users"]),
            "groups": list(permissions["view"]["groups"])
        },
        "change": {
            "users": list(permissions["change"]["users"]),
            "groups": list(permissions["change"]["groups"])
        }
    }
    set_cache_value(cache_key, result, timeout=CACHE_TIMEOUT)
    return result


def set_permissions_for_object_folder(obj, perm):
    """
    Cập nhật phân quyền cho folder (obj) theo dữ liệu từ perm.
    Sau khi update DB, invalidate các cache liên quan (xóa cache theo key đã quản lý).
    """
    from documents.models import FolderPermission
    path = obj.path

    # Xóa phân quyền cũ
    FolderPermission.objects.filter(path=path).delete()

    # Tạo mới quyền view
    for user in set(perm["view"]["users"]):
        FolderPermission.objects.create(user=user, path=path, view=True)
    for group in set(perm["view"]["groups"]):
        FolderPermission.objects.create(group=group, path=path, view=True)

    # Cập nhật quyền edit (edit luôn ngụ ý view)
    for user in set(perm["change"]["users"]):
        fp, _ = FolderPermission.objects.get_or_create(user=user, path=path)
        fp.edit = True
        fp.view = True
        fp.save()
    for group in set(perm["change"]["groups"]):
        fp, _ = FolderPermission.objects.get_or_create(group=group, path=path)
        fp.edit = True
        fp.view = True
        fp.save()

    # Invalidate cache sau khi update
    cache.delete("invalid_folder_paths")
    cache.delete(f"get_permission_folder::{obj.path}")
    cache.delete(f"get_permission_folder_for_index::{obj.path}")
    # Xóa cache của các key chứa obj.path cho get_users_with_perms_folder
    delete_cache_pattern(f"get_users_with_perms_folder::{obj.path}::")


def has_perms_owner_aware_for_folder(user, perm, obj):
    """
    Kiểm tra xem user có quyền (view hoặc edit) đối với folder (obj) hay không, bao gồm cả quyền kế thừa.
    Superuser hoặc owner của obj luôn có quyền.
    """
    from documents.models import FolderPermission
    if user.is_superuser or user == getattr(obj, "owner", None):
        return True
    if perm not in ["view_folder", "change_folder"]:
        raise ValueError("Perm must be 'view_folder' or 'change_folder'.")
    perm_field = "view" if perm == "view_folder" else "edit"
    parts = obj.path.rstrip("/").split("/")
    all_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)]
    group_ids = set(user.groups.values_list("id", flat=True))
    invalid_paths = _get_invalid_paths()
    exclude_q = _exclude_invalid_paths_q(invalid_paths)
    fps = FolderPermission.objects.filter(path__in=all_paths).exclude(
        exclude_q)
    for fp in fps:
        if fp.user == user and getattr(fp, perm_field):
            return True
        if fp.group and fp.group.id in group_ids and getattr(fp, perm_field):
            return True
    return False


def get_objects_folder_for_user(user, perm, with_group_users=False):
    """
    Trả về queryset các folder mà user có quyền (view hoặc edit) dựa trên dữ liệu từ FolderPermission.
    Dựa vào các filter theo path (startswith) và các ID trích ra từ path.
    """
    from documents.models import Folder, FolderPermission
    if perm not in ["view_folder", "change_folder"]:
        raise ValueError("Perm must be 'view_folder' or 'change_folder'.")
    if user.is_superuser:
        return Folder.objects.all()
    perm_field = "view" if perm == "view_folder" else "edit"
    q = Q(user=user) & Q(**{perm_field: True})
    if with_group_users:
        group_ids = list(user.groups.values_list("id", flat=True))
        q |= Q(group__in=group_ids) & Q(**{perm_field: True})
    invalid_paths = _get_invalid_paths()
    exclude_q = _exclude_invalid_paths_q(invalid_paths)
    allowed_paths = FolderPermission.objects.filter(q).exclude(
        exclude_q).values_list("path", flat=True)
    allow_q = Q()
    allow_ids = set()
    for p in allowed_paths:
        # Giả sử path có dạng "1/2/3/4/" (các thành phần là số)
        ids = {int(id_str) for id_str in p.rstrip("/").split("/") if
               id_str.isdigit()}
        allow_ids.update(ids)
        allow_q |= Q(path__startswith=p)
    folders = Folder.objects.filter(allow_q | Q(id__in=allow_ids))
    return folders.distinct()
