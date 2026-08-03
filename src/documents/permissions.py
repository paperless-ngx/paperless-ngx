from typing import Any

from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Case
from django.db.models import Count
from django.db.models import IntegerField
from django.db.models import Model
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import Cast
from guardian.core import ObjectPermissionChecker
from guardian.models import GroupObjectPermission
from guardian.models import UserObjectPermission
from guardian.shortcuts import assign_perm
from guardian.shortcuts import get_objects_for_user
from guardian.shortcuts import get_users_with_perms
from guardian.shortcuts import remove_perm
from rest_framework.permissions import BasePermission
from rest_framework.permissions import DjangoObjectPermissions

from documents.models import Document


class PaperlessObjectPermissions(DjangoObjectPermissions):
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
        if hasattr(obj, "owner") and obj.owner is not None:
            if request.user == obj.owner:
                return True
            else:
                return super().has_object_permission(request, view, obj)
        else:
            return True  # no owner


class PaperlessAdminPermissions(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff


def has_global_statistics_permission(user: User | None) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False

    return getattr(user, "is_superuser", False) or user.has_perm(
        "paperless.view_global_statistics",
    )


def has_system_status_permission(user: User | None) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False

    return (
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or user.has_perm("paperless.view_system_monitoring")
    )


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


def set_permissions_for_object(
    permissions: dict,
    object,
    *,
    merge: bool = False,
) -> None:
    """
    Set permissions for an object. The permissions are given as a mapping of actions
    to a dict of user / group id lists, e.g.
    {"view": {"users": [1], "groups": [2]}, "change": {"users": [], "groups": []}}.

    If merge is True, the permissions are merged with the existing permissions and
    no users or groups are removed. If False, the permissions are set to exactly
    the given list of users and groups.
    """

    for action, entry in permissions.items():
        permission = f"{action}_{object.__class__.__name__.lower()}"
        if "users" in entry:
            # users
            users_to_add = User.objects.filter(id__in=entry["users"])
            users_to_remove = (
                get_users_with_perms(
                    object,
                    only_with_perms_in=[permission],
                    with_group_users=False,
                )
                if not merge
                else User.objects.none()
            )
            if users_to_add.exists() and users_to_remove.exists():
                users_to_remove = users_to_remove.exclude(id__in=users_to_add)
            if users_to_remove.exists():
                for user in users_to_remove:
                    remove_perm(permission, user, object)
            if users_to_add.exists():
                for user in users_to_add:
                    assign_perm(permission, user, object)
                    if action == "change":
                        # change gives view too
                        assign_perm(
                            f"view_{object.__class__.__name__.lower()}",
                            user,
                            object,
                        )
        if "groups" in entry:
            # groups
            groups_to_add = Group.objects.filter(id__in=entry["groups"])
            groups_to_remove = (
                get_groups_with_only_permission(
                    object,
                    permission,
                )
                if not merge
                else Group.objects.none()
            )
            if groups_to_add.exists() and groups_to_remove.exists():
                groups_to_remove = groups_to_remove.exclude(id__in=groups_to_add)
            if groups_to_remove.exists():
                for group in groups_to_remove:
                    remove_perm(permission, group, object)
            if groups_to_add.exists():
                for group in groups_to_add:
                    assign_perm(permission, group, object)
                    if action == "change":
                        # change gives view too
                        assign_perm(
                            f"view_{object.__class__.__name__.lower()}",
                            group,
                            object,
                        )


def permitted_object_ids(
    user: User | None,
    model: type[Model],
    perm: str,
    *,
    include_deleted: bool = False,
) -> QuerySet[int]:
    """
    Generic version of ``permitted_document_ids`` for any model with an
    ``owner`` field and guardian object-level permissions. ``include_deleted``
    only has an effect for models exposing a ``global_objects``/``deleted_at``
    soft-delete pattern (currently only ``Document``); for every other model
    it is accepted but has no effect, since those models have no soft-delete
    concept.
    """
    has_soft_delete = hasattr(model, "global_objects")
    manager = (
        model.global_objects if include_deleted and has_soft_delete else model.objects
    )
    base_qs = manager.all().only("id", "owner")

    if user is None or not getattr(user, "is_authenticated", False):
        return base_qs.filter(owner__isnull=True).values_list("id", flat=True)

    if getattr(user, "is_superuser", False):
        return base_qs.values_list("id", flat=True)

    # Guardian's UserObjectPermission/GroupObjectPermission always store a bare
    # codename, but has_perm()-style callers commonly pass the qualified
    # "app_label.codename" form. content_type already disambiguates the
    # codename, so just drop any prefix rather than silently under-permitting.
    perm = perm.rsplit(".", 1)[-1]

    content_type = ContentType.objects.get_for_model(model)
    perm_filter = {
        "permission__codename": perm,
        "permission__content_type": content_type,
    }

    user_perm_ids = (
        UserObjectPermission.objects.filter(user=user, **perm_filter)
        .annotate(object_pk_int=Cast("object_pk", IntegerField()))
        .values_list("object_pk_int", flat=True)
    )
    group_perm_ids = (
        GroupObjectPermission.objects.filter(group__user=user, **perm_filter)
        .annotate(object_pk_int=Cast("object_pk", IntegerField()))
        .values_list("object_pk_int", flat=True)
    )
    permitted_ids = user_perm_ids.union(group_perm_ids)

    return base_qs.filter(
        Q(owner=user) | Q(owner__isnull=True) | Q(id__in=permitted_ids),
    ).values_list("id", flat=True)


def permitted_document_ids(
    user: User | None,
    *,
    perm: str = "view_document",
    include_deleted: bool = False,
) -> QuerySet[int]:
    """
    Document-specific convenience wrapper around ``permitted_object_ids``.
    Return a queryset of document IDs the user has ``perm`` on (default
    ``"view_document"``). By default limited to non-deleted documents; pass
    ``include_deleted=True`` for callers that need to check permission on
    soft-deleted documents (e.g. trash restore). This intentionally avoids
    ``get_objects_for_user`` to keep the subquery small and index-friendly.
    """
    return permitted_object_ids(user, Document, perm, include_deleted=include_deleted)


def get_document_count_filter_for_user(user, related_name: str = "documents"):
    """
    Return the Q object used to filter document counts for the given user.

    The filter is expressed as an ``id__in`` against a small subquery of permitted
    document IDs to keep the generated SQL simple and avoid large OR clauses.

    ``related_name`` is the ORM path from the annotated model to Document (e.g.
    ``"documents"`` for Tag's direct M2M, or ``"fields__document"`` for CustomField,
    which only reaches Document via the CustomFieldInstance through-model).
    """

    if getattr(user, "is_superuser", False):
        # Superuser: no permission filtering needed
        return Q(**{f"{related_name}__deleted_at__isnull": True})

    permitted_ids = permitted_document_ids(user)
    return Q(**{f"{related_name}__id__in": permitted_ids})


def annotate_document_count_by_ids(
    queryset: QuerySet[Any],
    through_model: Any,
    related_object_field: str,
    document_ids: Any,
    target_field: str = "document_id",
) -> QuerySet[Any]:
    """
    Annotate a queryset with a document count for a relation to Document that
    goes through an M2M/through-model table (e.g. Tag via
    ``Document.tags.through``, or CustomField via ``CustomFieldInstance``),
    for an explicit, already-resolved set of document ids.

    Counts are computed via a single, independent GROUP BY over the relation
    table -- with the id filter expressed as a plain ``WHERE`` rather than an
    aggregate ``FILTER`` -- then injected via ``Case``/``When``. This
    deliberately avoids two slower alternatives found while building this:

    - A per-outer-row correlated subquery (one execution per row of the
      annotated queryset): fine at a handful of rows, catastrophic once the
      queryset has hundreds/thousands of rows.
    - ``Count(..., filter=Q(id__in=document_ids), distinct=True)`` applied
      directly to the M2M relation: Postgres can fail to plan the ``id__in``
      check as a semi-join and instead re-checks subquery membership once per
      row of the (much larger) M2M join -- worse than the correlated subquery.

    Aggregation is restricted to rows whose ``related_object_field`` is one of
    ``queryset``'s pks, so passing a subset (e.g. a handful of tag descendants)
    doesn't pay the cost of counting for every row matching ``document_ids``.

    Args:
        queryset: base queryset to annotate (must contain pk)
        through_model: model representing the relation (e.g., Document.tags.through
                       or CustomFieldInstance)
        related_object_field: field on the relation pointing back to queryset pk
        document_ids: the document ids to count against -- a concrete list/set,
                       or a simple (already resolved) queryset of ids. Callers
                       that need this filtered by a complex condition (e.g. a
                       permission check) should resolve it to a concrete list
                       first if the same ids will be reused across multiple
                       calls, rather than passing the complex queryset itself
                       into each -- see ``_get_selection_data_for_queryset``.
        target_field: field on the relation pointing to Document id
    """

    counts = (
        through_model.objects.filter(
            **{
                f"{related_object_field}__in": queryset.values("pk"),
                f"{target_field}__in": document_ids,
            },
        )
        .values(related_object_field)
        .annotate(c=Count(target_field, distinct=True))
    )
    counts_by_pk = {row[related_object_field]: row["c"] for row in counts}

    if not counts_by_pk:
        return queryset.annotate(
            document_count=Value(0, output_field=IntegerField()),
        )

    return queryset.annotate(
        document_count=Case(
            *(When(pk=pk, then=Value(count)) for pk, count in counts_by_pk.items()),
            default=Value(0),
            output_field=IntegerField(),
        ),
    )


def annotate_document_count_for_related_queryset(
    queryset: QuerySet[Any],
    through_model: Any,
    related_object_field: str,
    target_field: str = "document_id",
    user: User | None = None,
) -> QuerySet[Any]:
    """
    Same as ``annotate_document_count_by_ids``, but resolves the document ids
    from the given user's view permissions rather than taking them directly.
    """

    return annotate_document_count_by_ids(
        queryset,
        through_model=through_model,
        related_object_field=related_object_field,
        document_ids=permitted_document_ids(user),
        target_field=target_field,
    )


def get_objects_for_user_owner_aware(
    user: User | None,
    perms: str | list[str],
    Model: Any,
    *,
    include_deleted: bool = False,
) -> QuerySet[Any]:
    """
    Returns objects the user owns, are unowned, or has explicit perms.
    When include_deleted is True, soft-deleted items are also included.
    """
    manager = (
        Model.global_objects
        if include_deleted and hasattr(Model, "global_objects")
        else Model.objects
    )

    objects_owned = manager.filter(owner=user)
    objects_unowned = manager.filter(owner__isnull=True)
    objects_with_perms = get_objects_for_user(
        user=user,
        perms=perms,
        klass=manager.all(),
        accept_global_perms=False,
    )
    return objects_owned | objects_unowned | objects_with_perms


def has_perms_owner_aware(user, perms, obj):
    checker = ObjectPermissionChecker(user)
    return obj.owner is None or obj.owner == user or checker.has_perm(perms, obj)


class ViewDocumentsPermissions(BasePermission):
    """
    Permissions class that checks for model permissions for only viewing Documents.
    """

    perms_map = {
        "OPTIONS": ["documents.view_document"],
        "GET": ["documents.view_document"],
        "POST": ["documents.view_document"],
    }

    def has_permission(self, request, view):
        if not request.user or (not request.user.is_authenticated):  # pragma: no cover
            return False

        return request.user.has_perms(self.perms_map.get(request.method, []))


class PaperlessNotePermissions(BasePermission):
    """
    Permissions class that checks for model permissions for Notes.
    """

    perms_map = {
        "OPTIONS": ["documents.view_note"],
        "GET": ["documents.view_note"],
        "POST": ["documents.add_note"],
        "DELETE": ["documents.delete_note"],
    }

    def has_permission(self, request, view):
        if not request.user or (not request.user.is_authenticated):  # pragma: no cover
            return False

        perms = self.perms_map[request.method]

        return request.user.has_perms(perms)


class AcknowledgeTasksPermissions(BasePermission):
    """
    Permissions class that checks for model permissions for acknowledging tasks.
    """

    perms_map = {
        "POST": ["documents.change_paperlesstask"],
    }

    def has_permission(self, request: Any, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:  # pragma: no cover
            return False

        perms = self.perms_map.get(request.method, [])

        return request.user.has_perms(perms)
