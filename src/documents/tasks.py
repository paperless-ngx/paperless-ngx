import datetime
import logging
import shutil
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from tempfile import mkstemp

from celery import Task
from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db import transaction
from django.db.models.signals import post_save
from django.utils import timezone
from filelock import FileLock

from documents import sanity_checker
from documents.barcodes import BarcodePlugin
from documents.bulk_download import ArchiveOnlyStrategy
from documents.bulk_download import OriginalsOnlyStrategy
from documents.caching import clear_document_caches
from documents.classifier import DocumentClassifier
from documents.classifier import load_classifier
from documents.consumer import AsnCheckPlugin
from documents.consumer import ConsumeFileDuplicateError
from documents.consumer import ConsumerPlugin
from documents.consumer import ConsumerPreflightPlugin
from documents.consumer import WorkflowTriggerPlugin
from documents.consumer import should_produce_archive
from documents.data_models import ConsumableDocument
from documents.data_models import ConsumeFileDuplicateResult
from documents.data_models import ConsumeFileStoppedResult
from documents.data_models import ConsumeFileSuccessResult
from documents.data_models import DocumentMetadataOverrides
from documents.double_sided import CollatePlugin
from documents.file_handling import create_source_path_directory
from documents.file_handling import generate_unique_filename
from documents.matching import prefilter_documents_by_workflowtrigger
from documents.models import Correspondent
from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import DocumentType
from documents.models import PaperlessTask
from documents.models import ShareLink
from documents.models import ShareLinkBundle
from documents.models import StoragePath
from documents.models import Tag
from documents.models import WorkflowRun
from documents.models import WorkflowTrigger
from documents.plugins.base import ConsumeTaskPlugin
from documents.plugins.base import StopConsumeTaskError
from documents.plugins.helpers import ProgressManager
from documents.plugins.helpers import ProgressStatusOptions
from documents.sanity_checker import SanityCheckFailedException
from documents.signals import document_updated
from documents.signals.handlers import cleanup_document_deletion
from documents.signals.handlers import run_workflows
from documents.signals.handlers import send_websocket_document_updated
from documents.utils import IterWrapper
from documents.utils import compute_checksum
from documents.utils import identity
from documents.workflows.utils import get_workflows_for_trigger
from paperless.config import AIConfig
from paperless.logging import consume_task_id
from paperless.parsers import ParserContext
from paperless.parsers.registry import get_parser_registry
from paperless_ai.indexing import llm_index_add_or_update_document
from paperless_ai.indexing import llm_index_remove_document
from paperless_ai.indexing import update_llm_index

if settings.AUDIT_LOG_ENABLED:
    from auditlog.models import LogEntry
logger = logging.getLogger("paperless.tasks")


@shared_task
def index_optimize() -> None:
    logger.info(
        "index_optimize is a no-op — Tantivy manages segment merging automatically.",
    )


@shared_task
def train_classifier(
    *,
    status_callback: Callable[[str], None] | None = None,
) -> str:
    if (
        not Tag.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not DocumentType.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not Correspondent.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not StoragePath.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
    ):
        result = "No automatic matching items, not training"
        logger.info(result)
        # Special case, items were once auto and trained, so remove the model
        # and prevent its use again
        if settings.MODEL_FILE.exists():  # pragma: no cover
            logger.info(f"Removing {settings.MODEL_FILE} so it won't be used")
            settings.MODEL_FILE.unlink()
        return result

    classifier = load_classifier()

    if not classifier:
        classifier = DocumentClassifier()

    if classifier.train(status_callback=status_callback):
        logger.info(
            f"Saving updated classifier model to {settings.MODEL_FILE}...",
        )
        classifier.save()
        return "Training completed successfully"
    else:
        logger.debug("Training data unchanged.")
        return "Training data unchanged"


