from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any
from typing import ClassVar
from typing import Final
from typing import Literal
from typing import TypeAlias
from typing import TypedDict
from typing import TypeGuard
from typing import TypeVar
from typing import cast

from django.contrib.auth.models import Group
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Case
from django.db.models import CharField
from django.db.models import Count
from django.db.models import F
from django.db.models import IntegerField
from django.db.models import Model
from django.db.models import Q
from django.db.models import QuerySet
from django.db.models import Value
from django.db.models import When
from django.db.models.functions import Cast
from django.db.models.functions import Coalesce
from guardian.core import ObjectPermissionChecker
from guardian.models import GroupObjectPermission
from guardian.models import UserObjectPermission
from rest_framework.permissions import BasePermission
from rest_framework.permissions import DjangoObjectPermissions

from documents.models import Document
from documents.versioning import get_root_document

PermissionAction = Literal["view", "change"]
PERMISSION_ACTIONS: Final[tuple[PermissionAction, ...]] = ("view", "change")


class PermissionGrantees(TypedDict):
    """
    The user and group ids holding one permission action directly on an
    object. Users who only hold it through a group are not listed.
    """

    users: list[int]
    groups: list[int]


class PermissionGranteesUpdate(TypedDict, total=False):
    """
    The user and group ids to grant one permission action to. A missing key
    leaves that kind of grant untouched.
    """

    users: Iterable[int]
    groups: Iterable[int]


PermissionsSpec: TypeAlias = Mapping[PermissionAction, PermissionGranteesUpdate]


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


def _is_active_and_authenticated(user: User | None) -> TypeGuard[User]:
    return (
        user is not None
        and getattr(user, "is_active", False)
        and getattr(user, "is_authenticated", False)
    )


def has_global_statistics_permission(user: User | None) -> bool:
    return _is_active_and_authenticated(user) and (
        getattr(user, "is_superuser", False)
        or user.has_perm("paperless.view_global_statistics")
    )


def has_system_status_permission(user: User | None) -> bool:
    return _is_active_and_authenticated(user) and (
        getattr(user, "is_superuser", False)
        or getattr(user, "is_staff", False)
        or user.has_perm("paperless.view_system_monitoring")
    )


