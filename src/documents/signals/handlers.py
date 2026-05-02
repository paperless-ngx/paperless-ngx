from __future__ import annotations

import datetime
import hashlib
import logging
import shutil
import traceback as _tb
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from celery import shared_task
from celery.signals import before_task_publish
from celery.signals import task_failure
from celery.signals import task_postrun
from celery.signals import task_prerun
from celery.signals import task_revoked
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
from rest_framework import serializers

from documents import matching
from documents.caching import clear_document_caches
from documents.caching import invalidate_llm_suggestions_cache
from documents.data_models import ConsumableDocument
from documents.file_handling import create_source_path_directory
from documents.file_handling import delete_empty_directories
from documents.file_handling import generate_filename
from documents.file_handling import generate_unique_filename
from documents.models import Correspondent
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import PaperlessTask
from documents.models import SavedView
from documents.models import StoragePath
from documents.models import Tag
from documents.models import UiSettings
from documents.models import Workflow
from documents.models import WorkflowAction
from documents.models import WorkflowRun
from documents.models import WorkflowTrigger
from documents.permissions import get_objects_for_user_owner_aware
from documents.plugins.helpers import DocumentsStatusManager
from documents.templating.utils import convert_format_str_to_template_format
from documents.workflows.actions import build_workflow_action_context
from documents.workflows.actions import execute_email_action
from documents.workflows.actions import execute_move_to_trash_action
from documents.workflows.actions import execute_password_removal_action
from documents.workflows.actions import execute_webhook_action
from documents.workflows.mutations import apply_assignment_to_document
from documents.workflows.mutations import apply_assignment_to_overrides
from documents.workflows.mutations import apply_removal_to_document
from documents.workflows.mutations import apply_removal_to_overrides
from documents.workflows.utils import get_workflows_for_trigger
from paperless.config import AIConfig

if TYPE_CHECKING:
    import uuid

    from documents.classifier import DocumentClassifier
    from documents.data_models import ConsumableDocument
    from documents.data_models import DocumentMetadataOverrides

logger = logging.getLogger("paperless.handlers")
DRF_DATETIME_FIELD = serializers.DateTimeField()


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


def set_correspondent(
    sender: object,
    document: Document,
    *,
    logging_group: object = None,
    classifier: DocumentClassifier | None = None,
    replace: bool = False,
    use_first: bool = True,
    dry_run: bool = False,
    **kwargs: Any,
) -> Correspondent | None:
    """
    Assign a correspondent to a document based on classifier results.

    Args:
        document: The document to classify.
        logging_group: Optional logging group for structured log output.
        classifier: The trained classifier. If None, only rule-based matching runs.
        replace: If True, overwrite an existing correspondent assignment.
        use_first: If True, pick the first match when multiple correspondents
            match. If False, skip assignment when multiple match.
        dry_run: If True, compute and return the selection without saving.
        **kwargs: Absorbed for Django signal compatibility (e.g. sender, signal).

    Returns:
        The correspondent that was (or would be) assigned, or None if no match
        was found or assignment was skipped.
    """
    if document.correspondent and not replace:
        return None

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
            return None

    if (selected or replace) and not dry_run:
        logger.info(
            f"Assigning correspondent {selected} to {document}",
            extra={"group": logging_group},
        )
        document.correspondent = selected
        document.save(update_fields=("correspondent",))

    return selected


def set_document_type(
    sender: object,
    document: Document,
    *,
    logging_group: object = None,
    classifier: DocumentClassifier | None = None,
    replace: bool = False,
    use_first: bool = True,
    dry_run: bool = False,
    **kwargs: Any,
) -> DocumentType | None:
    """
    Assign a document type to a document based on classifier results.

    Args:
        document: The document to classify.
        logging_group: Optional logging group for structured log output.
        classifier: The trained classifier. If None, only rule-based matching runs.
        replace: If True, overwrite an existing document type assignment.
        use_first: If True, pick the first match when multiple types match.
            If False, skip assignment when multiple match.
        dry_run: If True, compute and return the selection without saving.
        **kwargs: Absorbed for Django signal compatibility (e.g. sender, signal).

    Returns:
        The document type that was (or would be) assigned, or None if no match
        was found or assignment was skipped.
    """
    if document.document_type and not replace:
        return None

    potential_document_types = matching.match_document_types(document, classifier)
    potential_count = len(potential_document_types)
    selected = potential_document_types[0] if potential_document_types else None

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
            return None

    if (selected or replace) and not dry_run:
        logger.info(
            f"Assigning document type {selected} to {document}",
            extra={"group": logging_group},
        )
        document.document_type = selected
        document.save(update_fields=("document_type",))

    return selected