@shared_task(bind=True)
def consume_file(
    self: Task,
    input_doc: ConsumableDocument,
    overrides: DocumentMetadataOverrides | None = None,
) -> (
    ConsumeFileSuccessResult
    | ConsumeFileStoppedResult
    | ConsumeFileDuplicateResult
    | None
):
    token = consume_task_id.set((self.request.id or "")[:8])
    try:
        # Default no overrides
        if overrides is None:
            overrides = DocumentMetadataOverrides()

        plugins: list[type[ConsumeTaskPlugin]] = (
            [
                ConsumerPreflightPlugin,
                ConsumerPlugin,
            ]
            if input_doc.root_document_id is not None
            else [
                ConsumerPreflightPlugin,
                AsnCheckPlugin,
                CollatePlugin,
                BarcodePlugin,
                AsnCheckPlugin,  # Re-run ASN check after barcode reading
                WorkflowTriggerPlugin,
                ConsumerPlugin,
            ]
        )

        with (
            ProgressManager(
                overrides.filename or input_doc.original_file.name,
                self.request.id,
            ) as status_mgr,
            TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir,
        ):
            tmp_dir = Path(tmp_dir)
            msg = None
            for plugin_class in plugins:
                plugin_name = plugin_class.NAME

                plugin = plugin_class(
                    input_doc,
                    overrides,
                    status_mgr,
                    tmp_dir,
                    self.request.id,
                )

                if not plugin.able_to_run:
                    logger.debug(f"Skipping plugin {plugin_name}")
                    continue

                try:
                    logger.debug(f"Executing plugin {plugin_name}")
                    plugin.setup()

                    msg = plugin.run()

                    if msg is not None:
                        logger.info(f"{plugin_name} completed with: {msg}")
                    else:
                        logger.info(f"{plugin_name} completed with no message")

                    overrides = plugin.metadata

                except StopConsumeTaskError as e:
                    logger.info(f"{plugin_name} requested task exit: {e.message}")
                    return ConsumeFileStoppedResult(reason=e.message)

                except ConsumeFileDuplicateError as e:
                    logger.info(f"{plugin_name} rejected duplicate: {e}")
                    return ConsumeFileDuplicateResult(
                        duplicate_of=e.duplicate_id,
                        duplicate_in_trash=e.in_trash,
                    )

                except Exception as e:
                    logger.exception(f"{plugin_name} failed: {e}")
                    status_mgr.send_progress(
                        ProgressStatusOptions.FAILED,
                        f"{e}",
                        100,
                        100,
                    )
                    raise

                finally:
                    plugin.cleanup()

        return msg
    finally:
        consume_task_id.reset(token)


@shared_task
def sanity_check(*, raise_on_error: bool = True) -> str:
    messages = sanity_checker.check_sanity()
    messages.log_messages()

    if not messages.has_error and not messages.has_warning and not messages.has_info:
        return "No issues detected."

    parts: list[str] = []
    if messages.document_error_count:
        parts.append(f"{messages.document_error_count} document(s) with errors")
    if messages.document_warning_count:
        parts.append(f"{messages.document_warning_count} document(s) with warnings")
    if messages.document_info_count:
        parts.append(f"{messages.document_info_count} document(s) with infos")
    if messages.global_warning_count:
        parts.append(f"{messages.global_warning_count} global warning(s)")

    summary = ", ".join(parts) + " found."

    if messages.has_error:
        message = summary + " Check logs for details."
        if raise_on_error:
            raise SanityCheckFailedException(message)
        return message

    return summary


@shared_task
def bulk_update_documents(document_ids) -> None:
    from documents.search import get_backend

    documents = Document.objects.filter(id__in=document_ids)

    for doc in documents:
        clear_document_caches(doc.pk)
        document_updated.send(
            sender=None,
            document=doc,
            logging_group=uuid.uuid4(),
        )
        post_save.send(Document, instance=doc, created=False)

    with get_backend().batch_update() as batch:
        for doc in documents:
            batch.add_or_update(doc)

    ai_config = AIConfig()
    if ai_config.llm_index_enabled:
        update_llm_index(
            rebuild=False,
        )


