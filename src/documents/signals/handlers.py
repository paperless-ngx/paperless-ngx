from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from celery import shared_task
from celery import states
from celery.signals import before_task_publish
from celery.signals import task_failure
from celery.signals import task_postrun
from celery.signals import task_prerun
from celery.signals import worker_process_init
from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db import close_old_connections
from django.db import connections
from django.db import models
from django.db.models import Q
from django.dispatch import receiver
from django.utils import timezone
from filelock import FileLock

from documents import matching
from documents.caching import clear_document_caches
from documents.caching import invalidate_llm_suggestions_cache
from documents.data_models import ConsumableDocument
from documents.file_handling import create_source_path_directory
from documents.file_handling import delete_empty_directories
from documents.file_handling import generate_filename
from documents.file_handling import generate_unique_filename
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import MatchingModel
from documents.models import PaperlessTask
from documents.models import SavedView
from documents.models import Tag
from documents.models import UiSettings
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowRun
from documents.models import WorkflowTrigger
from documents.permissions import get_objects_for_user_owner_aware
from documents.templating.utils import convert_format_str_to_template_format
from documents.workflows.actions import build_workflow_action_context
from documents.workflows.actions import execute_email_action
from documents.workflows.actions import execute_password_removal_action
from documents.workflows.actions import execute_webhook_action
from documents.workflows.mutations import apply_assignment_to_document
from documents.workflows.mutations import apply_assignment_to_overrides
from documents.workflows.mutations import apply_removal_to_document
from documents.workflows.mutations import apply_removal_to_overrides
from documents.workflows.utils import get_workflows_for_trigger
from paperless.config import AIConfig

if TYPE_CHECKING:
    from documents.classifier import DocumentClassifier
    from documents.data_models import ConsumableDocument
    from documents.data_models import DocumentMetadataOverrides

logger = logging.getLogger("paperless.handlers")


def add_inbox_tags(sender, document: Document, logging_group=None, **kwargs) -> None:
    if document.owner is not None:
        tags = get_objects_for_user_owner_aware(
            document.owner,
            "documents.view_tag",
            Tag,
        )
    else:
        tags = Tag.objects.all()
    inbox_tags = tags.filter(is_inbox_tag=True)
    document.add_nested_tags(inbox_tags)


def _suggestion_printer(
    stdout,
    style_func,
    suggestion_type: str,
    document: Document,
    selected: MatchingModel,
    base_url: str | None = None,
) -> None:
    """
    Smaller helper to reduce duplication when just outputting suggestions to the console
    """
    doc_str = str(document)
    if base_url is not None:
        stdout.write(style_func.SUCCESS(doc_str))
        stdout.write(style_func.SUCCESS(f"{base_url}/documents/{document.pk}"))
    else:
        stdout.write(style_func.SUCCESS(f"{doc_str} [{document.pk}]"))
    stdout.write(f"Suggest {suggestion_type}: {selected}")


def set_correspondent(
    sender,
    document: Document,
    *,
    logging_group=None,
    classifier: DocumentClassifier | None = None,
    replace=False,
    use_first=True,
    suggest=False,
    base_url=None,
    stdout=None,
    style_func=None,
    **kwargs,
) -> None:
    if document.correspondent and not replace:
        return

    potential_correspondents = matching.match_correspondents(document, classifier)

    potential_count = len(potential_correspondents)
    selected = potential_correspondents[0] if potential_correspondents else None
    if potential_count > 1:
        if use_first:
            logger.debug(
                f"Detected {potential_count} potential correspondents, "
                f"so we've opted for {selected}",
                extra={"group": logging_group},
            )
        else:
            logger.debug(
                f"Detected {potential_count} potential correspondents, "
                f"not assigning any correspondent",
                extra={"group": logging_group},
            )
            return

    if selected or replace:
        if suggest:
            _suggestion_printer(
                stdout,
                style_func,
                "correspondent",
                document,
                selected,
                base_url,
            )
        else:
            logger.info(
                f"Assigning correspondent {selected} to {document}",
                extra={"group": logging_group},
            )

            document.correspondent = selected
            document.save(update_fields=("correspondent",))


