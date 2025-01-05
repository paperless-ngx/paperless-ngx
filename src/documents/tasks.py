import hashlib
import logging
import os
import shutil
import uuid
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, final

import tqdm
from celery import Task
from celery import shared_task
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.serializers import deserialize, serialize
from django.db import transaction, models
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from filelock import FileLock
from whoosh.writing import AsyncWriter

from documents import index
from documents import sanity_checker
from documents.barcodes import BarcodePlugin
from documents.caching import clear_document_caches
from documents.classifier import DocumentClassifier
from documents.classifier import load_classifier
from documents.consumer import Consumer, get_config_dossier_form
from documents.consumer import ConsumerError
from documents.consumer import WorkflowTriggerPlugin
from documents.data_models import ConsumableDocument
from documents.data_models import DocumentMetadataOverrides
from documents.double_sided import CollatePlugin
from documents.file_handling import create_source_path_directory
from documents.file_handling import generate_unique_filename
from documents.models import Correspondent, CustomFieldInstance, Dossier, \
    BackupRecord
from documents.models import Document
from documents.models import DocumentType
from documents.models import Folder
from documents.models import StoragePath
from documents.models import Tag
from documents.models import Warehouse
from documents.parsers import DocumentParser
from documents.parsers import custom_get_parser_class_for_mime_type
from documents.plugins.base import ConsumeTaskPlugin
from documents.plugins.base import ProgressManager
from documents.plugins.base import StopConsumeTaskError
from documents.plugins.helpers import ProgressStatusOptions
from documents.sanity_checker import SanityCheckFailedException
from documents.signals import document_updated
from documents.signals.handlers import cleanup_document_deletion
from documents.utils import generate_unique_name
from paperless.models import ApplicationConfiguration
from paperless_ocr_custom.parsers import RasterisedDocumentCustomParser


if settings.AUDIT_LOG_ENABLED:
    import json

    from auditlog.models import LogEntry
logger = logging.getLogger("paperless.tasks")

def revoke_permission():
    logger.debug('run')
    # today = date.today()
    # approvals = Approval.objects.filter(
    #     status="SUCCESS",
    #     expiration__date=today
    # )
    # approvals.update(status="REVOKED")
    # for approval in approvals:
    #     approvals.send(
    #         sender=Document,
    #         approval=approval,
    #     )
    # logger.info('Check all expired approvals')
    # thirty_days_ago = datetime.now() - timedelta(days=30)

    # approvals_reject = Approval.objects.filter(
    #     status__in=["REJECT", "REVOKED"],
    #     expiration__lte=thirty_days_ago

    # ).delete()



@shared_task
def index_optimize():
    ix = index.open_index()
    writer = AsyncWriter(ix)
    writer.commit(optimize=True)


def index_reindex(progress_bar_disable=False):
    documents = Document.objects.all()

    ix = index.open_index(recreate=True)

    with AsyncWriter(ix) as writer:
        for document in tqdm.tqdm(documents, disable=progress_bar_disable):
            index.update_document(writer, document)


@shared_task
def train_classifier():
    if (
        not Tag.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not DocumentType.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not Correspondent.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not Warehouse.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not Folder.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
        and not StoragePath.objects.filter(matching_algorithm=Tag.MATCH_AUTO).exists()
    ):
        logger.info("No automatic matching items, not training")
        # Special case, items were once auto and trained, so remove the model
        # and prevent its use again
        if settings.MODEL_FILE.exists():
            logger.info(f"Removing {settings.MODEL_FILE} so it won't be used")
            settings.MODEL_FILE.unlink()
        return

    classifier = load_classifier()

    if not classifier:
        classifier = DocumentClassifier()

    try:
        if classifier.train():
            logger.info(
                f"Saving updated classifier model to {settings.MODEL_FILE}...",
            )
            classifier.save()
        else:
            logger.debug("Training data unchanged.")

    except Exception as e:
        logger.warning("Classifier error: " + str(e))