@shared_task
def update_document_content_maybe_archive_file(document_id) -> None:
    """
    Re-creates OCR content and thumbnail for a document, and archive file if
    it exists.
    """
    document = Document.objects.get(id=document_id)

    mime_type = document.mime_type

    parser_class = get_parser_registry().get_parser_for_file(
        mime_type,
        document.original_filename or "",
        document.source_path,
    )

    if not parser_class:
        logger.error(
            f"No parser found for mime type {mime_type}, cannot "
            f"archive document {document} (ID: {document_id})",
        )
        return

    with parser_class() as parser:
        parser.configure(ParserContext())

        try:
            produce_archive = should_produce_archive(
                parser,
                mime_type,
                document.source_path,
            )
            parser.parse(
                document.source_path,
                mime_type,
                produce_archive=produce_archive,
            )

            thumbnail = parser.get_thumbnail(document.source_path, mime_type)

            with transaction.atomic():
                oldDocument = Document.objects.get(pk=document.pk)
                if parser.get_archive_path():
                    checksum = compute_checksum(parser.get_archive_path())
                    # I'm going to save first so that in case the file move
                    # fails, the database is rolled back.
                    # We also don't use save() since that triggers the filehandling
                    # logic, and we don't want that yet (file not yet in place)
                    document.archive_filename = generate_unique_filename(
                        document,
                        archive_filename=True,
                    )
                    Document.objects.filter(pk=document.pk).update(
                        archive_checksum=checksum,
                        content=parser.get_text(),
                        archive_filename=document.archive_filename,
                    )
                    newDocument = Document.objects.get(pk=document.pk)
                    if settings.AUDIT_LOG_ENABLED:
                        LogEntry.objects.log_create(
                            instance=oldDocument,
                            changes={
                                "content": [oldDocument.content, newDocument.content],
                                "archive_checksum": [
                                    oldDocument.archive_checksum,
                                    newDocument.archive_checksum,
                                ],
                                "archive_filename": [
                                    oldDocument.archive_filename,
                                    newDocument.archive_filename,
                                ],
                            },
                            additional_data={
                                "reason": "Update document content",
                            },
                            action=LogEntry.Action.UPDATE,
                        )
                else:
                    Document.objects.filter(pk=document.pk).update(
                        content=parser.get_text(),
                    )

                    if settings.AUDIT_LOG_ENABLED:
                        LogEntry.objects.log_create(
                            instance=oldDocument,
                            changes={
                                "content": [oldDocument.content, parser.get_text()],
                            },
                            additional_data={
                                "reason": "Update document content",
                            },
                            action=LogEntry.Action.UPDATE,
                        )

                with FileLock(settings.MEDIA_LOCK):
                    if parser.get_archive_path():
                        create_source_path_directory(document.archive_path)
                        shutil.move(parser.get_archive_path(), document.archive_path)
                    shutil.move(thumbnail, document.thumbnail_path)

            document.refresh_from_db()
            logger.info(
                f"Updating index for document {document_id} ({document.archive_checksum})",
            )
            from documents.search import get_backend

            get_backend().add_or_update(document)

            ai_config = AIConfig()
            if ai_config.llm_index_enabled:
                llm_index_add_or_update_document(document)

            clear_document_caches(document.pk)

        except Exception:
            logger.exception(
                f"Error while parsing document {document} (ID: {document_id})",
            )


@shared_task
def empty_trash(doc_ids=None) -> None:
    if doc_ids is None:
        logger.info("Emptying trash of all expired documents")
    documents = (
        Document.deleted_objects.filter(id__in=doc_ids)
        if doc_ids is not None
        else Document.deleted_objects.filter(
            deleted_at__lt=timezone.localtime(timezone.now())
            - datetime.timedelta(
                days=settings.EMPTY_TRASH_DELAY,
            ),
        )
    )

    try:
        deleted_document_ids = list(documents.values_list("id", flat=True))
        # Temporarily connect the cleanup handler
        models.signals.post_delete.connect(cleanup_document_deletion, sender=Document)
        documents.delete()  # this is effectively a hard delete
        logger.info(f"Deleted {len(deleted_document_ids)} documents from trash")

        if settings.AUDIT_LOG_ENABLED:
            # Delete the audit log entries for documents that dont exist anymore
            LogEntry.objects.filter(
                content_type=ContentType.objects.get_for_model(Document),
                object_id__in=deleted_document_ids,
            ).delete()
    except Exception as e:  # pragma: no cover
        logger.exception(f"Error while emptying trash: {e}")
    finally:
        models.signals.post_delete.disconnect(
            cleanup_document_deletion,
            sender=Document,
        )