def set_document_type(
    sender,
    document: Document,
    *,
    logging_group=None,
    classifier: DocumentClassifier | None = None,
    replace=False,
    use_first=True,
    suggest=False,
    base_url=None,
    stdout=None,
    style_func=None,
    **kwargs,
) -> None:
    if document.document_type and not replace:
        return

    potential_document_type = matching.match_document_types(document, classifier)

    potential_count = len(potential_document_type)
    selected = potential_document_type[0] if potential_document_type else None

    if potential_count > 1:
        if use_first:
            logger.info(
                f"Detected {potential_count} potential document types, "
                f"so we've opted for {selected}",
                extra={"group": logging_group},
            )
        else:
            logger.info(
                f"Detected {potential_count} potential document types, "
                f"not assigning any document type",
                extra={"group": logging_group},
            )
            return

    if selected or replace:
        if suggest:
            _suggestion_printer(
                stdout,
                style_func,
                "document type",
                document,
                selected,
                base_url,
            )
        else:
            logger.info(
                f"Assigning document type {selected} to {document}",
                extra={"group": logging_group},
            )

            document.document_type = selected
            document.save(update_fields=("document_type",))


def set_tags(
    sender,
    document: Document,
    *,
    logging_group=None,
    classifier: DocumentClassifier | None = None,
    replace=False,
    suggest=False,
    base_url=None,
    stdout=None,
    style_func=None,
    **kwargs,
) -> None:
    if replace:
        Document.tags.through.objects.filter(document=document).exclude(
            Q(tag__is_inbox_tag=True),
        ).exclude(
            Q(tag__match="") & ~Q(tag__matching_algorithm=Tag.MATCH_AUTO),
        ).delete()

    current_tags = set(document.tags.all())

    matched_tags = matching.match_tags(document, classifier)

    relevant_tags = set(matched_tags) - current_tags

    if suggest:
        extra_tags = current_tags - set(matched_tags)
        extra_tags = [
            t for t in extra_tags if t.matching_algorithm == MatchingModel.MATCH_AUTO
        ]
        if not relevant_tags and not extra_tags:
            return
        doc_str = style_func.SUCCESS(str(document))
        if base_url:
            stdout.write(doc_str)
            stdout.write(f"{base_url}/documents/{document.pk}")
        else:
            stdout.write(doc_str + style_func.SUCCESS(f" [{document.pk}]"))
        if relevant_tags:
            stdout.write("Suggest tags: " + ", ".join([t.name for t in relevant_tags]))
        if extra_tags:
            stdout.write("Extra tags: " + ", ".join([t.name for t in extra_tags]))
    else:
        if not relevant_tags:
            return

        message = 'Tagging "{}" with "{}"'
        logger.info(
            message.format(document, ", ".join([t.name for t in relevant_tags])),
            extra={"group": logging_group},
        )

        document.add_nested_tags(relevant_tags)


def set_storage_path(
    sender,
    document: Document,
    *,
    logging_group=None,
    classifier: DocumentClassifier | None = None,
    replace=False,
    use_first=True,
    suggest=False,
    base_url=None,
    stdout=None,
    style_func=None,
    **kwargs,
) -> None:
    if document.storage_path and not replace:
        return

    potential_storage_path = matching.match_storage_paths(
        document,
        classifier,
    )

    potential_count = len(potential_storage_path)
    selected = potential_storage_path[0] if potential_storage_path else None

    if potential_count > 1:
        if use_first:
            logger.info(
                f"Detected {potential_count} potential storage paths, "
                f"so we've opted for {selected}",
                extra={"group": logging_group},
            )
        else:
            logger.info(
                f"Detected {potential_count} potential storage paths, "
                f"not assigning any storage directory",
                extra={"group": logging_group},
            )
            return

    if selected or replace:
        if suggest:
            _suggestion_printer(
                stdout,
                style_func,
                "storage directory",
                document,
                selected,
                base_url,
            )
        else:
            logger.info(
                f"Assigning storage path {selected} to {document}",
                extra={"group": logging_group},
            )

            document.storage_path = selected
            document.save(update_fields=("storage_path",))


