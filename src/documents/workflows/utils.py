import ipaddress
import logging
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone
from guardian.shortcuts import remove_perm

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.mail import EmailAttachment
from documents.mail import send_email
from documents.models import Correspondent
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.permissions import set_permissions_for_object
from documents.templating.workflows import parse_w_workflow_placeholders

logger = logging.getLogger("paperless.workflows")


def get_workflows_for_trigger(
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
    workflow_to_run: Workflow | None = None,
):
    """
    Return workflows relevant to a trigger. If a specific workflow is given,
    wrap it in a list; otherwise fetch enabled workflows for the trigger with
    the prefetches used by the runner.
    """
    if workflow_to_run is not None:
        return [workflow_to_run]

    return (
        Workflow.objects.filter(enabled=True, triggers__type=trigger_type)
        .prefetch_related(
            "actions",
            "actions__assign_view_users",
            "actions__assign_view_groups",
            "actions__assign_change_users",
            "actions__assign_change_groups",
            "actions__assign_custom_fields",
            "actions__remove_tags",
            "actions__remove_correspondents",
            "actions__remove_document_types",
            "actions__remove_storage_paths",
            "actions__remove_custom_fields",
            "actions__remove_owners",
            "triggers",
        )
        .order_by("order")
        .distinct()
    )


