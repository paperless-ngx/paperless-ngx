import logging

from django.db.models.manager import BaseManager
from django.utils import timezone
from guardian.shortcuts import remove_perm

from documents.data_models import DocumentMetadataOverrides
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import WorkflowAction
from documents.permissions import set_permissions_for_object
from documents.templating.workflows import parse_w_workflow_placeholders

logger = logging.getLogger("paperless.workflows.mutations")


def _get_annotated_exists_flag(
    action: WorkflowAction,
    attr_name: str,
    manager: BaseManager,
):
    """
    Return a boolean from an annotated flag on the action, falling back to
    evaluating manager.exists().
    """
    return getattr(action, attr_name, manager.exists())


def apply_assignment_to_document(
    action: WorkflowAction,
    document: Document,
    doc_tag_ids: list[int],
    logging_group,
):
    """
    Apply assignment actions to a Document instance.
    """
    has_assign_tags = _get_annotated_exists_flag(
        action,
        "has_assign_tags",
        action.assign_tags,
    )
    if has_assign_tags:
        tag_ids_to_add: set[int] = set()
        for tag in action.assign_tags.all():
            tag_ids_to_add.add(tag.pk)
            tag_ids_to_add.update(int(pk) for pk in tag.get_ancestors_pks())

        doc_tag_ids[:] = list(set(doc_tag_ids) | tag_ids_to_add)

    if action.assign_correspondent:
        document.correspondent = action.assign_correspondent

    if action.assign_document_type:
        document.document_type = action.assign_document_type

    if action.assign_storage_path:
        document.storage_path = action.assign_storage_path

    if action.assign_owner:
        document.owner = action.assign_owner

    if action.assign_title:
        try:
            document.title = parse_w_workflow_placeholders(
                action.assign_title,
                document.correspondent.name if document.correspondent else "",
                document.document_type.name if document.document_type else "",
                document.owner.username if document.owner else "",
                timezone.localtime(document.added),
                document.original_filename or "",
                document.filename or "",
                document.created,
            )
        except Exception:  # pragma: no cover
            logger.exception(
                f"Error occurred parsing title assignment '{action.assign_title}', falling back to original",
                extra={"group": logging_group},
            )

    has_assign_view_users = _get_annotated_exists_flag(
        action,
        "has_assign_view_users",
        action.assign_view_users,
    )
    has_assign_view_groups = _get_annotated_exists_flag(
        action,
        "has_assign_view_groups",
        action.assign_view_groups,
    )
    has_assign_change_users = _get_annotated_exists_flag(
        action,
        "has_assign_change_users",
        action.assign_change_users,
    )
    has_assign_change_groups = _get_annotated_exists_flag(
        action,
        "has_assign_change_groups",
        action.assign_change_groups,
    )

    if any(
        [
            has_assign_view_users,
            has_assign_view_groups,
            has_assign_change_users,
            has_assign_change_groups,
        ],
    ):
        permissions = {
            "view": {
                "users": action.assign_view_users.values_list("id", flat=True),
                "groups": action.assign_view_groups.values_list("id", flat=True),
            },
            "change": {
                "users": action.assign_change_users.values_list("id", flat=True),
                "groups": action.assign_change_groups.values_list("id", flat=True),
            },
        }
        set_permissions_for_object(
            permissions=permissions,
            object=document,
            merge=True,
        )

    has_assign_custom_fields = _get_annotated_exists_flag(
        action,
        "has_assign_custom_fields",
        action.assign_custom_fields,
    )

    if has_assign_custom_fields:
        for field in action.assign_custom_fields.all():
            value_field_name = CustomFieldInstance.get_value_field_name(
                data_type=field.data_type,
            )
            args = {
                value_field_name: action.assign_custom_fields_values.get(
                    str(field.pk),
                    None,
                ),
            }
            # for some reason update_or_create doesn't work here
            instance = CustomFieldInstance.objects.filter(
                field=field,
                document=document,
            ).first()
            if instance and args[value_field_name] is not None:
                setattr(instance, value_field_name, args[value_field_name])
                instance.save()
            elif not instance:
                CustomFieldInstance.objects.create(
                    **args,
                    field=field,
                    document=document,
                )