# see empty_trash in documents/tasks.py for signal handling
def cleanup_document_deletion(sender, instance, **kwargs) -> None:
    with FileLock(settings.MEDIA_LOCK):
        if settings.EMPTY_TRASH_DIR:
            # Find a non-conflicting filename in case a document with the same
            # name was moved to trash earlier
            counter = 0
            old_filename = Path(instance.source_path).name
            old_filebase = Path(old_filename).stem
            old_fileext = Path(old_filename).suffix

            while True:
                new_file_path = settings.EMPTY_TRASH_DIR / (
                    old_filebase + (f"_{counter:02}" if counter else "") + old_fileext
                )

                if new_file_path.exists():
                    counter += 1
                else:
                    break

            logger.debug(f"Moving {instance.source_path} to trash at {new_file_path}")
            try:
                shutil.move(instance.source_path, new_file_path)
            except OSError as e:
                logger.error(
                    f"Failed to move {instance.source_path} to trash at "
                    f"{new_file_path}: {e}. Skipping cleanup!",
                )
                return

        files = (
            instance.archive_path,
            instance.thumbnail_path,
        )
        if not settings.EMPTY_TRASH_DIR:
            # Only delete the original file if we are not moving it to trash dir
            files += (instance.source_path,)

        for filename in files:
            if filename and filename.is_file():
                try:
                    filename.unlink()
                    logger.debug(f"Deleted file {filename}.")
                except OSError as e:
                    logger.warning(
                        f"While deleting document {instance!s}, the file "
                        f"{filename} could not be deleted: {e}",
                    )
            elif filename and not filename.is_file():
                logger.warning(f"Expected {filename} to exist, but it did not")

        delete_empty_directories(
            Path(instance.source_path).parent,
            root=settings.ORIGINALS_DIR,
        )

        if instance.has_archive_version:
            delete_empty_directories(
                Path(instance.archive_path).parent,
                root=settings.ARCHIVE_DIR,
            )


class CannotMoveFilesException(Exception):
    pass


def _filename_template_uses_custom_fields(doc: Document) -> bool:
    template = None
    if doc.storage_path is not None:
        template = doc.storage_path.path
    elif settings.FILENAME_FORMAT is not None:
        template = convert_format_str_to_template_format(settings.FILENAME_FORMAT)

    if not template:
        return False

    return "custom_fields" in template