def set_tags(
    sender: object,
    document: Document,
    *,
    logging_group: object = None,
    classifier: DocumentClassifier | None = None,
    replace: bool = False,
    dry_run: bool = False,
    **kwargs: Any,
) -> tuple[set[Tag], set[Tag]]:
    """
    Assign tags to a document based on classifier results.

    When replace=True, existing auto-matched and rule-matched tags are removed
    before applying the new set (inbox tags and manually-added tags are preserved).

    Args:
        document: The document to classify.
        logging_group: Optional logging group for structured log output.
        classifier: The trained classifier. If None, only rule-based matching runs.
        replace: If True, remove existing classifier-managed tags before applying
            new ones. Inbox tags and manually-added tags are always preserved.
        dry_run: If True, compute what would change without saving anything.
        **kwargs: Absorbed for Django signal compatibility (e.g. sender, signal).

    Returns:
        A two-tuple of (tags_added, tags_removed). In non-replace mode,
        tags_removed is always an empty set. In dry_run mode, neither set
        is applied to the database.
    """
    # Compute which tags would be removed under replace mode.
    # The filter mirrors the .delete() call below: keep inbox tags and
    # manually-added tags (match="" and not auto-matched).
    if replace:
        tags_to_remove: set[Tag] = set(
            document.tags.exclude(
                is_inbox_tag=True,
            ).exclude(
                Q(match="") & ~Q(matching_algorithm=Tag.MATCH_AUTO),
            ),
        )
    else:
        tags_to_remove = set()

    if replace and not dry_run:
        Document.tags.through.objects.filter(document=document).exclude(
            Q(tag__is_inbox_tag=True),
        ).exclude(
            Q(tag__match="") & ~Q(tag__matching_algorithm=Tag.MATCH_AUTO),
        ).delete()

    current_tags = set(document.tags.all())
    matched_tags = matching.match_tags(document, classifier)
    tags_to_add = set(matched_tags) - current_tags

    if tags_to_add and not dry_run:
        logger.info(
            f'Tagging "{document}" with "{", ".join(t.name for t in tags_to_add)}"',
            extra={"group": logging_group},
        )
        document.add_nested_tags(tags_to_add)

    return tags_to_add, tags_to_remove


def set_storage_path(
    sender: object,
    document: Document,
    *,
    logging_group: object = None,
    classifier: DocumentClassifier | None = None,
    replace: bool = False,
    use_first: bool = True,
    dry_run: bool = False,
    **kwargs: Any,
) -> StoragePath | None:
    """
    Assign a storage path to a document based on classifier results.

    Args:
        document: The document to classify.
        logging_group: Optional logging group for structured log output.
        classifier: The trained classifier. If None, only rule-based matching runs.
        replace: If True, overwrite an existing storage path assignment.
        use_first: If True, pick the first match when multiple paths match.
            If False, skip assignment when multiple match.
        dry_run: If True, compute and return the selection without saving.
        **kwargs: Absorbed for Django signal compatibility (e.g. sender, signal).

    Returns:
        The storage path that was (or would be) assigned, or None if no match
        was found or assignment was skipped.
    """
    if document.storage_path and not replace:
        return None

    potential_storage_paths = matching.match_storage_paths(document, classifier)
    potential_count = len(potential_storage_paths)
    selected = potential_storage_paths[0] if potential_storage_paths else None

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
            return None

    if (selected or replace) and not dry_run:
        logger.info(
            f"Assigning storage path {selected} to {document}",
            extra={"group": logging_group},
        )
        document.storage_path = selected
        document.save(update_fields=("storage_path",))

    return selected


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


