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

from documents.models import Folder


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


def get_users_with_perms_folder(obj, perm, with_group_users=False):
    from documents.models import FolderPermission
    if perm not in ["view_folder", "change_folder"]:
        raise ValueError("Perm phải là 'view_folder' hoặc 'change_folder'.")

    users = set()
    parts = obj.path.rstrip("/").split("/")
    all_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)]

    # Lấy folder permission đầu tiên từ sâu nhất lên
    fps = (
        FolderPermission.objects
        .filter(path__in=all_paths)
        .prefetch_related(
            'view_users',
            'view_groups__user_set',
            'can_not_view_users',
            'can_not_view_groups__user_set',
            'edit_users',
            'edit_groups__user_set',
            'can_not_edit_users',
            'can_not_edit_groups__user_set',
        )
    )
    fp_dict = {fp.path: fp for fp in fps}

    for path in all_paths:
        fp = fp_dict.get(path)
        if not fp:
            continue

        if perm == "view_folder":
            users.update(fp.view_users.all())
            if with_group_users:
                for group in fp.view_groups.all():
                    users.update(group.user_set.all())

            users.difference_update(fp.can_not_view_users.all())
            if with_group_users:
                for group in fp.can_not_view_groups.all():
                    users.difference_update(group.user_set.all())

        elif perm == "change_folder":
            users.update(fp.edit_users.all())
            if with_group_users:
                for group in fp.edit_groups.all():
                    users.update(group.user_set.all())

            users.difference_update(fp.can_not_edit_users.all())
            if with_group_users:
                for group in fp.can_not_edit_groups.all():
                    users.difference_update(group.user_set.all())

        break  # Dừng ở folder đầu tiên có permission

    return users

def get_permission_folder(obj):
    """
    Lấy danh sách quyền xem/sửa của thư mục, hợp nhất quyền từ tất cả thư mục cha,
    và loại bỏ các user/group bị chặn ở bất kỳ thư mục nào.
    Nếu user/group được gán quyền sửa thì cũng được xem,
    và nếu đang bị chặn xem/sửa thì sẽ được gỡ chặn.
    """
    from documents.models import FolderPermission
    permissions = {
        "view": {"users": set(), "groups": set()},
        "change": {"users": set(), "groups": set()}
    }

    parts = obj.path.rstrip("/").split("/")
    all_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)]

    fps = FolderPermission.objects.filter(path__in=all_paths).prefetch_related(
        'view_users', 'view_groups', 'edit_users', 'edit_groups',
        'can_not_view_users', 'can_not_view_groups',
        'can_not_edit_users', 'can_not_edit_groups',
    )

    for fp in fps:
        permissions["view"]["users"].update(
            user.id for user in fp.view_users.all())
        permissions["view"]["groups"].update(
            group.id for group in fp.view_groups.all())
        permissions["change"]["users"].update(
            user.id for user in fp.edit_users.all())
        permissions["change"]["groups"].update(
            group.id for group in fp.edit_groups.all())

    permissions["view"]["users"].update(permissions["change"]["users"])
    permissions["view"]["groups"].update(permissions["change"]["groups"])

    # Gộp toàn bộ chặn từ các folder (kể cả cha)
    blocked_view_user_ids = set()
    blocked_view_group_ids = set()
    blocked_edit_user_ids = set()
    blocked_edit_group_ids = set()

    for fp in fps:
        blocked_view_user_ids.update(
            user.id for user in fp.can_not_view_users.all())
        blocked_view_group_ids.update(
            group.id for group in fp.can_not_view_groups.all())
        blocked_edit_user_ids.update(
            user.id for user in fp.can_not_edit_users.all())
        blocked_edit_group_ids.update(
            group.id for group in fp.can_not_edit_groups.all())

    # Gỡ chặn nếu có quyền sửa (quyền sửa => quyền xem)
    unblocked_users = permissions["change"]["users"] & blocked_view_user_ids
    unblocked_groups = permissions["change"]["groups"] & blocked_view_group_ids

    blocked_view_user_ids -= unblocked_users
    blocked_view_group_ids -= unblocked_groups
    blocked_edit_user_ids -= unblocked_users
    blocked_edit_group_ids -= unblocked_groups

    # Xoá khỏi quyền nếu bị chặn
    permissions["view"]["users"] -= blocked_view_user_ids
    permissions["view"]["groups"] -= blocked_view_group_ids
    permissions["change"]["users"] -= blocked_edit_user_ids
    permissions["change"]["groups"] -= blocked_edit_group_ids

    return {
        "view": {
            "users": list(permissions["view"]["users"]),
            "groups": list(permissions["view"]["groups"])
        },
        "change": {
            "users": list(permissions["change"]["users"]),
            "groups": list(permissions["change"]["groups"])
        }
    }