# should be disabled in /src/documents/management/commands/document_importer.py handle
@receiver(models.signals.post_save, sender=CustomFieldInstance, weak=False)
@receiver(models.signals.m2m_changed, sender=Document.tags.through, weak=False)
@receiver(models.signals.post_save, sender=Document, weak=False)
def update_filename_and_move_files(
    sender,
    instance: Document | CustomFieldInstance,
    **kwargs,
) -> None:
    if isinstance(instance, CustomFieldInstance):
        if not _filename_template_uses_custom_fields(instance.document):
            return
        instance = instance.document

    def validate_move(instance, old_path: Path, new_path: Path, root: Path) -> None:
        if not new_path.is_relative_to(root):
            msg = (
                f"Document {instance!s}: Refusing to move file outside root {root}: "
                f"{new_path}."
            )
            logger.warning(msg)
            raise CannotMoveFilesException(msg)

        if not old_path.is_file():
            # Can't do anything if the old file does not exist anymore.
            msg = f"Document {instance!s}: File {old_path} doesn't exist."
            logger.fatal(msg)
            raise CannotMoveFilesException(msg)

        if new_path.is_file():
            # Can't do anything if the new file already exists. Skip updating file.
            msg = f"Document {instance!s}: Cannot rename file since target path {new_path} already exists."
            logger.warning(msg)
            raise CannotMoveFilesException(msg)

    if not instance.filename:
        # Can't update the filename if there is no filename to begin with
        # This happens when the consumer creates a new document.
        # The document is modified and saved multiple times, and only after
        # everything is done (i.e., the generated filename is final),
        # filename will be set to the location where the consumer has put
        # the file.
        #
        # This will in turn cause this logic to move the file where it belongs.
        return

    with FileLock(settings.MEDIA_LOCK):
        try:
            # If this was waiting for the lock, the filename or archive_filename
            # of this document may have been updated.  This happens if multiple updates
            # get queued from the UI for the same document
            # So freshen up the data before doing anything
            instance.refresh_from_db()

            old_filename = instance.filename
            old_source_path = instance.source_path

            candidate_filename = generate_filename(instance)
            candidate_source_path = (
                settings.ORIGINALS_DIR / candidate_filename
            ).resolve()
            if candidate_filename == Path(old_filename):
                new_filename = Path(old_filename)
            elif (
                candidate_source_path.exists()
                and candidate_source_path != old_source_path
            ):
                # Only fall back to unique search when there is an actual conflict
                new_filename = generate_unique_filename(instance)
            else:
                new_filename = candidate_filename

            # Need to convert to string to be able to save it to the db
            instance.filename = str(new_filename)
            move_original = old_filename != instance.filename

            old_archive_filename = instance.archive_filename
            old_archive_path = instance.archive_path

            if instance.has_archive_version:
                archive_candidate = generate_filename(instance, archive_filename=True)
                archive_candidate_path = (
                    settings.ARCHIVE_DIR / archive_candidate
                ).resolve()
                if archive_candidate == Path(old_archive_filename):
                    new_archive_filename = Path(old_archive_filename)
                elif (
                    archive_candidate_path.exists()
                    and archive_candidate_path != old_archive_path
                ):
                    new_archive_filename = generate_unique_filename(
                        instance,
                        archive_filename=True,
                    )
                else:
                    new_archive_filename = archive_candidate

                instance.archive_filename = str(new_archive_filename)

                move_archive = old_archive_filename != instance.archive_filename
            else:
                move_archive = False

            if not move_original and not move_archive:
                # Just update modified. Also, don't save() here to prevent infinite recursion.
                Document.objects.filter(pk=instance.pk).update(
                    modified=timezone.now(),
                )
                return

            if move_original:
                validate_move(
                    instance,
                    old_source_path,
                    instance.source_path,
                    settings.ORIGINALS_DIR,
                )
                create_source_path_directory(instance.source_path)
                shutil.move(old_source_path, instance.source_path)

            if move_archive:
                validate_move(
                    instance,
                    old_archive_path,
                    instance.archive_path,
                    settings.ARCHIVE_DIR,
                )
                create_source_path_directory(instance.archive_path)
                shutil.move(old_archive_path, instance.archive_path)

            # Don't save() here to prevent infinite recursion.
            Document.global_objects.filter(pk=instance.pk).update(
                filename=instance.filename,
                archive_filename=instance.archive_filename,
                modified=timezone.now(),
            )
            # Clear any caching for this document.  Slightly overkill, but not terrible
            clear_document_caches(instance.pk)

        except (OSError, DatabaseError, CannotMoveFilesException) as e:
            logger.warning(f"Exception during file handling: {e}")
            # This happens when either:
            #  - moving the files failed due to file system errors
            #  - saving to the database failed due to database errors
            # In both cases, we need to revert to the original state.

            # Try to move files to their original location.
            try:
                if move_original and instance.source_path.is_file():
                    logger.info("Restoring previous original path")
                    shutil.move(instance.source_path, old_source_path)

                if move_archive and instance.archive_path.is_file():
                    logger.info("Restoring previous archive path")
                    shutil.move(instance.archive_path, old_archive_path)

            except Exception:
                # This is fine, since:
                # A: if we managed to move source from A to B, we will also
                #  manage to move it from B to A. If not, we have a serious
                #  issue that's going to get caught by the santiy checker.
                #  All files remain in place and will never be overwritten,
                #  so this is not the end of the world.
                # B: if moving the original file failed, nothing has changed
                #  anyway.
                pass

            # restore old values on the instance
            instance.filename = old_filename
            instance.archive_filename = old_archive_filename

        # finally, remove any empty sub folders. This will do nothing if
        # something has failed above.
        if not old_source_path.is_file():
            delete_empty_directories(
                Path(old_source_path).parent,
                root=settings.ORIGINALS_DIR,
            )

        if instance.has_archive_version and not old_archive_path.is_file():
            delete_empty_directories(
                Path(old_archive_path).parent,
                root=settings.ARCHIVE_DIR,
            )


@shared_task
def process_cf_select_update(custom_field: CustomField) -> None:
    """
    Update documents tied to a select custom field:

    1. 'Select' custom field instances get their end-user value (e.g. in file names) from the select_options in extra_data,
    which is contained in the custom field itself. So when the field is changed, we (may) need to update the file names
    of all documents that have this custom field.
    2. If a 'Select' field option was removed, we need to nullify the custom field instances that have the option.
    """
    select_options = {
        option["id"]: option["label"]
        for option in custom_field.extra_data.get("select_options", [])
    }

    # Clear select values that no longer exist
    custom_field.fields.exclude(
        value_select__in=select_options.keys(),
    ).update(value_select=None)

    for cf_instance in custom_field.fields.select_related("document").iterator():
        # Update the filename and move files if necessary
        update_filename_and_move_files(CustomFieldInstance, cf_instance)


