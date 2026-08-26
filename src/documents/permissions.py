from typing import Any
from typing import TypeVar

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
        return request.user.is_active and request.user.is_staff


def has_global_statistics_permission(user: User | None) -> bool:
    if (
        user is None
        or not getattr(user, "is_active", False)
        or not getattr(user, "is_authenticated", False)
    ):
        return False

    return getattr(user, "is_superuser", False) or user.has_perm(
        "paperless.view_global_statistics",
    )


def has_system_status_permission(user: User | None) -> bool:
    if (
        user is None
        or not getattr(user, "is_active", False)
        or not getattr(user, "is_authenticated", False)
    ):
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


def _resolve_permissions(codenames: set[str], ctype: ContentType) -> list[Permission]:
    """
    Resolves `codenames` to Permission rows, raising like the single-object
    assign_perm() this bulk path replaces does (via a `.get()` internally)
    if any codename doesn't exist -- e.g. a client-supplied action name that
    was never validated (BulkEditObjectsSerializer._validate_permissions
    calls validate_set_permissions() only for its side-effecting id checks
    and discards the filtered dict it returns, so an unrecognized action key
    reaches this function as-is). A plain `.filter()` with no existence
    check would otherwise silently build zero rows and no-op instead of
    reporting the bad input.
    """
    permission_objs = list(
        Permission.objects.filter(content_type=ctype, codename__in=codenames),
    )
    missing = codenames - {p.codename for p in permission_objs}
    if missing:
        raise Permission.DoesNotExist(
            f"Permission matching query does not exist for codename(s): "
            f"{', '.join(sorted(missing))}",
        )
    return permission_objs


# Target number of permission rows to build in Python before handing them to
# bulk_create -- keeps peak memory bounded for a large "apply to all" call,
# independent of bulk_create's own batch_size (which only caps the size of
# each INSERT statement, not how many row objects exist in memory at once).
_PERMISSION_ROW_CHUNK_SIZE = 5000