def get_permission_folder_for_index(obj):
    """
    Lấy danh sách quyền xem/sửa của thư mục, hợp nhất quyền từ tất cả thư mục cha,
    và loại bỏ các user/group bị chặn ở bất kỳ thư mục nào.
    Nếu user/group được gán quyền sửa thì cũng được xem,
    và nếu đang bị chặn xem/sửa thì sẽ được gỡ chặn.
    Đồng thời thêm owner của các folder cha vào quyền chỉnh sửa.
    """
    from documents.models import Folder, FolderPermission
    permissions = {
        "view": {"users": set(), "groups": set()},
        "change": {"users": set(), "groups": set()}
    }

    # Parse path thành các ID thư mục và path cha
    parts = obj.path.rstrip("/").split("/")
    folder_ids = [int(id_p) for id_p in parts if id_p.isdigit()]
    all_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)]

    # Query FolderPermission
    fps = FolderPermission.objects.filter(path__in=all_paths).prefetch_related(
        'view_users', 'view_groups', 'edit_users', 'edit_groups',
        'can_not_view_users', 'can_not_view_groups',
        'can_not_edit_users', 'can_not_edit_groups',
    )

    # Query Folder owners
    owners = Folder.objects.filter(id__in=folder_ids).values_list("owner_id",
                                                                  flat=True)
    permissions["change"]["users"].update(owners)

    # Gom quyền xem/sửa từ các FolderPermission
    for fp in fps:
        permissions["view"]["users"].update(
            user.id for user in fp.view_users.all())
        permissions["view"]["groups"].update(
            group.id for group in fp.view_groups.all())
        permissions["change"]["users"].update(
            user.id for user in fp.edit_users.all())
        permissions["change"]["groups"].update(
            group.id for group in fp.edit_groups.all())

    # Quyền sửa bao gồm quyền xem
    permissions["view"]["users"].update(permissions["change"]["users"])
    permissions["view"]["groups"].update(permissions["change"]["groups"])

    # Gom danh sách chặn từ các thư mục
    blocked_view_user_ids = set()
    blocked_view_group_ids = set()
    blocked_edit_user_ids = set()
    blocked_edit_group_ids = set()

    for fp in fps:
        blocked_view_user_ids.update(
            user.id for user in fp.can_not_view_users.all())
        blocked_view_group_ids.update(
            group.id for group in fp.can_not_view_groups.all())
        blocked_edit_user_ids.update(
            user.id for user in fp.can_not_edit_users.all())
        blocked_edit_group_ids.update(
            group.id for group in fp.can_not_edit_groups.all())

    # Gỡ chặn nếu có quyền sửa
    unblocked_users = permissions["change"]["users"] & blocked_view_user_ids
    unblocked_groups = permissions["change"]["groups"] & blocked_view_group_ids

    blocked_view_user_ids -= unblocked_users
    blocked_view_group_ids -= unblocked_groups
    blocked_edit_user_ids -= unblocked_users
    blocked_edit_group_ids -= unblocked_groups

    # Xoá khỏi quyền nếu bị chặn
    permissions["view"]["users"] -= blocked_view_user_ids
    permissions["view"]["groups"] -= blocked_view_group_ids
    permissions["change"]["users"] -= blocked_edit_user_ids
    permissions["change"]["groups"] -= blocked_edit_group_ids

    return {
        "view": {
            "users": list(permissions["view"]["users"]),
            "groups": list(permissions["view"]["groups"])
        },
        "change": {
            "users": list(permissions["change"]["users"]),
            "groups": list(permissions["change"]["groups"])
        }
    }