@shared_task
def check_scheduled_workflows() -> None:
    """
    Check and run all enabled scheduled workflows.

    Scheduled triggers are evaluated based on a target date field (e.g. added, created, modified, or a custom date field),
    combined with a day offset:
        - Positive offsets mean the workflow should trigger AFTER the specified date (e.g., offset = +7 → trigger 7 days after)
        - Negative offsets mean the workflow should trigger BEFORE the specified date (e.g., offset = -7 → trigger 7 days before)

    Once a document satisfies this condition, and recurring/non-recurring constraints are met, the workflow is run.
    """
    scheduled_workflows = get_workflows_for_trigger(
        WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
    )
    if scheduled_workflows.count() > 0:
        logger.debug(f"Checking {len(scheduled_workflows)} scheduled workflows")
        now = timezone.now()
        for workflow in scheduled_workflows:
            schedule_triggers = workflow.triggers.filter(
                type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
            )
            trigger: WorkflowTrigger
            for trigger in schedule_triggers:
                documents = Document.objects.none()
                offset_td = datetime.timedelta(days=trigger.schedule_offset_days)
                threshold = now - offset_td
                logger.debug(
                    f"Trigger {trigger.id}: checking if (date + {offset_td}) <= now ({now})",
                )

                match trigger.schedule_date_field:
                    case WorkflowTrigger.ScheduleDateField.ADDED:
                        documents = Document.objects.filter(
                            root_document__isnull=True,
                            added__lte=threshold,
                        )

                    case WorkflowTrigger.ScheduleDateField.CREATED:
                        documents = Document.objects.filter(
                            root_document__isnull=True,
                            created__lte=threshold,
                        )

                    case WorkflowTrigger.ScheduleDateField.MODIFIED:
                        documents = Document.objects.filter(
                            root_document__isnull=True,
                            modified__lte=threshold,
                        )

                    case WorkflowTrigger.ScheduleDateField.CUSTOM_FIELD:
                        # cap earliest date to avoid massive scans
                        earliest_date = now - datetime.timedelta(days=365)
                        if offset_td.days < -365:
                            logger.warning(
                                f"Trigger {trigger.id} has large negative offset ({offset_td.days}), "
                                f"limiting earliest scan date to {earliest_date}",
                            )

                        cf_filter_kwargs = {
                            "field": trigger.schedule_date_custom_field,
                            "value_date__isnull": False,
                            "value_date__lte": threshold,
                            "value_date__gte": earliest_date,
                        }

                        recent_cf_instances = CustomFieldInstance.objects.filter(
                            **cf_filter_kwargs,
                        )

                        matched_ids = [
                            cfi.document_id
                            for cfi in recent_cf_instances
                            if cfi.value_date
                            and (
                                timezone.make_aware(
                                    datetime.datetime.combine(
                                        cfi.value_date,
                                        datetime.time.min,
                                    ),
                                )
                                + offset_td
                                <= now
                            )
                        ]

                        documents = Document.objects.filter(
                            root_document__isnull=True,
                            id__in=matched_ids,
                        )

                if documents.exists():
                    documents = prefilter_documents_by_workflowtrigger(
                        documents,
                        trigger,
                    )

                if documents.exists():
                    logger.debug(
                        f"Found {documents.count()} documents for trigger {trigger}",
                    )
                    for document in documents:
                        workflow_runs = WorkflowRun.objects.filter(
                            document=document,
                            type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
                            workflow=workflow,
                        ).order_by("-run_at")
                        if not trigger.schedule_is_recurring and workflow_runs.exists():
                            logger.debug(
                                f"Skipping document {document} for non-recurring workflow {workflow} as it has already been run",
                            )
                            continue

                        if (
                            trigger.schedule_is_recurring
                            and workflow_runs.exists()
                            and (
                                workflow_runs.first().run_at
                                > now
                                - datetime.timedelta(
                                    days=trigger.schedule_recurring_interval_days,
                                )
                            )
                        ):
                            # schedule is recurring but the last run was within the number of recurring interval days
                            logger.debug(
                                f"Skipping document {document} for recurring workflow {workflow} as the last run was within the recurring interval",
                            )
                            continue
                        run_workflows(
                            trigger_type=WorkflowTrigger.WorkflowTriggerType.SCHEDULED,
                            workflow_to_run=workflow,
                            document=document,
                        )
                        # Scheduled workflows dont send document_updated signal, so send a websocket update here to ensure clients are updated
                        send_websocket_document_updated(
                            sender=None,
                            document=document,
                        )


def update_document_parent_tags(tag: Tag, new_parent: Tag) -> None:
    """
    When a tag's parent changes, ensure all documents containing the tag also have
    the parent tag (and its ancestors) applied.
    """
    doc_tag_relationship = Document.tags.through

    doc_ids: list[int] = list(
        Document.objects.filter(tags=tag).values_list("pk", flat=True),
    )

    if not doc_ids:
        return

    parent_ids = [new_parent.id, *new_parent.get_ancestors_pks()]

    parent_ids = list(dict.fromkeys(parent_ids))

    existing_pairs = set(
        doc_tag_relationship.objects.filter(
            document_id__in=doc_ids,
            tag_id__in=parent_ids,
        ).values_list("document_id", "tag_id"),
    )

    to_create: list = []
    affected: set[int] = set()

    for doc_id in doc_ids:
        for parent_id in parent_ids:
            if (doc_id, parent_id) in existing_pairs:
                continue

            to_create.append(
                doc_tag_relationship(document_id=doc_id, tag_id=parent_id),
            )
            affected.add(doc_id)

    if to_create:
        doc_tag_relationship.objects.bulk_create(
            to_create,
            ignore_conflicts=True,
        )

    if affected:
        bulk_update_documents.apply_async(
            kwargs={"document_ids": list(affected)},
            headers={"trigger_source": PaperlessTask.TriggerSource.SYSTEM},
        )