def apply_assignment_to_overrides(
    action: WorkflowAction,
    overrides: DocumentMetadataOverrides,
):
    """
    Apply assignment actions to DocumentMetadataOverrides.
    """
    has_assign_tags = _get_annotated_exists_flag(
        action,
        "has_assign_tags",
        action.assign_tags,
    )
    if has_assign_tags:
        if overrides.tag_ids is None:
            overrides.tag_ids = []
        tag_ids_to_add: set[int] = set()
        for tag in action.assign_tags.all():
            tag_ids_to_add.add(tag.pk)
            tag_ids_to_add.update(int(pk) for pk in tag.get_ancestors_pks())

        overrides.tag_ids = list(set(overrides.tag_ids) | tag_ids_to_add)

    if action.assign_correspondent:
        overrides.correspondent_id = action.assign_correspondent.pk

    if action.assign_document_type:
        overrides.document_type_id = action.assign_document_type.pk

    if action.assign_storage_path:
        overrides.storage_path_id = action.assign_storage_path.pk

    if action.assign_owner:
        overrides.owner_id = action.assign_owner.pk

    if action.assign_title:
        overrides.title = action.assign_title

    has_assign_view_users = _get_annotated_exists_flag(
        action,
        "has_assign_view_users",
        action.assign_view_users,
    )
    has_assign_view_groups = _get_annotated_exists_flag(
        action,
        "has_assign_view_groups",
        action.assign_view_groups,
    )
    has_assign_change_users = _get_annotated_exists_flag(
        action,
        "has_assign_change_users",
        action.assign_change_users,
    )
    has_assign_change_groups = _get_annotated_exists_flag(
        action,
        "has_assign_change_groups",
        action.assign_change_groups,
    )

    if any(
        [
            has_assign_view_users,
            has_assign_view_groups,
            has_assign_change_users,
            has_assign_change_groups,
        ],
    ):
        overrides.view_users = list(
            set(
                (overrides.view_users or [])
                + list(action.assign_view_users.values_list("id", flat=True)),
            ),
        )
        overrides.view_groups = list(
            set(
                (overrides.view_groups or [])
                + list(action.assign_view_groups.values_list("id", flat=True)),
            ),
        )
        overrides.change_users = list(
            set(
                (overrides.change_users or [])
                + list(action.assign_change_users.values_list("id", flat=True)),
            ),
        )
        overrides.change_groups = list(
            set(
                (overrides.change_groups or [])
                + list(action.assign_change_groups.values_list("id", flat=True)),
            ),
        )

    has_assign_custom_fields = _get_annotated_exists_flag(
        action,
        "has_assign_custom_fields",
        action.assign_custom_fields,
    )

    if has_assign_custom_fields:
        if overrides.custom_fields is None:
            overrides.custom_fields = {}
        overrides.custom_fields.update(
            {
                field.pk: action.assign_custom_fields_values.get(
                    str(field.pk),
                    None,
                )
                for field in action.assign_custom_fields.all()
            },
        )


def apply_removal_to_document(
    action: WorkflowAction,
    document: Document,
    doc_tag_ids: list[int],
):
    """
    Apply removal actions to a Document instance.
    """

    if action.remove_all_tags:
        doc_tag_ids.clear()
    else:
        tag_ids_to_remove: set[int] = set()
        for tag in action.remove_tags.all():
            tag_ids_to_remove.add(tag.pk)
            tag_ids_to_remove.update(int(pk) for pk in tag.get_descendants_pks())

        doc_tag_ids[:] = [t for t in doc_tag_ids if t not in tag_ids_to_remove]

    if action.remove_all_correspondents or (
        document.correspondent
        and action.remove_correspondents.filter(pk=document.correspondent.pk).exists()
    ):
        document.correspondent = None

    if action.remove_all_document_types or (
        document.document_type
        and action.remove_document_types.filter(pk=document.document_type.pk).exists()
    ):
        document.document_type = None

    if action.remove_all_storage_paths or (
        document.storage_path
        and action.remove_storage_paths.filter(pk=document.storage_path.pk).exists()
    ):
        document.storage_path = None

    if action.remove_all_owners or (
        document.owner and action.remove_owners.filter(pk=document.owner.pk).exists()
    ):
        document.owner = None

    if action.remove_all_permissions:
        permissions = {
            "view": {"users": [], "groups": []},
            "change": {"users": [], "groups": []},
        }
        set_permissions_for_object(
            permissions=permissions,
            object=document,
            merge=False,
        )
    has_remove_view_users = _get_annotated_exists_flag(
        action,
        "has_remove_view_users",
        action.remove_view_users,
    )
    has_remove_view_groups = _get_annotated_exists_flag(
        action,
        "has_remove_view_groups",
        action.remove_view_groups,
    )
    has_remove_change_users = _get_annotated_exists_flag(
        action,
        "has_remove_change_users",
        action.remove_change_users,
    )
    has_remove_change_groups = _get_annotated_exists_flag(
        action,
        "has_remove_change_groups",
        action.remove_change_groups,
    )

    if any(
        [
            has_remove_view_users,
            has_remove_view_groups,
            has_remove_change_users,
            has_remove_change_groups,
        ],
    ):
        for user in action.remove_view_users.all():
            remove_perm("view_document", user, document)
        for user in action.remove_change_users.all():
            remove_perm("change_document", user, document)
        for group in action.remove_view_groups.all():
            remove_perm("view_document", group, document)
        for group in action.remove_change_groups.all():
            remove_perm("change_document", group, document)

    has_remove_custom_fields = _get_annotated_exists_flag(
        action,
        "has_remove_custom_fields",
        action.remove_custom_fields,
    )
    if action.remove_all_custom_fields:
        CustomFieldInstance.objects.filter(document=document).hard_delete()
    elif has_remove_custom_fields:
        CustomFieldInstance.objects.filter(
            field__in=action.remove_custom_fields.all(),
            document=document,
        ).hard_delete()