def set_permissions_for_object_folder(obj, perm):
    """
    Gán quyền xem/sửa cho thư mục, bỏ qua nếu user/group đã có quyền ở thư mục cha.
    Nếu user/group từng kế thừa quyền nhưng giờ không còn được phép, thì thêm vào danh sách bị chặn.
    Nếu user/group được gán quyền sửa thì không được chặn quyền xem, và bỏ chặn nếu có.
    """
    from documents.models import FolderPermission, User
    parts = obj.path.rstrip("/").split("/")
    parent_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)
                    if "/".join(parts[:i]) + "/" != obj.path]

    parent_permissions = FolderPermission.objects.filter(
        path__in=parent_paths).prefetch_related(
        'view_users', 'view_groups__user_set',
        'edit_users', 'edit_groups__user_set',
        'can_not_view_users', 'can_not_edit_users',
        'can_not_view_groups', 'can_not_edit_groups',
    )

    inherited = {
        "view": {"users": set(), "groups": set()},
        "change": {"users": set(), "groups": set()}
    }

    for fp in parent_permissions:
        inherited["view"]["users"].update(fp.view_users.all())
        inherited["view"]["groups"].update(fp.view_groups.all())
        inherited["change"]["users"].update(fp.edit_users.all())
        inherited["change"]["groups"].update(fp.edit_groups.all())

    def ensure_user_objects(user_list):
        user_list = list(user_list)
        if user_list and isinstance(user_list[0], int):
            return list(User.objects.filter(id__in=user_list))
        return user_list

    def ensure_group_objects(group_list):
        group_list = list(group_list)
        if group_list and isinstance(group_list[0], int):
            return list(Group.objects.filter(id__in=group_list))
        return group_list

    perm["view"]["users"] = ensure_user_objects(perm["view"]["users"])
    perm["change"]["users"] = ensure_user_objects(perm["change"]["users"])
    perm["view"]["groups"] = ensure_group_objects(perm["view"]["groups"])
    perm["change"]["groups"] = ensure_group_objects(perm["change"]["groups"])

    user_list = list(set(perm["view"]["users"]) | set(perm["change"]["users"]))
    user_to_groups = {u.id: set(u.groups.all()) for u in user_list}

    def is_user_inherited(user, action):
        if user in inherited[action]["users"]:
            return True
        for g in user_to_groups.get(user.id, []):
            if g in inherited[action]["groups"]:
                return True
        return False

    def is_group_inherited(group, action):
        return group in inherited[action]["groups"]

    # Danh sách gán quyền mới (trừ đi quyền đã kế thừa)
    view_users = [u for u in perm["view"]["users"] if
                  not is_user_inherited(u, "view")]
    view_groups = [g for g in perm["view"]["groups"] if
                   not is_group_inherited(g, "view")]
    edit_users = [u for u in perm["change"]["users"] if
                  not is_user_inherited(u, "change")]
    edit_groups = [g for g in perm["change"]["groups"] if
                   not is_group_inherited(g, "change")]

    # Danh sách bị chặn (từng được kế thừa nhưng giờ không còn trong quyền mới)
    inherited_view_users = inherited["view"]["users"]
    inherited_change_users = inherited["change"]["users"]
    inherited_view_groups = inherited["view"]["groups"]
    inherited_change_groups = inherited["change"]["groups"]

    current_view_users = set(perm["view"]["users"])
    current_change_users = set(perm["change"]["users"])
    current_view_groups = set(perm["view"]["groups"])
    current_change_groups = set(perm["change"]["groups"])

    blocked_view_users = inherited_view_users - current_view_users
    blocked_change_users = inherited_change_users - current_change_users
    blocked_view_groups = inherited_view_groups - current_view_groups
    blocked_change_groups = inherited_change_groups - current_change_groups

    # ❗ Nếu được gán quyền chỉnh sửa thì không được chặn xem
    blocked_view_users -= current_change_users
    blocked_view_groups -= current_change_groups

    # Gán vào DB
    fp, _ = FolderPermission.objects.get_or_create(path=obj.path)
    fp.view_users.set(view_users)
    fp.view_groups.set(view_groups)
    fp.edit_users.set(edit_users)
    fp.edit_groups.set(edit_groups)
    fp.can_not_view_users.set(blocked_view_users)
    fp.can_not_edit_users.set(blocked_change_users)
    fp.can_not_view_groups.set(blocked_view_groups)
    fp.can_not_edit_groups.set(blocked_change_groups)
    fp.save()