# should be disabled in /src/documents/management/commands/document_importer.py handle
@receiver(models.signals.post_save, sender=CustomField)
def check_paths_and_prune_custom_fields(
    sender,
    instance: CustomField,
    **kwargs,
) -> None:
    """
    When a custom field is updated, check if we need to update any documents. Done async to avoid slowing down the save operation.
    """
    if (
        instance.data_type == CustomField.FieldDataType.SELECT
        and instance.fields.count() > 0
        and instance.extra_data
    ):  # Only select fields, for now
        process_cf_select_update.delay(instance)


@receiver(models.signals.post_delete, sender=CustomField)
def cleanup_custom_field_deletion(sender, instance: CustomField, **kwargs) -> None:
    """
    When a custom field is deleted, ensure no saved views reference it.
    """
    field_identifier = SavedView.DisplayFields.CUSTOM_FIELD % instance.pk
    # remove field from display_fields of all saved views
    for view in SavedView.objects.filter(display_fields__isnull=False).distinct():
        if field_identifier in view.display_fields:
            logger.debug(
                f"Removing custom field {instance} from view {view}",
            )
            view.display_fields.remove(field_identifier)
            view.save()

    # remove from sort_field of all saved views
    views_with_sort_updated = SavedView.objects.filter(
        sort_field=field_identifier,
    ).update(
        sort_field=SavedView.DisplayFields.CREATED,
    )
    if views_with_sort_updated > 0:
        logger.debug(
            f"Removing custom field {instance} from sort field of {views_with_sort_updated} views",
        )


@receiver(models.signals.post_save, sender=Document)
def update_llm_suggestions_cache(sender, instance, **kwargs):
    """
    Invalidate the LLM suggestions cache when a document is saved.
    """
    # Invalidate the cache for the document
    invalidate_llm_suggestions_cache(instance.pk)


@receiver(models.signals.post_delete, sender=User)
@receiver(models.signals.post_delete, sender=Group)
def cleanup_user_deletion(sender, instance: User | Group, **kwargs) -> None:
    """
    When a user or group is deleted, remove non-cascading references.
    At the moment, just the default permission settings in UiSettings.
    """
    # Remove the user permission settings e.g.
    #   DEFAULT_PERMS_OWNER: 'general-settings:permissions:default-owner',
    #   DEFAULT_PERMS_VIEW_USERS: 'general-settings:permissions:default-view-users',
    #   DEFAULT_PERMS_VIEW_GROUPS: 'general-settings:permissions:default-view-groups',
    #   DEFAULT_PERMS_EDIT_USERS: 'general-settings:permissions:default-edit-users',
    #   DEFAULT_PERMS_EDIT_GROUPS: 'general-settings:permissions:default-edit-groups',
    for ui_settings in UiSettings.objects.all():
        try:
            permissions = ui_settings.settings.get("permissions", {})
            updated = False
            if isinstance(instance, User):
                if permissions.get("default_owner") == instance.pk:
                    permissions["default_owner"] = None
                    updated = True
                if instance.pk in permissions.get("default_view_users", []):
                    permissions["default_view_users"].remove(instance.pk)
                    updated = True
                if instance.pk in permissions.get("default_change_users", []):
                    permissions["default_change_users"].remove(instance.pk)
                    updated = True
            elif isinstance(instance, Group):
                if instance.pk in permissions.get("default_view_groups", []):
                    permissions["default_view_groups"].remove(instance.pk)
                    updated = True
                if instance.pk in permissions.get("default_change_groups", []):
                    permissions["default_change_groups"].remove(instance.pk)
                    updated = True
            if updated:
                ui_settings.settings["permissions"] = permissions
                ui_settings.save(update_fields=["settings"])
        except Exception as e:
            logger.error(
                f"Error while cleaning up user {instance.pk} ({instance.username}) from ui_settings: {e}"
                if isinstance(instance, User)
                else f"Error while cleaning up group {instance.pk} ({instance.name}) from ui_settings: {e}",
            )