def apply_removal_to_overrides(
    action: WorkflowAction,
    overrides: DocumentMetadataOverrides,
):
    """
    Apply removal actions to DocumentMetadataOverrides.
    """
    if action.remove_all_tags:
        overrides.tag_ids = None
    elif overrides.tag_ids:
        tag_ids_to_remove: set[int] = set()
        for tag in action.remove_tags.all():
            tag_ids_to_remove.add(tag.pk)
            tag_ids_to_remove.update(int(pk) for pk in tag.get_descendants_pks())

        overrides.tag_ids = [t for t in overrides.tag_ids if t not in tag_ids_to_remove]

    if action.remove_all_correspondents or (
        overrides.correspondent_id
        and action.remove_correspondents.filter(pk=overrides.correspondent_id).exists()
    ):
        overrides.correspondent_id = None

    if action.remove_all_document_types or (
        overrides.document_type_id
        and action.remove_document_types.filter(pk=overrides.document_type_id).exists()
    ):
        overrides.document_type_id = None

    if action.remove_all_storage_paths or (
        overrides.storage_path_id
        and action.remove_storage_paths.filter(pk=overrides.storage_path_id).exists()
    ):
        overrides.storage_path_id = None

    if action.remove_all_owners or (
        overrides.owner_id
        and action.remove_owners.filter(pk=overrides.owner_id).exists()
    ):
        overrides.owner_id = None

    has_remove_view_users = _get_annotated_exists_flag(
        action,
        "has_remove_view_users",
        action.remove_view_users,
    )
    has_remove_view_groups = _get_annotated_exists_flag(
        action,
        "has_remove_view_groups",
        action.remove_view_groups,
    )
    has_remove_change_users = _get_annotated_exists_flag(
        action,
        "has_remove_change_users",
        action.remove_change_users,
    )
    has_remove_change_groups = _get_annotated_exists_flag(
        action,
        "has_remove_change_groups",
        action.remove_change_groups,
    )

    if action.remove_all_permissions:
        overrides.view_users = None
        overrides.view_groups = None
        overrides.change_users = None
        overrides.change_groups = None
    elif any(
        [
            has_remove_view_users,
            has_remove_view_groups,
            has_remove_change_users,
            has_remove_change_groups,
        ],
    ):
        if overrides.view_users:
            for user in action.remove_view_users.filter(pk__in=overrides.view_users):
                overrides.view_users.remove(user.pk)
        if overrides.change_users:
            for user in action.remove_change_users.filter(
                pk__in=overrides.change_users,
            ):
                overrides.change_users.remove(user.pk)
        if overrides.view_groups:
            for group in action.remove_view_groups.filter(pk__in=overrides.view_groups):
                overrides.view_groups.remove(group.pk)
        if overrides.change_groups:
            for group in action.remove_change_groups.filter(
                pk__in=overrides.change_groups,
            ):
                overrides.change_groups.remove(group.pk)

    has_remove_custom_fields = _get_annotated_exists_flag(
        action,
        "has_remove_custom_fields",
        action.remove_custom_fields,
    )

    if action.remove_all_custom_fields:
        overrides.custom_fields = None
    elif has_remove_custom_fields and overrides.custom_fields:
        for field in action.remove_custom_fields.filter(
            pk__in=overrides.custom_fields.keys(),
        ):
            overrides.custom_fields.pop(field.pk, None)