def has_perms_owner_aware_for_folder(user: User, perm, obj: Folder):
    from documents.models import FolderPermission

    if user.is_superuser or user == obj.owner:
        return True
    if perm not in ["view_folder", "change_folder"]:
        raise ValueError("Perm phải là 'view_folder' hoặc 'change_folder'.")

    parts = obj.path.rstrip("/").split("/")
    all_paths = ["/".join(parts[:i]) + "/" for i in range(len(parts), 0, -1)]
    fps = FolderPermission.objects.filter(path__in=all_paths)
    folders = Folder.objects.filter(path__in=all_paths)
    fp_dict = {fp.path: fp for fp in fps}
    user_group_ids = {g.id for g in user.groups.all()}
    for f in folders:
        if user == f.owner:
            return True
    for path in all_paths:
        fp = fp_dict.get(path)
        if not fp:
            continue

        if perm == "view_folder":
            if (
                user in fp.view_users.all() or
                fp.view_groups.filter(id__in=user_group_ids).exists()
            ):
                if (
                    user in fp.can_not_view_users.all() or
                    fp.can_not_view_groups.filter(
                        id__in=user_group_ids).exists()
                ):
                    return False
                return True

        if perm == "change_folder":
            if (
                user in fp.edit_users.all() or
                fp.edit_groups.filter(id__in=user_group_ids).exists()
            ):
                if (
                    user in fp.can_not_edit_users.all() or
                    fp.can_not_edit_groups.filter(
                        id__in=user_group_ids).exists()
                ):
                    return False
                return True

    return False


from django.db.models import Q


def get_objects_folder_for_user(user: User, perm, with_group_users=False):
    """
    Lấy danh sách thư mục mà user có quyền xem hoặc sửa, kế thừa từ thư mục cha và loại trừ bị chặn.

    :param user: Đối tượng User.
    :param perm: 'view_folder' hoặc 'change_folder'.
    :param with_group_users: Nếu True, sẽ lấy theo cả group của user.
    :return: QuerySet chứa các thư mục user có quyền.
    """
    from documents.models import Folder, FolderPermission
    if perm not in ["view_folder", "change_folder"]:
        raise ValueError("Perm phải là 'view_folder' hoặc 'change_folder'.")
    if user.is_superuser:
        return Folder.objects.all()
    group_ids = list(
        user.groups.values_list("id", flat=True)) if with_group_users else []

    allowed_q = Q()
    blocked_q = Q()

    if perm == "view_folder":
        allowed_q |= Q(view_users=user)
        if group_ids:
            allowed_q |= Q(view_groups__in=group_ids)

        blocked_q |= Q(can_not_view_users=user)
        if group_ids:
            blocked_q |= Q(can_not_view_groups__in=group_ids)

    else:  # perm == "change_folder"
        allowed_q |= Q(edit_users=user)
        if group_ids:
            allowed_q |= Q(edit_groups__in=group_ids)

        blocked_q |= Q(can_not_edit_users=user)
        if group_ids:
            blocked_q |= Q(can_not_edit_groups__in=group_ids)

    # Lấy tất cả path cho phép và bị chặn
    allowed_paths = set(
        FolderPermission.objects.filter(allowed_q).values_list("path",
                                                               flat=True)
    )

    blocked_paths = set(
        FolderPermission.objects.filter(blocked_q).values_list("path",
                                                               flat=True)
    )

    # Truy vấn thư mục dựa trên path được cho phép và loại trừ path bị chặn
    folders = Folder.objects.none()

    folder_paths_owner = Folder.objects.filter(owner=user).values_list('path',
                                                                       flat=True)
    owner_path_q = Q()
    folders_owner = Folder.objects.none()
    if allowed_paths:
        # folders = Folder.objects.all()
        allow_q = Q()
        allow_ids = set()
        for f in folder_paths_owner:
            ids = (int(id) for id in f.rstrip("/").split("/"))
            allow_ids.update(ids)
            owner_path_q |= Q(path__startswith=f)
        folders_owner = Folder.objects.filter(owner_path_q)
        for p in allowed_paths:
            ids = (int(id) for id in p.rstrip("/").split("/"))
            allow_ids.update(ids)
            allow_q |= Q(path__startswith=p)
        folders = Folder.objects.filter(allow_q | Q(id__in=allow_ids))

    if blocked_paths:
        block_q = Q()
        for p in blocked_paths:
            block_q |= Q(path__startswith=p)
        folders = folders.exclude(block_q) | folders_owner

    return folders.distinct()


def get_objects_folder_for_user_owner_aware(user, perm):
    """
    Lấy danh sách thư mục mà user có quyền xem hoặc sửa, bao gồm cả thư mục do user sở hữu.

    :param user: Đối tượng User.
    :param perm: 'view_folder' hoặc 'change_folder'.
    :return: QuerySet chứa các thư mục user có quyền.
    """
    from documents.models import Folder
    owned_folders = Folder.objects.filter(owner=user)
    unowned_folders = Folder.objects.filter(owner__isnull=True)
    folders_with_perms = get_objects_folder_for_user(
        user=user,
        perm=perm,
        with_group_users=False,
    )
    return owned_folders | unowned_folders | folders_with_perms