@shared_task
def llmindex_index(
    *,
    iter_wrapper: IterWrapper[Document] = identity,
    rebuild: bool = False,
) -> str | None:
    ai_config = AIConfig()
    if not ai_config.llm_index_enabled:  # pragma: no cover
        logger.info("LLM index is disabled, skipping update.")
        return None

    from paperless_ai.indexing import update_llm_index

    return update_llm_index(
        iter_wrapper=iter_wrapper,
        rebuild=rebuild,
    )


@shared_task
def update_document_in_llm_index(document) -> None:
    llm_index_add_or_update_document(document)


@shared_task
def remove_document_from_llm_index(document) -> None:
    llm_index_remove_document(document)


@shared_task
def build_share_link_bundle(bundle_id: int) -> None:
    try:
        bundle = (
            ShareLinkBundle.objects.filter(pk=bundle_id)
            .prefetch_related("documents")
            .get()
        )
    except ShareLinkBundle.DoesNotExist:
        logger.warning("Share link bundle %s no longer exists.", bundle_id)
        return

    bundle.remove_file()
    bundle.status = ShareLinkBundle.Status.PROCESSING
    bundle.last_error = None
    bundle.size_bytes = None
    bundle.built_at = None
    bundle.file_path = ""
    bundle.save(
        update_fields=[
            "status",
            "last_error",
            "size_bytes",
            "built_at",
            "file_path",
        ],
    )

    documents = list(bundle.documents.all().order_by("pk"))

    _, temp_zip_path_str = mkstemp(suffix=".zip", dir=settings.SCRATCH_DIR)
    temp_zip_path = Path(temp_zip_path_str)

    try:
        strategy_class = (
            ArchiveOnlyStrategy
            if bundle.file_version == ShareLink.FileVersion.ARCHIVE
            else OriginalsOnlyStrategy
        )
        with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            strategy = strategy_class(zipf)
            for document in documents:
                strategy.add_document(document)

        output_dir = settings.SHARE_LINK_BUNDLE_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        final_path = (output_dir / f"{bundle.slug}.zip").resolve()
        if final_path.exists():
            final_path.unlink()
        shutil.move(temp_zip_path, final_path)

        bundle.file_path = f"{bundle.slug}.zip"
        bundle.size_bytes = final_path.stat().st_size
        bundle.status = ShareLinkBundle.Status.READY
        bundle.built_at = timezone.now()
        bundle.last_error = None
        bundle.save(
            update_fields=[
                "file_path",
                "size_bytes",
                "status",
                "built_at",
                "last_error",
            ],
        )
        logger.info("Built share link bundle %s", bundle.pk)
    except Exception as exc:
        logger.exception(
            "Failed to build share link bundle %s: %s",
            bundle_id,
            exc,
        )
        bundle.status = ShareLinkBundle.Status.FAILED
        bundle.last_error = {
            "bundle_id": bundle_id,
            "exception_type": exc.__class__.__name__,
            "message": str(exc),
            "timestamp": timezone.now().isoformat(),
        }
        bundle.save(update_fields=["status", "last_error"])
        try:
            temp_zip_path.unlink()
        except OSError:
            pass
        raise
    finally:
        try:
            temp_zip_path.unlink(missing_ok=True)
        except OSError:
            pass


@shared_task
def cleanup_expired_share_link_bundles() -> None:
    now = timezone.now()
    expired_qs = ShareLinkBundle.objects.filter(
        expiration__isnull=False,
        expiration__lt=now,
    )
    count = 0
    for bundle in expired_qs.iterator():
        count += 1
        try:
            bundle.delete()
        except Exception as exc:
            logger.warning(
                "Failed to delete expired share link bundle %s: %s",
                bundle.pk,
                exc,
            )
    if count:
        logger.info("Deleted %s expired share link bundle(s)", count)