def _resolve_permissions(codenames: set[str], ctype: ContentType) -> list[Permission]:
    """
    Resolve ``codenames`` to Permission rows, raising for any that don't exist
    so a bad action name fails loudly instead of granting nothing.
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


def _apply_bulk_permission_entry(
    *,
    perm_model: type[UserObjectPermission] | type[GroupObjectPermission],
    identity_model: type[User] | type[Group],
    identity_field: str,
    ids: Iterable[int],
    codename: str,
    permission_objs: list[Permission],
    ctype: ContentType,
    object_pks: list[str],
    merge: bool,
) -> None:
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

    rows = [
        perm_model(
            content_type=ctype,
            object_pk=pk,
            permission=permission_obj,
            **{f"{identity_field}_id": identity_id},
        )
        for permission_obj in permission_objs
        for pk in object_pks
        for identity_id in add_ids
    ]
    # ignore_conflicts skips grants that already exist (unique constraint).
    perm_model.objects.bulk_create(rows, ignore_conflicts=True, batch_size=1000)


def set_permissions_for_objects(
    permissions: PermissionsSpec,
    model: type[Model],
    pks: QuerySet | list,
    *,
    merge: bool = False,
) -> None:
    """
    Set the view/change grants for every object in ``pks``. With ``merge``,
    the given users and groups are added; without it, each given action's
    direct grants are replaced. Granting change also grants view, and an
    action entry with neither key is left untouched.

    guardian's bulk assign_perm is avoided because it skips the direct row
    for anyone who already has access through a group, so revoking the group
    later would silently remove access that was granted explicitly.
    """
    object_pks = [str(pk) for pk in pks]
    if not object_pks:  # pragma: no cover
        return

    model_name = model.__name__.lower()
    ctype = ContentType.objects.get_for_model(model)

    # Resolve every action before writing, so a bad one can't leave the
    # actions ahead of it applied.
    permissions_by_action: dict[PermissionAction, list[Permission]] = {}
    for action, entry in permissions.items():
        if "users" not in entry and "groups" not in entry:
            continue
        implied_codenames = {f"{action}_{model_name}"}
        if action == "change":
            # change gives view too
            implied_codenames.add(f"view_{model_name}")
        permissions_by_action[action] = _resolve_permissions(
            implied_codenames,
            ctype,
        )

    for action, entry in permissions.items():
        codename = f"{action}_{model_name}"
        permission_objs = permissions_by_action.get(action, [])

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


def get_permission_grantees(
    model: type[Model],
    pks: Iterable[int],
    actions: Iterable[PermissionAction] = PERMISSION_ACTIONS,
) -> dict[int, dict[PermissionAction, PermissionGrantees]]:
    """
    Return the users and groups holding each of ``actions`` directly on each
    object of ``model`` identified by ``pks``, in two queries however many
    objects are asked about.

    Every requested pk and action has an entry, with empty lists where nothing
    is granted. Ids are sorted. Group grants stay group ids rather than being
    expanded to their members, so a caller that copies them keeps access tied
    to current group membership.
    """
    pks = list(pks)
    actions = list(actions)
    model_name = model.__name__.lower()
    action_by_codename: dict[str, PermissionAction] = {
        f"{action}_{model_name}": action for action in actions
    }
    result: dict[int, dict[PermissionAction, PermissionGrantees]] = {
        pk: {action: {"users": [], "groups": []} for action in actions} for pk in pks
    }
    if not pks or not actions:
        return result

    ctype = ContentType.objects.get_for_model(model)
    grant_filter = {
        "content_type": ctype,
        "permission__content_type": ctype,
        "permission__codename__in": list(action_by_codename),
        "object_pk__in": [str(pk) for pk in pks],
    }
    for perm_model, identity_field, key in (
        (UserObjectPermission, "user_id", "users"),
        (GroupObjectPermission, "group_id", "groups"),
    ):
        rows = (
            perm_model.objects.filter(**grant_filter)
            .values_list("object_pk", "permission__codename", identity_field)
            .order_by(identity_field)
        )
        for object_pk, codename, identity_id in rows:
            result[int(object_pk)][action_by_codename[codename]][key].append(
                identity_id,
            )
    return result


def permitted_object_ids(
    user: User | None,
    model: type[Model],
    perm: str,
    *,
    include_deleted: bool = False,
    parent_field: str | None = None,
) -> QuerySet[int]:
    """
    Generic version of ``permitted_document_ids`` for any model with an
    ``owner`` field and guardian object-level permissions. ``include_deleted``
    only has an effect for models exposing a ``global_objects``/``deleted_at``
    soft-delete pattern (currently only ``Document``); for every other model
    it is accepted but has no effect, since those models have no soft-delete
    concept.

    ``parent_field`` names a self-referencing foreign key whose target
    authorizes the row (``Document.root_document``). A row with a parent is
    visible exactly when its parent is, judged by the parent's owner and
    grants, so the row's own owner and grants are ignored.

    Guardian stores ``object_pk`` as a string, so the row key is cast to a
    string and tested against the user's and groups' grants with a single
    uncorrelated ``IN``. Postgres and SQLite build that set once. MariaDB
    evaluates it as an index probe per row, which is cheap because the
    lookups use guardian's unique indexes. Casting every ``object_pk`` to an
    integer instead cannot use an index, and MariaDB cannot materialize it
    inside the owner ``OR``, so it re-scans the user's grants for every row.
    A correlated ``EXISTS`` per grant fixes MariaDB too, but Postgres and
    SQLite re-run it for every row and end up slower than the original. The
    user's groups are matched with an ``IN`` subquery rather than a join
    through the membership table, which SQLite plans badly once the grant
    tables grow.
    """
    has_soft_delete = hasattr(model, "global_objects")
    manager = (
        model.global_objects if include_deleted and has_soft_delete else model.objects
    )
    base_qs = manager.all().only("id", "owner")

    owner_field, key_field = "owner", "pk"
    if parent_field is not None:
        owner_field, key_field = "authorizing_owner", "authorizing_id"
        base_qs = annotate_authorizing_fields(base_qs, parent_field)
    unowned = Q(**{f"{owner_field}__isnull": True})

    if user is None or not getattr(user, "is_authenticated", False):
        return base_qs.filter(unowned).values_list("id", flat=True)

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

    # Both grant sets are compared to the row key as strings, exactly as
    # guardian stores them, and are uncorrelated, so each engine can build the
    # set once instead of probing per row.
    user_keys = UserObjectPermission.objects.filter(
        user=user,
        **perm_filter,
    ).values_list("object_pk", flat=True)
    group_keys = GroupObjectPermission.objects.filter(
        group_id__in=user.groups.values("id"),
        **perm_filter,
    ).values_list("object_pk", flat=True)
    permitted_keys = user_keys.union(group_keys, all=True)

    return (
        base_qs.annotate(permitted_key=Cast(key_field, CharField(max_length=64)))
        .filter(
            Q(**{owner_field: user.pk}) | unowned | Q(permitted_key__in=permitted_keys),
        )
        .values_list("id", flat=True)
    )


ModelT = TypeVar("ModelT", bound=Model)


def annotate_authorizing_fields(
    queryset: QuerySet[ModelT],
    parent_field: str,
) -> QuerySet[ModelT]:
    """
    Annotate each row with ``authorizing_id`` and ``authorizing_owner``: the id
    and owner of the row that authorizes it. A row with a parent (the
    self-referencing foreign key ``parent_field``) is authorized by its parent,
    any other row by itself.
    """
    return queryset.annotate(
        authorizing_id=Coalesce(f"{parent_field}_id", "id"),
        authorizing_owner=Case(
            When(**{f"{parent_field}_id__isnull": True}, then=F("owner_id")),
            default=F(f"{parent_field}__owner_id"),
            output_field=IntegerField(),
        ),
    )


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


def user_is_active_superuser(user: User | None) -> bool:
    """
    True only for an active, authenticated superuser.
    """
    return user is not None and user_is_unrestricted(user)


def restrict_queryset_to_owner_visible(
    queryset: QuerySet[ModelT],
    user: User | None,
    perm: str,
) -> QuerySet[ModelT]:
    """
    Like ``restrict_queryset_to_visible``, but ``user=None`` sees only unowned
    rows (``permitted_object_ids(None, ...)`` semantics) instead of every row.
    See ``user_is_active_superuser``.
    """
    if user_is_active_superuser(user):
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

    A version is authorized by its root document, so a version's own owner and
    grants never matter.
    """
    return permitted_object_ids(
        user,
        Document,
        perm,
        include_deleted=include_deleted,
        parent_field="root_document",
    )


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
                       or a simple (already resolved) queryset of ids. Keep
                       the list small: it is embedded in the statement as
                       literal parameters.
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