def _apply_bulk_permission_entry(
    *,
    perm_model: type[UserObjectPermission] | type[GroupObjectPermission],
    identity_model: type[User] | type[Group],
    identity_field: str,
    ids: list[int],
    codename: str,
    permission_objs: list[Permission],
    ctype: ContentType,
    object_pks: list[str],
    merge: bool,
) -> None:
    # Only the ids are needed to build permission rows (via `<field>_id=`),
    # so avoid fetching full User/Group rows for identities that may not
    # even end up being granted anything new.
    add_ids = set(
        identity_model.objects.filter(id__in=ids).values_list("id", flat=True),
    )

    if not merge:
        existing_ids = set(
            perm_model.objects.filter(
                content_type=ctype,
                object_pk__in=object_pks,
                permission__codename=codename,
            )
            .values_list(f"{identity_field}_id", flat=True)
            .distinct(),
        )
        remove_ids = existing_ids - add_ids
        if remove_ids:
            perm_model.objects.filter(
                content_type=ctype,
                object_pk__in=object_pks,
                permission__codename=codename,
                **{f"{identity_field}_id__in": remove_ids},
            ).delete()

    if not add_ids:
        return

    rows_per_pk = len(permission_objs) * len(add_ids)
    pks_per_chunk = max(1, _PERMISSION_ROW_CHUNK_SIZE // rows_per_pk)
    for start in range(0, len(object_pks), pks_per_chunk):
        pk_chunk = object_pks[start : start + pks_per_chunk]
        rows = [
            perm_model(
                content_type=ctype,
                object_pk=pk,
                permission=permission_obj,
                **{f"{identity_field}_id": identity_id},
            )
            for permission_obj in permission_objs
            for pk in pk_chunk
            for identity_id in add_ids
        ]
        # ignore_conflicts skips only rows that already exist as an exact
        # (identity, permission, object) match -- the same de-dup the
        # underlying (user|group, permission, object_pk) unique constraint
        # already enforces for the single-object assign_perm() this
        # replaces, so it doesn't change what counts as "already granted".
        # batch_size caps how many rows go into a single INSERT so a huge
        # chunk doesn't build one enormous statement.
        perm_model.objects.bulk_create(rows, ignore_conflicts=True, batch_size=1000)


def set_permissions_for_objects(
    permissions: dict,
    model: type[Model],
    pks: QuerySet | list,
    *,
    merge: bool = False,
) -> None:
    """
    Bulk equivalent of set_permissions_for_object: applies the same
    permission changes to every object identified by `pks` at once.

    Takes a model + pks (rather than model instances) deliberately -- the
    permission rows built below only ever need `pk`, `content_type`, and
    identity ids, so callers shouldn't have to fetch full rows (with every
    other field) just to hand them to this function.

    Deliberately does not use guardian's queryset/list-aware assign_perm:
    passing a list as the object routes to bulk_assign_perm, which skips
    creating a direct permission row for anyone who already has the
    permission via ANY group membership (it checks
    ObjectPermissionChecker.has_perm, which is group-inheritance-aware) --
    unlike the single-object assign_perm this replaces, which always
    ensures a direct row via get_or_create regardless of group-derived
    access. Losing that guarantee would mean a later revocation of the
    group's grant silently strips access an admin explicitly asked to be
    direct. Bulk-creating rows straight against the permission models
    instead (see _apply_bulk_permission_entry) preserves the original
    always-create-a-direct-row semantics while still batching every object
    and every identity into one query per action, rather than one query per
    (object, user) pair.
    """
    object_pks = [str(pk) for pk in pks]
    if not object_pks:  # pragma: no cover
        return

    model_name = model.__name__.lower()
    ctype = ContentType.objects.get_for_model(model)

    for action, entry in permissions.items():
        codename = f"{action}_{model_name}"
        implied_codenames = {codename}
        if action == "change":
            # change gives view too
            implied_codenames.add(f"view_{model_name}")

        # Resolved once per action (not once per users/groups branch) and
        # shared between both below -- also where an unrecognized action
        # name (see _resolve_permissions) is caught.
        permission_objs = (
            _resolve_permissions(implied_codenames, ctype)
            if "users" in entry or "groups" in entry
            else []
        )

        if "users" in entry:
            _apply_bulk_permission_entry(
                perm_model=UserObjectPermission,
                identity_model=User,
                identity_field="user",
                ids=entry["users"],
                codename=codename,
                permission_objs=permission_objs,
                ctype=ctype,
                object_pks=object_pks,
                merge=merge,
            )

        if "groups" in entry:
            _apply_bulk_permission_entry(
                perm_model=GroupObjectPermission,
                identity_model=Group,
                identity_field="group",
                ids=entry["groups"],
                codename=codename,
                permission_objs=permission_objs,
                ctype=ctype,
                object_pks=object_pks,
                merge=merge,
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

    # Deactivated users get nothing, deactivated superusers included, so this
    # has to come before the superuser shortcut. guardian's
    # ObjectPermissionChecker denies inactive users, but get_objects_for_user
    # (the pattern this replaces) does not, so it would not be inherited.
    if not getattr(user, "is_active", False):
        return base_qs.none().values_list("id", flat=True)

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


ModelT = TypeVar("ModelT", bound=Model)


def user_is_unrestricted(user: User | None) -> bool:
    """
    True when ``user`` means "no restriction at all" (an absent user, or an
    *active* superuser) without needing a database check to know it.

    ``permitted_object_ids(None, ...)`` itself means the much narrower "only
    unowned rows", which is NOT the same thing as "no user filtering
    requested", so callers must special-case this before ever calling it.
    A deactivated superuser is deliberately NOT unrestricted here, matching
    permitted_object_ids's own is_active-before-is_superuser ordering.

    Callers that can avoid a database round trip entirely when this is true
    (e.g. checking a single already-loaded object's visibility rather than
    filtering a queryset) should do so via this function directly, rather
    than through restrict_queryset_to_visible() below.
    """
    if user is None:
        return True
    return (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_superuser", False)
    )


def restrict_queryset_to_visible(
    queryset: QuerySet[ModelT],
    user: User | None,
    perm: str,
) -> QuerySet[ModelT]:
    """
    Restrict ``queryset`` to the rows ``user`` may see with ``perm``.

    Delegates the visibility check to the database as a
    ``WHERE id IN (subquery)`` rather than materializing the full
    permitted-id set into a Python collection first: a caller that only
    needs to check a small handful of rows (a resolved-id list, a few
    RAG-neighbour candidate ids) never pays for scanning or holding the
    installation's entire taxonomy in memory to do it.

    Returns ``queryset`` unchanged for user_is_unrestricted(user); every
    other case is delegated to ``permitted_object_ids`` rather than
    re-deciding the ordering here.
    """
    if user_is_unrestricted(user):
        return queryset
    return queryset.filter(pk__in=permitted_object_ids(user, queryset.model, perm))


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

    Legacy slow path (guardian-backed, O(n) style permission resolution).
    Most queryset-filtering call sites have migrated onto
    ``PermittedObjectsFilter``/``permitted_object_ids()``, but this function
    is kept because production callers still remain. Several callers remain
    across ``documents/``, ``paperless_mail/``, and ``paperless_ai/`` --
    grep for this function name before removing it.
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
    """
    Legacy slow path (guardian-backed) single-object permission check.

    The queryset-filtering side of this migrated onto
    ``PermittedObjectsFilter``/``permitted_object_ids()``, but this
    single-object check still has many production callers. Several callers
    remain across ``documents/``, ``paperless_mail/``, and ``paperless_ai/``
    -- grep for this function name before removing it.
    """
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