def add_to_index(sender, document, **kwargs) -> None:
    from documents import index

    index.add_or_update_document(document)


def run_workflows_added(
    sender,
    document: Document,
    logging_group=None,
    original_file=None,
    **kwargs,
) -> None:
    run_workflows(
        trigger_type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_ADDED,
        document=document,
        logging_group=logging_group,
        overrides=None,
        original_file=original_file,
    )


def run_workflows_updated(
    sender,
    document: Document,
    logging_group=None,
    **kwargs,
) -> None:
    run_workflows(
        trigger_type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        document=document,
        logging_group=logging_group,
    )


def run_workflows(
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
    document: Document | ConsumableDocument,
    workflow_to_run: Workflow | None = None,
    logging_group=None,
    overrides: DocumentMetadataOverrides | None = None,
    original_file: Path | None = None,
) -> tuple[DocumentMetadataOverrides, str] | None:
    """
    Execute workflows matching a document for the given trigger. When `overrides` is provided
    (consumption flow), actions mutate that object and the function returns `(overrides, messages)`.
    Otherwise actions mutate the actual document and return nothing.

    Attachments for email/webhook actions use `original_file` when given, otherwise fall back to
    `document.source_path` (Document) or `document.original_file` (ConsumableDocument).

    Passing `workflow_to_run` skips the workflow query (currently only used by scheduled runs).
    """

    use_overrides = overrides is not None
    if original_file is None:
        original_file = (
            document.source_path if not use_overrides else document.original_file
        )
    messages = []

    workflows = get_workflows_for_trigger(trigger_type, workflow_to_run)

    for workflow in workflows:
        if not use_overrides:
            # This can be called from bulk_update_documents, which may be running multiple times
            # Refresh this so the matching data is fresh and instance fields are re-freshed
            # Otherwise, this instance might be behind and overwrite the work another process did
            document.refresh_from_db()
            doc_tag_ids = list(document.tags.values_list("pk", flat=True))

        if matching.document_matches_workflow(document, workflow, trigger_type):
            action: WorkflowAction
            for action in workflow.actions.order_by("order", "pk"):
                message = f"Applying {action} from {workflow}"
                if not use_overrides:
                    logger.info(message, extra={"group": logging_group})
                else:
                    messages.append(message)

                if action.type == WorkflowAction.WorkflowActionType.ASSIGNMENT:
                    if use_overrides and overrides:
                        apply_assignment_to_overrides(action, overrides)
                    else:
                        apply_assignment_to_document(
                            action,
                            document,
                            doc_tag_ids,
                            logging_group,
                        )
                elif action.type == WorkflowAction.WorkflowActionType.REMOVAL:
                    if use_overrides and overrides:
                        apply_removal_to_overrides(action, overrides)
                    else:
                        apply_removal_to_document(action, document, doc_tag_ids)
                elif action.type == WorkflowAction.WorkflowActionType.EMAIL:
                    context = build_workflow_action_context(document, overrides)
                    execute_email_action(
                        action,
                        document,
                        context,
                        logging_group,
                        original_file,
                        trigger_type,
                    )
                elif action.type == WorkflowAction.WorkflowActionType.WEBHOOK:
                    context = build_workflow_action_context(document, overrides)
                    execute_webhook_action(
                        action,
                        document,
                        context,
                        logging_group,
                        original_file,
                    )
                elif action.type == WorkflowAction.WorkflowActionType.PASSWORD_REMOVAL:
                    execute_password_removal_action(action, document, logging_group)

            if not use_overrides:
                # limit title to 128 characters
                document.title = document.title[:128]
                # save first before setting tags
                document.save()
                document.tags.set(doc_tag_ids)

            WorkflowRun.objects.create(
                workflow=workflow,
                type=trigger_type,
                document=document if not use_overrides else None,
            )

    if use_overrides:
        return overrides, "\n".join(messages)