def apply_assignment_to_document(
    action: WorkflowAction,
    document: Document,
    doc_tag_ids: list[int],
    logging_group,
):
    """
    Apply assignment actions to a Document instance.
    """
    if action.assign_tags.exists():
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
        except Exception:
            logger.exception(
                f"Error occurred parsing title assignment '{action.assign_title}', falling back to original",
                extra={"group": logging_group},
            )

    if any(
        [
            action.assign_view_users.exists(),
            action.assign_view_groups.exists(),
            action.assign_change_users.exists(),
            action.assign_change_groups.exists(),
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

    if action.assign_custom_fields.exists():
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
    if action.assign_tags.exists():
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

    if any(
        [
            action.assign_view_users.exists(),
            action.assign_view_groups.exists(),
            action.assign_change_users.exists(),
            action.assign_change_groups.exists(),
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

    if action.assign_custom_fields.exists():
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
    elif any(
        [
            action.remove_view_users.exists(),
            action.remove_view_groups.exists(),
            action.remove_change_users.exists(),
            action.remove_change_groups.exists(),
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

    if action.remove_all_custom_fields:
        CustomFieldInstance.objects.filter(document=document).hard_delete()
    elif action.remove_custom_fields.exists():
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

    if action.remove_all_permissions:
        overrides.view_users = None
        overrides.view_groups = None
        overrides.change_users = None
        overrides.change_groups = None
    elif any(
        [
            action.remove_view_users.exists(),
            action.remove_view_groups.exists(),
            action.remove_change_users.exists(),
            action.remove_change_groups.exists(),
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

    if action.remove_all_custom_fields:
        overrides.custom_fields = None
    elif action.remove_custom_fields.exists() and overrides.custom_fields:
        for field in action.remove_custom_fields.filter(
            pk__in=overrides.custom_fields.keys(),
        ):
            overrides.custom_fields.pop(field.pk, None)


def build_workflow_action_context(
    document: Document | ConsumableDocument,
    overrides: DocumentMetadataOverrides | None,
    *,
    use_overrides: bool = False,
) -> dict:
    """
    Build context dictionary for workflow action placeholder parsing.
    """
    if not use_overrides:
        return {
            "title": document.title,
            "doc_url": f"{settings.PAPERLESS_URL}{settings.BASE_URL}documents/{document.pk}/",
            "correspondent": document.correspondent.name
            if document.correspondent
            else "",
            "document_type": document.document_type.name
            if document.document_type
            else "",
            "owner_username": document.owner.username if document.owner else "",
            "filename": document.original_filename or "",
            "current_filename": document.filename or "",
            "added": timezone.localtime(document.added),
            "created": document.created,
        }

    correspondent_obj = (
        Correspondent.objects.filter(pk=overrides.correspondent_id).first()
        if overrides and overrides.correspondent_id
        else None
    )
    document_type_obj = (
        DocumentType.objects.filter(pk=overrides.document_type_id).first()
        if overrides and overrides.document_type_id
        else None
    )
    owner_obj = (
        User.objects.filter(pk=overrides.owner_id).first()
        if overrides and overrides.owner_id
        else None
    )

    filename = document.original_file if document.original_file else ""
    return {
        "title": overrides.title
        if overrides and overrides.title
        else str(document.original_file),
        "doc_url": "",
        "correspondent": correspondent_obj.name if correspondent_obj else "",
        "document_type": document_type_obj.name if document_type_obj else "",
        "owner_username": owner_obj.username if owner_obj else "",
        "filename": filename,
        "current_filename": filename,
        "added": timezone.localtime(timezone.now()),
        "created": overrides.created if overrides else None,
    }


def execute_email_action(
    action: WorkflowAction,
    document: Document | ConsumableDocument,
    context: dict,
    logging_group,
    original_file: Path,
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
) -> None:
    """
    Execute an email action for a workflow.
    """

    subject = (
        parse_w_workflow_placeholders(
            action.email.subject,
            context["correspondent"],
            context["document_type"],
            context["owner_username"],
            context["added"],
            context["filename"],
            context["current_filename"],
            context["created"],
            context["title"],
            context["doc_url"],
        )
        if action.email.subject
        else ""
    )
    body = (
        parse_w_workflow_placeholders(
            action.email.body,
            context["correspondent"],
            context["document_type"],
            context["owner_username"],
            context["added"],
            context["filename"],
            context["current_filename"],
            context["created"],
            context["title"],
            context["doc_url"],
        )
        if action.email.body
        else ""
    )

    try:
        attachments: list[EmailAttachment] = []
        if action.email.include_document:
            attachment: EmailAttachment | None = None
            if trigger_type in [
                WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
                WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            ] and isinstance(document, Document):
                friendly_name = (
                    Path(context["current_filename"]).name
                    if context["current_filename"]
                    else document.source_path.name
                )
                attachment = EmailAttachment(
                    path=document.source_path,
                    mime_type=document.mime_type,
                    friendly_name=friendly_name,
                )
            elif original_file:
                friendly_name = (
                    Path(context["current_filename"]).name
                    if context["current_filename"]
                    else original_file.name
                )
                attachment = EmailAttachment(
                    path=original_file,
                    mime_type=document.mime_type,
                    friendly_name=friendly_name,
                )
            if attachment:
                attachments = [attachment]

        n_messages = send_email(
            subject=subject,
            body=body,
            to=action.email.to.split(","),
            attachments=attachments,
        )
        logger.debug(
            f"Sent {n_messages} notification email(s) to {action.email.to}",
            extra={"group": logging_group},
        )
    except Exception as e:
        logger.exception(
            f"Error occurred sending notification email: {e}",
            extra={"group": logging_group},
        )


def execute_webhook_action(
    action: WorkflowAction,
    document: Document | ConsumableDocument,
    context: dict,
    logging_group,
    original_file: Path,
):
    try:
        data = {}
        if action.webhook.use_params:
            if action.webhook.params:
                try:
                    for key, value in action.webhook.params.items():
                        data[key] = parse_w_workflow_placeholders(
                            value,
                            context["correspondent"],
                            context["document_type"],
                            context["owner_username"],
                            context["added"],
                            context["filename"],
                            context["current_filename"],
                            context["created"],
                            context["title"],
                            context["doc_url"],
                        )
                except Exception as e:
                    logger.error(
                        f"Error occurred parsing webhook params: {e}",
                        extra={"group": logging_group},
                    )
        elif action.webhook.body:
            data = parse_w_workflow_placeholders(
                action.webhook.body,
                context["correspondent"],
                context["document_type"],
                context["owner_username"],
                context["added"],
                context["filename"],
                context["current_filename"],
                context["created"],
                context["title"],
                context["doc_url"],
            )
        headers = {}
        if action.webhook.headers:
            try:
                headers = {str(k): str(v) for k, v in action.webhook.headers.items()}
            except Exception as e:
                logger.error(
                    f"Error occurred parsing webhook headers: {e}",
                    extra={"group": logging_group},
                )
        files = None
        if action.webhook.include_document:
            with original_file.open("rb") as f:
                files = {
                    "file": (
                        str(context["filename"])
                        if context["filename"]
                        else original_file.name,
                        f.read(),
                        document.mime_type,
                    ),
                }
        send_webhook.delay(
            url=action.webhook.url,
            data=data,
            headers=headers,
            files=files,
            as_json=action.webhook.as_json,
        )
        logger.debug(
            f"Webhook to {action.webhook.url} queued",
            extra={"group": logging_group},
        )
    except Exception as e:
        logger.exception(
            f"Error occurred sending webhook: {e}",
            extra={"group": logging_group},
        )


def _is_public_ip(ip: str) -> bool:
    try:
        obj = ipaddress.ip_address(ip)
        return not (
            obj.is_private
            or obj.is_loopback
            or obj.is_link_local
            or obj.is_multicast
            or obj.is_unspecified
        )
    except ValueError:  # pragma: no cover
        return False


def _resolve_first_ip(host: str) -> str | None:
    try:
        info = socket.getaddrinfo(host, None)
        return info[0][4][0] if info else None
    except Exception:  # pragma: no cover
        return None


@shared_task(
    retry_backoff=True,
    autoretry_for=(httpx.HTTPStatusError,),
    max_retries=3,
    throws=(httpx.HTTPError,),
)
def send_webhook(
    url: str,
    data: str | dict,
    headers: dict,
    files: dict,
    *,
    as_json: bool = False,
):
    p = urlparse(url)
    if p.scheme.lower() not in settings.WEBHOOKS_ALLOWED_SCHEMES or not p.hostname:
        logger.warning("Webhook blocked: invalid scheme/hostname")
        raise ValueError("Invalid URL scheme or hostname.")

    port = p.port or (443 if p.scheme == "https" else 80)
    if (
        len(settings.WEBHOOKS_ALLOWED_PORTS) > 0
        and port not in settings.WEBHOOKS_ALLOWED_PORTS
    ):
        logger.warning("Webhook blocked: port not permitted")
        raise ValueError("Destination port not permitted.")

    ip = _resolve_first_ip(p.hostname)
    if not ip or (
        not _is_public_ip(ip) and not settings.WEBHOOKS_ALLOW_INTERNAL_REQUESTS
    ):
        logger.warning("Webhook blocked: destination not allowed")
        raise ValueError("Destination host is not allowed.")

    try:
        post_args = {
            "url": url,
            "headers": {
                k: v for k, v in (headers or {}).items() if k.lower() != "host"
            },
            "files": files or None,
            "timeout": 5.0,
            "follow_redirects": False,
        }
        if as_json:
            post_args["json"] = data
        elif isinstance(data, dict):
            post_args["data"] = data
        else:
            post_args["content"] = data

        httpx.post(
            **post_args,
        ).raise_for_status()
        logger.info(
            f"Webhook sent to {url}",
        )
    except Exception as e:
        logger.error(
            f"Failed attempt sending webhook to {url}: {e}",
        )
        raise e