def _path_matches_checksum(path: Path, checksum: str | None) -> bool:
    if checksum is None or not path.is_file():
        return False

    with path.open("rb") as f:
        return hashlib.md5(f.read()).hexdigest() == checksum


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
            move_original = False
            original_already_moved = False

            old_archive_filename = instance.archive_filename
            old_archive_path = instance.archive_path
            move_archive = False
            archive_already_moved = False

            candidate_filename = generate_filename(instance)
            if len(str(candidate_filename)) > Document.MAX_STORED_FILENAME_LENGTH:
                msg = (
                    f"Document {instance!s}: Generated filename exceeds db path "
                    f"limit ({len(str(candidate_filename))} > "
                    f"{Document.MAX_STORED_FILENAME_LENGTH}): {candidate_filename!s}"
                )
                logger.warning(msg)
                raise CannotMoveFilesException(msg)

            candidate_source_path = (
                settings.ORIGINALS_DIR / candidate_filename
            ).resolve()
            if candidate_filename == Path(old_filename):
                new_filename = Path(old_filename)
            elif (
                candidate_source_path.exists()
                and candidate_source_path != old_source_path
            ):
                if not old_source_path.is_file() and _path_matches_checksum(
                    candidate_source_path,
                    instance.checksum,
                ):
                    new_filename = candidate_filename
                    original_already_moved = True
                else:
                    # Only fall back to unique search when there is an actual conflict
                    new_filename = generate_unique_filename(instance)
            else:
                new_filename = candidate_filename

            # Need to convert to string to be able to save it to the db
            instance.filename = str(new_filename)
            move_original = (
                old_filename != instance.filename and not original_already_moved
            )

            if instance.has_archive_version:
                archive_candidate = generate_filename(instance, archive_filename=True)
                if len(str(archive_candidate)) > Document.MAX_STORED_FILENAME_LENGTH:
                    msg = (
                        f"Document {instance!s}: Generated archive filename exceeds "
                        f"db path limit ({len(str(archive_candidate))} > "
                        f"{Document.MAX_STORED_FILENAME_LENGTH}): {archive_candidate!s}"
                    )
                    logger.warning(msg)
                    raise CannotMoveFilesException(msg)
                archive_candidate_path = (
                    settings.ARCHIVE_DIR / archive_candidate
                ).resolve()
                if archive_candidate == Path(old_archive_filename):
                    new_archive_filename = Path(old_archive_filename)
                elif (
                    archive_candidate_path.exists()
                    and archive_candidate_path != old_archive_path
                ):
                    if not old_archive_path.is_file() and _path_matches_checksum(
                        archive_candidate_path,
                        instance.archive_checksum,
                    ):
                        new_archive_filename = archive_candidate
                        archive_already_moved = True
                    else:
                        new_archive_filename = generate_unique_filename(
                            instance,
                            archive_filename=True,
                        )
                else:
                    new_archive_filename = archive_candidate

                instance.archive_filename = str(new_archive_filename)

                move_archive = (
                    old_archive_filename != instance.archive_filename
                    and not archive_already_moved
                )
            else:
                move_archive = False

            if not move_original and not move_archive:
                updates = {"modified": timezone.now()}
                if old_filename != instance.filename:
                    updates["filename"] = instance.filename
                if old_archive_filename != instance.archive_filename:
                    updates["archive_filename"] = instance.archive_filename

                # Don't save() here to prevent infinite recursion.
                Document.objects.filter(pk=instance.pk).update(**updates)
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

    # Keep version files in sync with root
    if instance.root_document_id is None:
        for version_doc in Document.objects.filter(root_document_id=instance.pk).only(
            "pk",
        ):
            update_filename_and_move_files(
                Document,
                version_doc,
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
        process_cf_select_update.apply_async(kwargs={"custom_field": instance})


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
    from documents.search import get_backend

    get_backend().add_or_update(
        document,
        effective_content=document.get_effective_content(),
    )


def run_workflows_added(
    sender,
    document: Document,
    logging_group: uuid.UUID | None = None,
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
    logging_group: uuid.UUID | None = None,
    **kwargs,
) -> None:
    run_workflows(
        trigger_type=WorkflowTrigger.WorkflowTriggerType.DOCUMENT_UPDATED,
        document=document,
        logging_group=logging_group,
    )


def send_websocket_document_updated(
    sender,
    document: Document,
    **kwargs,
) -> None:
    # At this point, workflows may already have applied additional changes.
    document.refresh_from_db()

    from documents.data_models import DocumentMetadataOverrides

    doc_overrides = DocumentMetadataOverrides.from_document(document)

    with DocumentsStatusManager() as status_mgr:
        status_mgr.send_document_updated(
            document_id=document.id,
            modified=DRF_DATETIME_FIELD.to_representation(document.modified),
            owner_id=doc_overrides.owner_id,
            users_can_view=doc_overrides.view_users,
            groups_can_view=doc_overrides.view_groups,
        )


def run_workflows(
    trigger_type: WorkflowTrigger.WorkflowTriggerType,
    document: Document | ConsumableDocument,
    workflow_to_run: Workflow | None = None,
    logging_group: uuid.UUID | None = None,
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

    if isinstance(document, Document) and document.root_document_id is not None:
        logger.debug(
            "Skipping workflow execution for version document %s",
            document.pk,
        )
        return None

    if original_file is None:
        original_file = (
            document.source_path if not use_overrides else document.original_file
        )
    messages = []

    workflows = get_workflows_for_trigger(trigger_type, workflow_to_run)

    for workflow in workflows:
        if not use_overrides:
            if TYPE_CHECKING:
                assert isinstance(document, Document)
            try:
                # This can be called from bulk_update_documents, which may be running multiple times
                # Refresh this so the matching data is fresh and instance fields are re-freshed
                # Otherwise, this instance might be behind and overwrite the work another process did
                document.refresh_from_db()
            except Document.DoesNotExist:
                # Document was hard deleted by a previous workflow or another process
                logger.info(
                    "Document no longer exists, skipping remaining workflows",
                    extra={"group": logging_group},
                )
                break

            # Check if document was soft deleted (moved to trash)
            if document.is_deleted:
                logger.info(
                    "Document was moved to trash, skipping remaining workflows",
                    extra={"group": logging_group},
                )
                break

        if matching.document_matches_workflow(document, workflow, trigger_type):
            action: WorkflowAction
            has_move_to_trash_action = False
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
                            logging_group,
                        )
                elif action.type == WorkflowAction.WorkflowActionType.REMOVAL:
                    if use_overrides and overrides:
                        apply_removal_to_overrides(action, overrides)
                    else:
                        apply_removal_to_document(action, document)
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
                elif action.type == WorkflowAction.WorkflowActionType.MOVE_TO_TRASH:
                    has_move_to_trash_action = True

            if not use_overrides:
                # limit title to 128 characters
                document.title = document.title[:128]
                # Save only the fields that workflow actions can set directly.
                # Deliberately excludes filename and archive_filename — those are
                # managed exclusively by update_filename_and_move_files via the
                # post_save signal. Writing stale in-memory values here would revert
                # a concurrent update_filename_and_move_files DB write, leaving the
                # DB pointing at the old path while the file is already at the new
                # one (see: https://github.com/paperless-ngx/paperless-ngx/issues/12386).
                # modified has auto_now=True but is not auto-added when update_fields
                # is specified, so it must be listed explicitly.
                document.save(
                    update_fields=[
                        "title",
                        "correspondent",
                        "document_type",
                        "storage_path",
                        "owner",
                        "modified",
                    ],
                )

            WorkflowRun.objects.create(
                workflow=workflow,
                type=trigger_type,
                document=document if not use_overrides else None,
            )

            if has_move_to_trash_action:
                execute_move_to_trash_action(action, document, logging_group)

    if use_overrides:
        if TYPE_CHECKING:
            assert overrides is not None
        return overrides, "\n".join(messages)


# ---------------------------------------------------------------------------
# Task tracking -- Celery signal handlers
# ---------------------------------------------------------------------------

TRACKED_TASKS: dict[str, PaperlessTask.TaskType] = {
    "documents.tasks.consume_file": PaperlessTask.TaskType.CONSUME_FILE,
    "documents.tasks.train_classifier": PaperlessTask.TaskType.TRAIN_CLASSIFIER,
    "documents.tasks.sanity_check": PaperlessTask.TaskType.SANITY_CHECK,
    "documents.tasks.llmindex_index": PaperlessTask.TaskType.LLM_INDEX,
    "documents.tasks.empty_trash": PaperlessTask.TaskType.EMPTY_TRASH,
    "documents.tasks.check_scheduled_workflows": PaperlessTask.TaskType.CHECK_WORKFLOWS,
    "paperless_mail.tasks.process_mail_accounts": PaperlessTask.TaskType.MAIL_FETCH,
    "documents.tasks.bulk_update_documents": PaperlessTask.TaskType.BULK_UPDATE,
    "documents.tasks.update_document_content_maybe_archive_file": PaperlessTask.TaskType.REPROCESS_DOCUMENT,
    "documents.tasks.build_share_link_bundle": PaperlessTask.TaskType.BUILD_SHARE_LINK,
    "documents.bulk_edit.delete": PaperlessTask.TaskType.BULK_DELETE,
}

_CELERY_STATE_TO_STATUS: dict[str, PaperlessTask.Status] = {
    "SUCCESS": PaperlessTask.Status.SUCCESS,
    "FAILURE": PaperlessTask.Status.FAILURE,
    "REVOKED": PaperlessTask.Status.REVOKED,
}


def _extract_input_data(
    task_type: PaperlessTask.TaskType,
    task_kwargs: dict,
) -> dict:
    """Build the input_data dict stored on the PaperlessTask record.

    For consume_file tasks this includes the filename, MIME type, and any
    non-null overrides from the DocumentMetadataOverrides object.  For
    mail_fetch tasks it captures the account_ids list.  All other task
    types store no input data and return {}.
    """
    if task_type == PaperlessTask.TaskType.CONSUME_FILE:
        input_doc = task_kwargs.get("input_doc")
        overrides = task_kwargs.get("overrides")
        if input_doc is None:
            return {}
        data: dict = {
            "filename": input_doc.original_file.name,
            "mime_type": input_doc.mime_type,
        }
        if input_doc.original_path:  # pragma: no cover
            data["source_path"] = str(input_doc.original_path)
        if input_doc.mailrule_id:  # pragma: no cover
            data["mailrule_id"] = input_doc.mailrule_id
        if overrides:
            override_dict = {}
            for k, v in vars(overrides).items():
                if v is None or k.startswith("_"):
                    continue
                if isinstance(v, datetime.date):
                    v = v.isoformat()
                elif isinstance(v, Path):
                    v = str(v)
                override_dict[k] = v
            if override_dict:
                data["overrides"] = override_dict
        return data

    if task_type == PaperlessTask.TaskType.MAIL_FETCH:
        account_ids = task_kwargs.get("account_ids")
        if account_ids is not None:
            return {"account_ids": account_ids}
        return {}

    return {}


def _determine_trigger_source(
    headers: dict,
) -> PaperlessTask.TriggerSource:
    """Resolve the TriggerSource for a task being published to the broker.

    Reads the trigger_source header set by the caller; falls back to MANUAL
    when the header is absent or contains an unrecognised value.
    """
    header_source = headers.get("trigger_source")
    if header_source is not None:
        try:
            return PaperlessTask.TriggerSource(header_source)
        except ValueError:
            pass
    return PaperlessTask.TriggerSource.MANUAL


def _extract_owner_id(
    task_type: PaperlessTask.TaskType,
    task_kwargs: dict,
) -> int | None:
    """Return the owner_id from consume_file overrides, or None for all other task types."""
    if task_type != PaperlessTask.TaskType.CONSUME_FILE:
        return None
    overrides = task_kwargs.get("overrides")
    if overrides and hasattr(overrides, "owner_id"):
        return overrides.owner_id
    return None  # pragma: no cover


@before_task_publish.connect
def before_task_publish_handler(
    sender=None,
    headers=None,
    body=None,
    **kwargs,
) -> None:
    """
    Creates the PaperlessTask record when the task is published to broker.

    https://docs.celeryq.dev/en/stable/userguide/signals.html#before-task-publish
    https://docs.celeryq.dev/en/stable/internals/protocol.html#version-2
    """
    if headers is None or body is None:
        return

    task_name = headers.get("task", "")
    task_type = TRACKED_TASKS.get(task_name)
    if task_type is None:
        return

    try:
        _, task_kwargs, _ = body
        task_id = headers["id"]

        input_data = _extract_input_data(task_type, task_kwargs)
        trigger_source = _determine_trigger_source(headers)
        owner_id = _extract_owner_id(task_type, task_kwargs)

        PaperlessTask.objects.create(
            task_id=task_id,
            task_type=task_type,
            trigger_source=trigger_source,
            status=PaperlessTask.Status.PENDING,
            input_data=input_data,
            owner_id=owner_id,
        )
    except Exception:  # pragma: no cover
        logger.exception("Creating PaperlessTask failed")


@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, **kwargs) -> None:
    """
    Marks the task STARTED when execution begins on a worker.

    https://docs.celeryq.dev/en/stable/userguide/signals.html#task-prerun
    """
    if task_id is None:  # pragma: no cover
        return
    if task and task.name not in TRACKED_TASKS:
        return
    try:
        close_old_connections()
        PaperlessTask.objects.filter(task_id=task_id).update(
            status=PaperlessTask.Status.STARTED,
            date_started=timezone.now(),
        )
    except Exception:  # pragma: no cover
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
    Records task completion and result data for non-failure outcomes.

    Skips FAILURE states entirely, since task_failure_handler fires first
    and fully owns the failure path (status, date_done, duration, result_data).

    https://docs.celeryq.dev/en/stable/userguide/signals.html#task-postrun
    """
    if task_id is None:  # pragma: no cover
        return
    if task and task.name not in TRACKED_TASKS:
        return
    try:
        close_old_connections()

        new_status = _CELERY_STATE_TO_STATUS.get(state, PaperlessTask.Status.FAILURE)
        if new_status == PaperlessTask.Status.FAILURE:
            return

        now = timezone.now()
        try:
            task_instance = PaperlessTask.objects.get(task_id=task_id)
        except PaperlessTask.DoesNotExist:
            return

        task_instance.status = new_status
        task_instance.date_done = now
        changed_fields = ["status", "date_done"]

        if task_instance.date_started:
            task_instance.duration_seconds = (
                now - task_instance.date_started
            ).total_seconds()
            changed_fields.append("duration_seconds")
        if task_instance.date_started and task_instance.date_created:
            task_instance.wait_time_seconds = (
                task_instance.date_started - task_instance.date_created
            ).total_seconds()
            changed_fields.append("wait_time_seconds")

        if isinstance(retval, dict):
            task_instance.result_data = retval
            changed_fields.append("result_data")
            if "duplicate_of" in retval:
                task_instance.status = PaperlessTask.Status.FAILURE
                changed_fields.append("status")

        task_instance.save(update_fields=changed_fields)
    except Exception:  # pragma: no cover
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
    Records failure details when a task raises an exception.

    Fully owns the FAILURE path. task_postrun_handler skips FAILURE
    states so there is no overlap.

    https://docs.celeryq.dev/en/stable/userguide/signals.html#task-failure
    """
    if task_id is None:  # pragma: no cover
        return
    if sender and sender.name not in TRACKED_TASKS:  # pragma: no cover
        return
    try:
        close_old_connections()

        result_data: dict = {
            "error_type": type(exception).__name__ if exception else "Unknown",
            "error_message": str(exception) if exception else "Unknown error",
        }
        if traceback:
            tb_str = "".join(_tb.format_tb(traceback))
            result_data["traceback"] = tb_str[:5000]

        now = timezone.now()
        update_fields: dict = {
            "status": PaperlessTask.Status.FAILURE,
            "result_data": result_data,
            "date_done": now,
        }

        task_qs = PaperlessTask.objects.filter(task_id=task_id)
        task_instance = task_qs.values("date_started", "date_created").first()
        if task_instance:
            date_started = task_instance["date_started"]
            if date_started:
                update_fields["duration_seconds"] = (now - date_started).total_seconds()
            date_created = task_instance["date_created"]
            if date_started and date_created:
                update_fields["wait_time_seconds"] = (
                    date_started - date_created
                ).total_seconds()
            task_qs.update(**update_fields)
    except Exception:  # pragma: no cover
        logger.exception("Updating PaperlessTask on failure failed")