def has_perms_owner_aware(user, perms, obj):
    """
    Legacy slow path (guardian-backed) single-object permission check.

    The queryset-filtering side of this migrated onto
    ``PermittedObjectsFilter``/``permitted_object_ids()``, but this
    single-object check still has many production callers. Several callers
    remain across ``documents/``, ``paperless_mail/``, and ``paperless_ai/``
    -- grep for this function name before removing it.

    A document version is authorized by its root document, like in
    ``permitted_document_ids``, so a version's own owner and grants never
    matter. Fetch the root with ``select_related("root_document__owner")`` to
    avoid extra queries.
    """
    if isinstance(obj, Document):
        obj = get_root_document(obj)
    checker = ObjectPermissionChecker(user)
    return obj.owner is None or obj.owner == user or checker.has_perm(perms, obj)


# HEAD is deliberately absent: GlobalPermissionsByMethod checks it against GET.
MappedMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


class GlobalPermissionsByMethod(BasePermission):
    """
    Requires the global (model-level) permissions listed in ``perms_map`` for
    the request's HTTP method. HEAD is checked against the ``"GET"`` entry,
    since DRF runs the GET handler for it. A method missing from
    ``perms_map`` is denied.
    """

    perms_map: ClassVar[Mapping[MappedMethod, Sequence[str]]]

    def has_permission(self, request: Any, view: Any) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        method = "GET" if request.method == "HEAD" else request.method
        # An unknown method is not a MappedMethod, but .get() returns None for
        # it, so it is still denied.
        perms = self.perms_map.get(cast("MappedMethod", method))
        return perms is not None and request.user.has_perms(perms)


class ViewDocumentsPermissions(GlobalPermissionsByMethod):
    """
    Permissions class that checks for model permissions for only viewing Documents.
    """

    perms_map = {
        "OPTIONS": ["documents.view_document"],
        "GET": ["documents.view_document"],
        "POST": ["documents.view_document"],
    }


class TrashPermissions(GlobalPermissionsByMethod):
    """Check the global document permission for each trash operation."""

    perms_map = {
        "OPTIONS": ["documents.view_document"],
        "GET": ["documents.view_document"],
        "POST": ["documents.delete_document"],
    }


class PaperlessNotePermissions(GlobalPermissionsByMethod):
    """
    Permissions class that checks for model permissions for Notes.
    """

    perms_map = {
        "OPTIONS": ["documents.view_note", "documents.view_document"],
        "GET": ["documents.view_note", "documents.view_document"],
        "POST": [
            "documents.add_note",
            "documents.view_document",
            "documents.change_document",
        ],
        "DELETE": [
            "documents.delete_note",
            "documents.view_document",
            "documents.change_document",
        ],
    }


class AcknowledgeTasksPermissions(GlobalPermissionsByMethod):
    """
    Permissions class that checks for model permissions for acknowledging tasks.
    """

    perms_map = {
        "OPTIONS": ["documents.change_paperlesstask"],
        "POST": ["documents.change_paperlesstask"],
    }
