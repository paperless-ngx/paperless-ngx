import logging
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.mail import EmailAttachment
from documents.mail import send_email
from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import WorkflowAction
from documents.models import WorkflowTrigger
from documents.signals import document_consumption_finished
from documents.templating.workflows import parse_w_workflow_placeholders
from documents.workflows.webhooks import send_webhook

logger = logging.getLogger("paperless.workflows.actions")


def build_workflow_action_context(
    document: Document | ConsumableDocument,
    overrides: DocumentMetadataOverrides | None,
) -> dict:
    """
    Build context dictionary for workflow action placeholder parsing.
    """
    use_overrides = overrides is not None

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
            "id": document.pk,
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
        "id": "",
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

    if not settings.EMAIL_ENABLED:
        logger.error(
            "Email backend has not been configured, cannot send email notifications",
            extra={"group": logging_group},
        )
        return

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
            context["id"],
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
            context["id"],
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
                            context["id"],
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
                context["id"],
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


def execute_password_removal_action(
    action: WorkflowAction,
    document: Document | ConsumableDocument,
    logging_group,
) -> None:
    """
    Try to remove a password from a document using the configured list.
    """
    passwords = action.passwords
    if not passwords:
        logger.warning(
            "Password removal action %s has no passwords configured",
            action.pk,
            extra={"group": logging_group},
        )
        return

    passwords = [
        password.strip()
        for password in re.split(r"[,\n]", passwords)
        if password.strip()
    ]

    if isinstance(document, ConsumableDocument):
        # hook the consumption-finished signal to attempt password removal later
        def handler(sender, **kwargs):
            consumed_document: Document = kwargs.get("document")
            if consumed_document is not None:
                execute_password_removal_action(
                    action,
                    consumed_document,
                    logging_group,
                )
            document_consumption_finished.disconnect(handler)

        document_consumption_finished.connect(handler, weak=False)
        return

    # import here to avoid circular dependency
    from documents.bulk_edit import remove_password

    for password in passwords:
        try:
            remove_password(
                [document.id],
                password=password,
                update_document=True,
                user=document.owner,
            )
            logger.info(
                "Removed password from document %s using workflow action %s",
                document.pk,
                action.pk,
                extra={"group": logging_group},
            )
            return
        except ValueError as e:
            logger.warning(
                "Password removal failed for document %s with supplied password: %s",
                document.pk,
                e,
                extra={"group": logging_group},
            )

    logger.error(
        "Password removal failed for document %s after trying all provided passwords",
        document.pk,
        extra={"group": logging_group},
    )