@shared_task(bind=True)
def consume_file(
    self: Task,
    input_doc: ConsumableDocument,
    overrides: Optional[DocumentMetadataOverrides] = None,
):
    # Default no overrides
    if overrides is None:
        overrides = DocumentMetadataOverrides()

    plugins: list[type[ConsumeTaskPlugin]] = [
        CollatePlugin,
        BarcodePlugin,
        WorkflowTriggerPlugin,
    ]

    with ProgressManager(
        overrides.filename or input_doc.original_file.name,
        self.request.id,
    ) as status_mgr, TemporaryDirectory(dir=settings.SCRATCH_DIR) as tmp_dir:
        tmp_dir = Path(tmp_dir)
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
                return e.message

            except Exception as e:
                logger.exception(f"{plugin_name} failed: {e}")
                status_mgr.send_progress(ProgressStatusOptions.FAILED, f"{e}", 100, 100)
                raise

            finally:
                plugin.cleanup()

    # continue with consumption if no barcode was found
    document = Consumer().try_consume_file(
        input_doc.original_file,
        override_filename=overrides.filename,
        override_title=overrides.title,
        override_correspondent_id=overrides.correspondent_id,
        override_document_type_id=overrides.document_type_id,
        override_tag_ids=overrides.tag_ids,
        override_warehouse_id=overrides.warehouse_id,
        override_folder_id=overrides.folder_id,
        override_dossier_id=overrides.dossier_id,
        override_storage_path_id=overrides.storage_path_id,
        override_created=overrides.created,
        override_asn=overrides.asn,
        override_owner_id=overrides.owner_id,
        override_view_users=overrides.view_users,
        override_view_groups=overrides.view_groups,
        override_change_users=overrides.change_users,
        override_change_groups=overrides.change_groups,
        override_custom_field_ids=overrides.custom_field_ids,
        task_id=self.request.id,
    )

    if document:
        return f"Success. New document id {document.pk} created"
    else:
        raise ConsumerError(
            "Unknown error: Returned document was null, but "
            "no error message was given.",
        )


@shared_task
def sanity_check():
    messages = sanity_checker.check_sanity()

    messages.log_messages()

    if messages.has_error:
        raise SanityCheckFailedException("Sanity check failed with errors. See log.")
    elif messages.has_warning:
        return "Sanity check exited with warnings. See log."
    elif len(messages) > 0:
        return "Sanity check exited with infos. See log."
    else:
        return "No issues detected."


@shared_task
def bulk_update_documents(document_ids):
    documents = Document.objects.filter(id__in=document_ids)

    ix = index.open_index()

    for doc in documents:
        clear_document_caches(doc.pk)
        document_updated.send(
            sender=None,
            document=doc,
            logging_group=uuid.uuid4(),
        )
        post_save.send(Document, instance=doc, created=False)

    with AsyncWriter(ix) as writer:
        for doc in documents:
            index.update_document(writer, doc)