@task_revoked.connect
def task_revoked_handler(
    sender=None,
    request=None,
    *,
    terminated: bool = False,
    signum=None,
    expired: bool = False,
    **kwargs,
) -> None:
    """
    Marks the task REVOKED when it is cancelled before or during execution.

    This fires for tasks revoked while still queued (before task_prerun) as
    well as for tasks terminated mid-run.  task_postrun does NOT fire for
    pre-start revocations, so this handler is the only way to move those
    records out of PENDING.

    https://docs.celeryq.dev/en/stable/userguide/signals.html#task-revoked
    """
    task_id = request.id if request else None
    if task_id is None:  # pragma: no cover
        return
    if sender and sender.name not in TRACKED_TASKS:  # pragma: no cover
        return
    try:
        close_old_connections()
        PaperlessTask.objects.filter(task_id=task_id).update(
            status=PaperlessTask.Status.REVOKED,
            date_done=timezone.now(),
        )
    except Exception:  # pragma: no cover
        logger.exception("Updating PaperlessTask on revocation failed")


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

        update_document_in_llm_index.apply_async(kwargs={"document": document})


@receiver(models.signals.post_delete, sender=Document)
def delete_document_from_llm_index(
    sender: Any,
    instance: Document,
    **kwargs: Any,
) -> None:
    """
    Delete a document from the LLM index when it is deleted.
    """
    ai_config = AIConfig()
    if ai_config.llm_index_enabled:
        from documents.tasks import remove_document_from_llm_index

        remove_document_from_llm_index.apply_async(kwargs={"document": instance})