@before_task_publish.connect
def before_task_publish_handler(sender=None, headers=None, body=None, **kwargs) -> None:
    """
    Creates the PaperlessTask object in a pending state.  This is sent before
    the task reaches the broker, but before it begins executing on a worker.

    https://docs.celeryq.dev/en/stable/userguide/signals.html#before-task-publish

    https://docs.celeryq.dev/en/stable/internals/protocol.html#version-2

    """
    if "task" not in headers or headers["task"] != "documents.tasks.consume_file":
        # Assumption: this is only ever a v2 message
        return

    try:
        close_old_connections()

        task_args = body[0]
        input_doc, overrides = task_args

        task_file_name = input_doc.original_file.name
        user_id = overrides.owner_id if overrides else None

        PaperlessTask.objects.create(
            type=PaperlessTask.TaskType.AUTO,
            task_id=headers["id"],
            status=states.PENDING,
            task_file_name=task_file_name,
            task_name=PaperlessTask.TaskName.CONSUME_FILE,
            result=None,
            date_created=timezone.now(),
            date_started=None,
            date_done=None,
            owner_id=user_id,
        )
    except Exception:  # pragma: no cover
        # Don't let an exception in the signal handlers prevent
        # a document from being consumed.
        logger.exception("Creating PaperlessTask failed")


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs) -> None:
    """

    Updates the PaperlessTask to be started.  Sent before the task begins execution
    on a worker.

    https://docs.celeryq.dev/en/stable/userguide/signals.html#task-prerun
    """
    try:
        close_old_connections()
        task_instance = PaperlessTask.objects.filter(task_id=task_id).first()

        if task_instance is not None:
            task_instance.status = states.STARTED
            task_instance.date_started = timezone.now()
            task_instance.save()
    except Exception:  # pragma: no cover
        # Don't let an exception in the signal handlers prevent
        # a document from being consumed.
        logger.exception("Setting PaperlessTask started failed")


@task_postrun.connect
def task_postrun_handler(
    sender=None,
    task_id=None,
    task=None,
    retval=None,
    state=None,
    **kwargs,
) -> None:
    """
    Updates the result of the PaperlessTask.

    https://docs.celeryq.dev/en/stable/userguide/signals.html#task-postrun
    """
    try:
        close_old_connections()
        task_instance = PaperlessTask.objects.filter(task_id=task_id).first()

        if task_instance is not None:
            task_instance.status = state or states.FAILURE
            task_instance.result = retval
            task_instance.date_done = timezone.now()
            task_instance.save()
    except Exception:  # pragma: no cover
        # Don't let an exception in the signal handlers prevent
        # a document from being consumed.
        logger.exception("Updating PaperlessTask failed")


@task_failure.connect
def task_failure_handler(
    sender=None,
    task_id=None,
    exception=None,
    args=None,
    traceback=None,
    **kwargs,
) -> None:
    """
    Updates the result of a failed PaperlessTask.

    https://docs.celeryq.dev/en/stable/userguide/signals.html#task-failure
    """
    try:
        close_old_connections()
        task_instance = PaperlessTask.objects.filter(task_id=task_id).first()

        if task_instance is not None and task_instance.result is None:
            task_instance.status = states.FAILURE
            task_instance.result = traceback
            task_instance.date_done = timezone.now()
            task_instance.save()
    except Exception:  # pragma: no cover
        logger.exception("Updating PaperlessTask failed")


@worker_process_init.connect
def close_connection_pool_on_worker_init(**kwargs) -> None:
    """
    Close the DB connection pool for each Celery child process after it starts.

    This is necessary because the parent process parse the Django configuration,
    initializes connection pools then forks.

    Closing these pools after forking ensures child processes have a valid connection.
    """
    for conn in connections.all(initialized_only=True):
        if conn.alias == "default" and hasattr(conn, "pool") and conn.pool:
            conn.close_pool()


def add_or_update_document_in_llm_index(sender, document, **kwargs):
    """
    Add or update a document in the LLM index when it is created or updated.
    """
    ai_config = AIConfig()
    if ai_config.llm_index_enabled:
        from documents.tasks import update_document_in_llm_index

        update_document_in_llm_index.delay(document)


@receiver(models.signals.post_delete, sender=Document)
def delete_document_from_llm_index(sender, instance: Document, **kwargs):
    """
    Delete a document from the LLM index when it is deleted.
    """
    ai_config = AIConfig()
    if ai_config.llm_index_enabled:
        from documents.tasks import remove_document_from_llm_index

        remove_document_from_llm_index.delay(instance)