@shared_task
def update_document_archive_file(document_id=None):
    """
    Re-creates the archive file of a document, including new OCR content and thumbnail
    """


    document = Document.objects.get(id=document_id)

    mime_type = document.mime_type

    parser_class: type[DocumentParser] = custom_get_parser_class_for_mime_type(mime_type)

    if not parser_class:
        logger.error(
            f"No parser found for mime type {mime_type}, cannot "
            f"archive document {document} (ID: {document_id})",
        )
        return

    parser: DocumentParser = parser_class(logging_group=uuid.uuid4())

    try:
        enable_ocr = ApplicationConfiguration.objects.filter().first().enable_ocr
        if enable_ocr:
            # self.log.debug(f"Parsing {self.filename}...")

            if isinstance(parser,RasterisedDocumentCustomParser):
                dossier = None
                if document.dossier is not None:
                    dossier = Dossier.objects.filter(id = document.dossier.id).first()

                parent_dossier = None
                if dossier is not None:
                    parent_dossier = dossier.parent_dossier
                data_ocr_fields = parser.parse(document.source_path, mime_type, document.get_public_filename(), get_config_dossier_form(parent_dossier))
            else:
                parser.parse(document.source_path, mime_type, document.get_public_filename())
        # parser.parse(document.source_path, mime_type, document.get_public_filename())

        thumbnail = parser.get_thumbnail(
            document.source_path,
            mime_type,
            document.get_public_filename(),
        )

        if parser.get_archive_path():
            with transaction.atomic():
                with open(parser.get_archive_path(), "rb") as f:
                    checksum = hashlib.md5(f.read()).hexdigest()
                # I'm going to save first so that in case the file move
                # fails, the database is rolled back.
                # We also don't use save() since that triggers the filehandling
                # logic, and we don't want that yet (file not yet in place)
                document.archive_filename = generate_unique_filename(
                    document,
                    archive_filename=True,
                )
                oldDocument = Document.objects.get(pk=document.pk)
                Document.objects.filter(pk=document.pk).update(
                    archive_checksum=checksum,
                    content=parser.get_text(),
                    archive_filename=document.archive_filename,
                )
                newDocument = Document.objects.get(pk=document.pk)
                if settings.AUDIT_LOG_ENABLED:
                    LogEntry.objects.log_create(
                        instance=oldDocument,
                        changes=json.dumps(
                            {
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
                        ),
                        additional_data=json.dumps(
                            {
                                "reason": "Redo OCR called",
                            },
                        ),
                        action=LogEntry.Action.UPDATE,
                    )

                with FileLock(settings.MEDIA_LOCK):
                    create_source_path_directory(document.archive_path)
                    shutil.move(parser.get_archive_path(), document.archive_path)
                    shutil.move(thumbnail, document.thumbnail_path)

            with index.open_index_writer() as writer:
                index.update_document(writer, document)

            clear_document_caches(document.pk)

    except Exception as ex:
        logger.exception(
            f"Error while parsing document {document} (ID: {document_id} ex: {ex}) ",
        )
        return  f"Error while parsing document {document} (ID: {document_id} ex: {ex}) "
    finally:
        parser.cleanup()
    return f"Success. New document id {document.pk} created"



@shared_task
def update_document_field(document_id):
    """
    Re-creates the archive file of a document, including new OCR content and thumbnail
    """
    document = Document.objects.get(id=document_id)

    mime_type = document.mime_type

    parser_class: type[DocumentParser] = custom_get_parser_class_for_mime_type(mime_type)

    if not parser_class:
        logger.error(
            f"No parser found for mime type {mime_type}, cannot "
            f"archive document {document} (ID: {document_id})",
        )
        return

    parser: DocumentParser = parser_class(logging_group=uuid.uuid4())

    try:
        data_ocr_fields = parser.parse(document.source_path, mime_type, document.get_public_filename())


        if parser.get_archive_path():
            with transaction.atomic():
                oldDocument = Document.objects.get(pk=document.pk)
                fields = CustomFieldInstance.objects.filter(
                                    document=document,
                                )
                dict_data = {}
                try:
                    if data_ocr_fields is not None:
                        if isinstance(data_ocr_fields[0],list):

                            for r in data_ocr_fields[0][0].get("fields"):
                                dict_data[r.get("name")] = r.get("values")[0].get("value") if r.get("values") else None
                            user_args=ApplicationConfiguration.objects.filter().first().user_args
                            mapping_field_user_args = []
                            for f in user_args.get("form_code",[]):
                                if f.get("name") == data_ocr_fields[1]:
                                    mapping_field_user_args = f.get("mapping",[])
                            map_fields = {}

                            for key,value in mapping_field_user_args[0].items():
                                map_fields[key]=dict_data.get(value)
                            for f in fields:
                                f.value_text = map_fields.get(f.field.name,None)
                            CustomFieldInstance.objects.bulk_update(fields, ['value_text'])
                except Exception as e:
                    logger.exception(f"Error while parsing field form document {document} (ID: {document_id})",
                    # self.log.error("error ocr field",e)
        )
                if settings.AUDIT_LOG_ENABLED:
                    LogEntry.objects.log_create(
                        instance=oldDocument,
                        changes=json.dumps(
                            {
                                "content": [oldDocument.content],
                            },
                        ),
                        additional_data=json.dumps(
                            {
                                "reason": "Redo Peeling Field called",
                            },
                        ),
                        action=LogEntry.Action.UPDATE,
                    )

    except Exception:
        logger.exception(
            f"Error while parsing document {document} (ID: {document_id})",
        )
    finally:
        parser.cleanup()

@shared_task
def empty_trash(doc_ids=None):
    if doc_ids is None:
        logger.info("Emptying trash of all expired documents")
    documents = (
        Document.deleted_objects.filter(id__in=doc_ids)
        if doc_ids is not None
        else Document.deleted_objects.filter(
            deleted_at__lt=timezone.localtime(timezone.now())
            - timedelta(
                days=settings.EMPTY_TRASH_DELAY,
            ),
        )
    )

    try:
        # deleted_document_ids = documents.values_list("id", flat=True)
        deleted_documents = documents.values('id', 'folder_id', 'dossier_id')
        deleted_document_ids = [doc['id'] for doc in deleted_documents]
        deleted_folder_ids = [doc['folder_id'] for doc in deleted_documents]
        deleted_dossier_ids = [doc['dossier_id'] for doc in deleted_documents]
        # print('deleted folder',deleted_folder_ids)
        # print('deleted dossier',deleted_dossier_ids)
        # Temporarily connect the cleanup handler
        models.signals.post_delete.connect(cleanup_document_deletion, sender=Document)
        documents.delete()  # this is effectively a hard delete
        # delete Folder
        folders = Folder.deleted_objects.filter(id__in=deleted_folder_ids)

        folders.delete()

        # delete Dossier
        dossiers = Dossier.deleted_objects.filter(id__in=deleted_dossier_ids)

        dossiers.delete()

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


def remove_folder_dossier_related(list_checksum):
    docs = Document.objects.filter(checksum__in=list_checksum)
    # docs = Document.objects.filter(id__in=doc_ids)
    for doc in docs:
        doc_folder = doc.folder
        # doc.folder = None
        doc_dossier = doc.dossier
        # doc.dossier = None
        # doc.save()
        if doc_folder is not None:
            doc_folder.hard_delete()
        if doc_dossier is not None:
            doc_dossier.hard_delete()
    docs.hard_delete()
    from documents import index

    with index.open_index_writer() as writer:
        for doc in docs:
            index.remove_document_by_id(writer, doc.id)


def restore_model(file_path, cls, compare_field):
    obj_set = set(cls.objects.all().values_list(compare_field, flat=True))
    with open(file_path, 'r') as backup_obj:
        # update document exist and add document
        objs_update = []
        objs_create = []
        objs_checksum = []
        for obj in deserialize('json', backup_obj.read()):
            if 'pk' in obj.object.__dict__:
                obj.id = obj.object.__dict__['pk']
            if getattr(obj.object, compare_field, None) in obj_set:
                objs_update.append(obj.object)
                if cls == Document:
                    objs_checksum.append(
                        getattr(obj.object, compare_field, None))
                    objs_create.append(obj.object)
                obj_set.discard(getattr(obj.object, compare_field))
                continue
            objs_create.append(obj.object)

        # cls.objects.bulk_update(objs=objs_update,
        #                         fields = [field.name for field in cls._meta.fields if field.name != 'id'],  batch_size=1000)
        if cls == Document:
            remove_folder_dossier_related(objs_checksum)
        cls.objects.bulk_create(objs=objs_create, batch_size=1000)


@shared_task()
def restore_documents(backup_record: BackupRecord):
    """
    copy source -> temp -> copy source to -> destination_directory
    """
    backup_root_dir = os.path.join(settings.BACKUP_DIR, backup_record.filename)
    temp_backup_dir = os.path.join(backup_root_dir, 'temp_backup')
    try:
        with transaction.atomic():
            file_document_backup = os.path.join(backup_root_dir,
                                                f'documents_backup.json')
            file_folder_backup = os.path.join(backup_root_dir,
                                              f'folders_backup.json')
            file_dossier_backup = os.path.join(backup_root_dir,
                                               f'dossiers_backup.json')
            restore_model(file_path=file_document_backup, cls=Document,
                          compare_field='checksum')
            restore_model(file_path=file_folder_backup, cls=Folder,
                          compare_field="checksum")
            restore_model(file_path=file_dossier_backup, cls=Dossier,
                          compare_field="id")
            # document_ids_set = set(Document.objects.values_list('id', flat=True))
            # with open(file_document_backup, 'r') as backup_document:
            #     # update document exist and add document
            #     documents_update=[]
            #     documents_create=[]
            #     for obj in deserialize('json', backup_document.read()):
            #         if getattr(obj,'id') in document_ids_set:
            #             documents_update.append(obj)
            #             document_ids_set.discard(getattr(obj,'id'))
            #             continue
            #         documents_create.append(obj)
            #
            #
            #     Document.objects.bulk_update(objs=documents_update,batch_size=1000)
            #     Document.objects.bulk_create(objs=documents_create,batch_size=1000)
            # file_folder_backup = os.path.join(backup_root_dir, f'folders_backup.json')
            # # Create a folder containing backup documents
            # folder_ids_set = set(
            #     Document.objects.values_list('id', flat=True))
            # # if folder_backup is None:
            # #     folder_backup = Folder.create_folder(name='backup')
            # with open(file_folder_backup, 'r') as backup_file:
            #     folders_update = []
            #     folders_create = []
            #     for obj in deserialize('json', backup_file.read()):
            #         if getattr(obj,'id') in folder_ids_set:
            #             folders_update.append(obj)
            #             folder_ids_set.discard(getattr(obj,'id'))
            #             continue
            #         folders_create.append(obj)
            #     Document.objects.bulk_update(objs=folders_update,
            #                                  batch_size=1000)
            #     Document.objects.bulk_create(objs=folders_create,
            #                                  batch_size=1000)

            os.makedirs(temp_backup_dir, exist_ok=True)
            if os.path.exists(temp_backup_dir):
                shutil.copytree(settings.MEDIA_ROOT / "documents",
                                temp_backup_dir, dirs_exist_ok=True)
            if os.path.exists(backup_root_dir):
                shutil.copytree(backup_root_dir,
                                settings.MEDIA_ROOT / "documents",
                                dirs_exist_ok=True)
            backup_record.log = _("Restore successful")
    except Exception as e:
        backup_record.log = e
        logger.debug(e)
        # retore
        if os.path.exists(temp_backup_dir):
            shutil.copytree(temp_backup_dir, settings.MEDIA_ROOT / "documents")
    finally:
        # shutil.rmtree(temp_backup_dir)
        backup_record.count = backup_record.count + 1
        backup_record.save()


@shared_task()
def backup_documents():
    # Lưu thông tin vào BackupRecord
    backup_dir = settings.BACKUP_DIR
    os.makedirs(backup_dir, exist_ok=True)

    # Sao lưu các bản ghi Document
    documents = Document.objects.all()
    folders = Folder.objects.all()
    dossiers = Dossier.objects.all()
    detail = {'documents': documents.count()}

    from datetime import datetime
    current_date = datetime.now().strftime('%Y_%m_%d')

    # Tạo thư mục sao lưu theo ngày tháng năm
    backups_name = BackupRecord.objects.filter(
        filename__startswith=current_date).order_by('filename').values_list(
        'filename', flat=True)
    name = current_date
    if backups_name.count() > 0:
        name = generate_unique_name(current_date, backups_name)
    backup_root_dir = os.path.join(settings.BACKUP_DIR, name)
    backup = BackupRecord.objects.create(filename=name, detail=detail)
    backup_document_file_path = os.path.join(backup_root_dir,
                                             f'documents_backup.json')
    backup_folder_file_path = os.path.join(backup_root_dir,
                                           f'folders_backup.json')
    backup_dossier_path = os.path.join(backup_root_dir,
                                       f'dossiers_backup.json')
    archive_dir = os.path.join(backup_root_dir, 'archive')
    originals_dir = os.path.join(backup_root_dir, 'originals')
    thumbnails_dir = os.path.join(backup_root_dir, 'thumbnails')
    try:
        os.makedirs(archive_dir, exist_ok=True)
        os.makedirs(originals_dir, exist_ok=True)
        os.makedirs(thumbnails_dir, exist_ok=True)

        if os.path.exists(settings.ORIGINALS_DIR):
            shutil.copytree(settings.ORIGINALS_DIR, originals_dir,
                            dirs_exist_ok=True)
        if os.path.exists(settings.ORIGINALS_DIR):
            shutil.copytree(settings.ARCHIVE_DIR, archive_dir,
                            dirs_exist_ok=True)
        if os.path.exists(settings.THUMBNAIL_DIR):
            shutil.copytree(settings.THUMBNAIL_DIR, thumbnails_dir,
                            dirs_exist_ok=True)

        # Xuất dữ liệu thành JSON
        with open(backup_document_file_path, 'w') as backup_document_file:
            backup_document_file.write(serialize('json', documents))
        with open(backup_folder_file_path, 'w') as backup_folder_file:
            backup_folder_file.write(serialize('json', folders))
        with open(backup_dossier_path, 'w') as backup_dossier_file:
            backup_dossier_file.write(serialize('json', dossiers))

        backup.log = _('Backup successful')


    except Exception as e:
        shutil.rmtree(backup_root_dir)
        backup.log = e
    finally:
        backup.save()
