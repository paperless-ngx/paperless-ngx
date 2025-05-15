import logging
import re

from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from elasticsearch.helpers import bulk
from guardian.shortcuts import get_users_with_perms

from edoc.settings import ELASTIC_SEARCH_DOCUMENT_INDEX
from .models import Document as DocumentModel, Note, CustomFieldInstance
from .permissions import get_groups_with_only_permission

logger = logging.getLogger("edoc.document_elasticsearch")
@registry.register_document
class DocumentDocument(Document):
    id = fields.IntegerField(attr='id')
    title = fields.TextField(attr='title')
    title_keyword = fields.KeywordField(attr='title')
    suggest = fields.CompletionField()
    content = fields.TextField(
        analyzer="standard"  # Sử dụng analyzer cho tiếng Việt
    )
    suggest_content = fields.CompletionField()
    asn = fields.KeywordField(attr='archive_serial_number')
    correspondent = fields.TextField(attr='correspondent.name')
    correspondent_id = fields.IntegerField(attr='correspondent.id')
    has_correspondent = fields.BooleanField(attr='correspondent is not None')
    tags = fields.ListField(fields.TextField())
    tag_id = fields.ListField(fields.IntegerField())
    has_tag = fields.BooleanField(attr='len(tags) > 0')
    type = fields.KeywordField(attr='document_type.name')
    type_id = fields.IntegerField(attr='document_type.id')
    has_type = fields.BooleanField(attr='document_type is not None')
    warehouse = fields.KeywordField(attr='warehouse.name')
    warehouse_path = fields.KeywordField(attr='warehouse.path')
    warehouse_id = fields.IntegerField(attr='warehouse.id')
    has_warehouse = fields.BooleanField(attr='warehouse is not None')
    archive_font = fields.TextField(attr='archive_font.name')
    archive_font_id = fields.IntegerField(attr='archive_font.id')
    has_archive_font = fields.BooleanField(attr='archive_font is not None')
    folder = fields.TextField(attr='folder.name')
    folder_id = fields.IntegerField(attr='folder.id')
    has_folder = fields.BooleanField(attr='folder is not None')
    folder_path = fields.BooleanField(attr='folder.path')
    created = fields.DateField(attr='created')
    added = fields.DateField(attr='added')
    modified = fields.DateField(attr='modified')
    path = fields.TextField(attr='storage_path.name')
    path_id = fields.IntegerField(attr='storage_path.id')
    has_path = fields.BooleanField(attr='storage_path is not None')
    notes = fields.ListField(fields.TextField())  # Thay đổi kiểu dữ liệu
    num_notes = fields.IntegerField(attr='num_notes')
    custom_fields = fields.ListField(fields.TextField())  # Thay đổi kiểu dữ liệu
    # custom_field_count = fields.IntegerField(attr='custom_field_count')
    owner = fields.KeywordField(attr='owner.username')
    owner_id = fields.IntegerField(attr='owner.id')
    has_owner = fields.BooleanField(attr='owner is not None')
    viewer_id = fields.ListField(fields.IntegerField())
    checksum = fields.TextField(attr='checksum')
    page_count = fields.IntegerField(attr='page_count')
    original_filename = fields.TextField(attr='original_filename')
    is_shared = fields.BooleanField(attr='len(viewer_id) > 0')
    # shared_by = fields.ListField(fields.IntegerField())
    view_users = fields.ListField(fields.IntegerField())
    view_groups = fields.ListField(fields.IntegerField())
    change_users = fields.ListField(fields.IntegerField())
    change_groups = fields.ListField(fields.IntegerField())


    class Index:
        name = ELASTIC_SEARCH_DOCUMENT_INDEX
        settings = {
            'number_of_shards': 3,  # Phân đoạn cho dữ liệu lớn
            'number_of_replicas': 1,

        }

    class Django:
        model = DocumentModel
        fields = []
    @staticmethod
    def prepare_suggest_content( instance):
        # Trích xuất các cụm từ từ content để dùng cho gợi ý

        content = instance.content
        if not content or not isinstance(content, str):
            return []

        # Chuẩn hóa và tách từ
        # normalized_text = text_normalize(content.lower())
        # tokens = word_tokenize(normalized_text)
        tokens = re.split(r'[\n\t\r\b\s]+|[^\w]+', instance.content.lower())

        # Tạo danh sách cụm từ (bigram và trigram) với trọng số
        phrases = []
        weights = {}
        for i in range(len(tokens) - 1):
            phrase2 = ' '.join(tokens[i:i + 2])  # Bigram
            phrases.append(phrase2)
            weights[phrase2] = weights.get(phrase2,
                                           0) + 1  # Tăng trọng số nếu lặp lại

            if i < len(tokens) - 2:
                phrase3 = ' '.join(tokens[i:i + 3])  # Trigram
                phrases.append(phrase3)
                weights[phrase3] = weights.get(phrase3, 0) + 1

        # Loại bỏ trùng lặp và sắp xếp theo trọng số
        unique_phrases = list(set(phrases))
        return [{"input": phrase, "weight": weights[phrase]} for phrase in
                unique_phrases if weights[phrase] > 1]

    def prepare_tags(self, instance):
        return [tag.name for tag in instance.tags.all()]

    def prepare_custom_fields(self, instance):
        return [str(c) for c in CustomFieldInstance.objects.filter(document=instance)]

    def prepare_tag_id(self, instance):
        return [tag.id for tag in instance.tags.all()]

    def prepare_suggest(self, instance):
        return {
            "input": re.split(r'[\n\t\r\b\s]+|[^\w]+', instance.content.lower())
        }

    def prepare_notes(self, instance):
        return [str(c.note) for c in Note.objects.filter(document=instance)]

    def prepare_view_users(self, instance):
        return DocumentDocument.get_view_users(instance)

    def prepare_view_groups(self, instance):
        return DocumentDocument.get_view_groups(instance)

    @staticmethod
    def get_view_users(instance):
        """Truy vấn riêng để lấy danh sách user có quyền view."""
        view_codename = f"view_{instance.__class__.__name__.lower()}"
        return list(
            get_users_with_perms(
                instance, only_with_perms_in=[view_codename],
                with_group_users=False
            ).values_list("id", flat=True)
        )

    @staticmethod
    def get_view_groups(instance):
        """Truy vấn riêng để lấy danh sách group có quyền view."""
        view_codename = f"view_{instance.__class__.__name__.lower()}"
        return list(
            get_groups_with_only_permission(
                instance, codename=view_codename
            ).values_list("id", flat=True)
        )

    @staticmethod
    def get_permissions(instance):
        """Kết hợp kết quả hai truy vấn vào một dictionary."""
        return {
            "view": {
                "users": DocumentDocument.get_view_users(instance),
                "groups": DocumentDocument.get_view_groups(instance)
            }
        }

    #
    #
    # @staticmethod
    #     def get_permissions(instance):
    #         view_codename = f"view_{instance.__class__.__name__.lower()}"
    #         change_codename = f"change_{instance.__class__.__name__.lower()}"
    #
    #         return {
    #             "view": {
    #                 "users": list(get_users_with_perms(instance,
    #                                                    only_with_perms_in=[
    #                                                        view_codename],
    #                                                    with_group_users=False
    #                                                    ).values_list("id",
    #                                                                  flat=True)),
    #                 "groups": list(get_groups_with_only_permission(instance,
    #                                                                codename=view_codename).values_list(
    #                     "id", flat=True)),
    #             },
    #             # "change": {
    #             #     "users": list(get_users_with_perms(instance,only_with_perms_in=[change_codename],
    #             #         with_group_users=False
    #             #     ).values_list("id", flat=True)),
    #             #     "groups": list(get_groups_with_only_permission(instance,codename=change_codename).values_list(
    #             #         "id", flat=True)),
    #             # },
    #         }

    @classmethod
    def update_document(cls, doc):
        document_data = {}
        # users_with_perms = get_users_with_perms(doc, only_with_perms_in=["view_document"])
        tags = [t.name for t in doc.tags.all()]
        tags_ids = [t.id for t in doc.tags.all()]
        notes = list(Note.objects.filter(document=doc).values_list('note', flat=True))
        custom_fields = ",".join([str(c) for c in CustomFieldInstance.objects.filter(document=doc)],)
        permissions = cls().get_permissions(doc)
        viewer_ids = [u for u in permissions['view']['users']]

        # document_data['id'] = doc.id or None
        document_data['title'] = doc.title or ''
        document_data['content'] = doc.content or ''
        document_data['suggest_content'] = cls().prepare_suggest_content(instance=doc)
        document_data['asn'] = doc.archive_serial_number or -1
        document_data['correspondent'] = doc.correspondent.name if doc.correspondent else ''
        document_data['correspondent_id'] = doc.correspondent.id if doc.correspondent else -1
        document_data['has_correspondent'] = bool(doc.correspondent) is not False
        document_data['tags'] = tags or ['']
        document_data['tag_id'] = tags_ids or [-1]
        document_data['has_tag'] = bool(tags)
        document_data['type'] = doc.document_type.name if doc.document_type else ''
        document_data['type_keyword'] = doc.document_type.name if doc.document_type else ''
        document_data['type_id'] = doc.document_type.id if doc.document_type else -1
        document_data['has_type'] = bool(doc.document_type) is not False
        document_data['warehouse'] = doc.warehouse.name if doc.warehouse else ''
        document_data['warehouse_path'] = doc.warehouse.path if doc.warehouse else ''
        document_data['warehouse_id'] = doc.warehouse.id if doc.warehouse else -1
        document_data['has_warehouse'] = bool(doc.warehouse) is not False
        document_data['archive_font'] = doc.archive_font.name if doc.archive_font else ''
        document_data['archive_font_id'] = doc.archive_font.id if doc.archive_font else -1
        document_data['has_archive_font'] = bool(doc.archive_font) is not False
        document_data['folder'] = doc.folder.name if doc.folder else ''
        document_data['folder_path'] = doc.folder.path if doc.folder else ''
        document_data['folder_id'] = doc.folder.id if doc.folder else -1
        document_data['has_folder'] = bool(doc.folder) is not None or False
        document_data['created'] = doc.created or None
        document_data['added'] = doc.added or None
        document_data['modified'] = doc.modified or None
        document_data['path'] = doc.storage_path.name if doc.storage_path else ''
        document_data['path_id'] = doc.storage_path.id if doc.storage_path else -1
        document_data['has_path'] = bool(doc.storage_path) is not None or False
        document_data['notes'] = notes or ['']  # Đảm bảo là danh sách
        document_data['num_notes'] = len(notes) or 0
        document_data['custom_fields'] = custom_fields or ['']  # Đảm bảo là danh sách
        document_data['custom_field_count'] = len(custom_fields) or 0
        document_data['owner'] = doc.owner.username if doc.owner else ''
        document_data['owner_id'] = doc.owner.id if doc.owner else -1
        document_data['has_owner'] = bool(doc.owner) is not None or False
        document_data['viewer_id'] = viewer_ids or [-1]  # Đảm bảo là danh sách
        document_data['checksum'] = doc.checksum or ''
        document_data['page_count'] = doc.page_count or 0
        document_data['original_filename'] = doc.original_filename or ''
        document_data['is_shared'] = bool(viewer_ids)
        document_data['view_users'] = permissions['view']['users'] or [-1]
        document_data['view_groups'] = permissions['view']['groups'] or [-1]
        # document_data['change_users'] = permissions['change']['users'] or [-1]
        # document_data['change_groups'] = permissions['change']['groups'] or [-1]
        document_instance = cls(**document_data,_id=str(doc.id))
        logger.info(
            f"Đang cập nhật tài liệu {doc.id} {document_data} vào Elasticsearch.")
        document_instance.save()  # Gọi save trên instance


    # @classmethod
    # def rebuild(cls):
    #     # Tái lập chỉ mục cho tất cả các tài liệu
    #     for doc in DocumentModel.objects.all():
    #         cls.update_document(doc)

    @classmethod
    def bulk_index_documents(cls, documents, batch_size=10000):
        """
        Chỉ mục các tài liệu vào Elasticsearch bằng phương pháp bulk indexing với batching.
        :param documents: QuerySet hoặc danh sách các tài liệu cần chỉ mục.
        :param batch_size: Kích thước lô (batch size) cho mỗi lần xử lý.
        """
        total_documents = len(documents)
        # logger.info(
        #     f"Tổng số tài liệu cần xử lý: {total_documents}. Batch size: {batch_size}.")

        # Process documents in batches
        for i in range(0, total_documents, batch_size):
            # Create a batch of documents
            batch = documents[i:i + batch_size]
            # logger.info(
            #     f"Đang xử lý batch {i // batch_size + 1} với {len(batch)} tài liệu.")

            actions = []
            for doc in batch:
                try:

                    parsed_document = DocumentDocument.prepare_document_data(doc)
                    actions.append({
                        "_index": cls.Index.name,
                        "_id": str(doc.id),
                        "_source": parsed_document,
                    })
                    # logger.info(
                    #     f"Tài liệu {doc.id} đã được chuẩn bị để chỉ mục trong batch {i // batch_size + 1}.")
                except Exception as e:
                    raise e
                    logger.error(f"Lỗi khi xử lý tài liệu {doc.id}: {e}")

            # Skip processing if the batch has no valid actions
            if not actions:
                logger.warning(
                    f"Batch {i // batch_size + 1}: Không có tài liệu hợp lệ để chỉ mục.")
                continue

            try:
                # Perform bulk indexing for the current batch
                client = cls._get_connection()
                bulk(client, actions)
                logger.info(
                    f"Batch {i // batch_size + 1}: Đã chỉ mục thành công {len(actions)} tài liệu.")
            except Exception as e:
                logger.error(
                    f"Batch {i // batch_size + 1}: Lỗi khi thực hiện chỉ mục theo lô: {e}")
    @staticmethod
    def prepare_document_data(instance):
        """
        Prepares the document data for Elasticsearch indexing.
        :param instance: A document instance from the `DocumentModel`.
        :return: Dictionary containing the document data.
        """
        try:

            # users_with_perms = get_users_with_perms(instance, only_with_perms_in=[
            #     "view_document"])
            # Basic fields
            document_data = {"id": instance.id, "title": instance.title or '',
                             "content": instance.content or '',
                             "asn": instance.archive_serial_number or -1,
                             "created": instance.created,
                             "added": instance.added,
                             "modified": instance.modified,
                             "checksum": instance.checksum or '',
                             "page_count": instance.page_count or 0,
                             "original_filename": instance.original_filename or '',
                             "suggest_content": DocumentDocument.prepare_suggest_content(
                                 instance), "tags": [''], "tag_id": [-1],
                             "has_tag": bool(
                                 instance.tags.all()) if instance.tags else False}

            # Suggest content (bigram and trigram logic)

            permissions = DocumentDocument.get_permissions(instance)
            viewer_ids = [u for u in permissions['view']['users']]
            document_data["view_users"] = permissions['view']['users'] or [-1]
            document_data["view_groups"] = permissions['view']['groups'] or [
                -1]
            # document_data["change_users"] = permissions['change']['users'] or [-1]
            # document_data["change_groups"] = permissions['change']['groups'] or [-1]
            document_data["viewer_id"] = viewer_ids or [-1]
            document_data["is_shared"] = bool(viewer_ids)
            # Tags

            for tag in instance.tags.all():
                document_data["tags"].append(tag.name)
                document_data["tag_id"].append(tag.id)


            # Correspondent information
            document_data["has_correspondent"] = bool(instance.correspondent) is not False
            if instance.correspondent:
                document_data["correspondent"] = instance.correspondent.name
                document_data["correspondent_id"] = instance.correspondent.id
            else:
                document_data["correspondent"] = ''
                document_data["correspondent_id"] = -1


            # Warehouse details
            if instance.warehouse:
                document_data["warehouse"] = instance.warehouse.name
                document_data["warehouse_path"] = instance.warehouse.path
                document_data["warehouse_id"] = instance.warehouse.id
                document_data["has_warehouse"] = True
            else:
                document_data["warehouse"] = ''
                document_data["warehouse_path"] = ''
                document_data["warehouse_id"] = -1
                document_data["has_warehouse"] = False

            # document_type details
            if instance.document_type:
                document_data["type"] = instance.document_type.name
                document_data["type_id"] = instance.document_type.id
                document_data["has_type"] = True
            else:
                document_data["type"] = ''
                document_data["type_id"] = -1
                document_data["has_type"] = False

            # Folder details
            if instance.folder:
                document_data["folder"] = instance.folder.name
                document_data["folder_id"] = instance.folder.id
                document_data["folder_path"] = instance.folder.path
                document_data["has_folder"] = True
            else:
                document_data["folder"] = ''
                document_data["folder_id"] = -1
                document_data["folder_path"] = ''
                document_data["has_folder"] = False

            # Archive font details
            if instance.archive_font:
                document_data["archive_font"] = instance.archive_font.name
                document_data["archive_font_id"] = instance.archive_font.id
                document_data["has_archive_font"] = True
            else:
                document_data["archive_font"] = ''
                document_data["archive_font_id"] = -1
                document_data["has_archive_font"] = False

            # Notes and custom fields
            # document_data["notes"] = list(
            #     Note.objects.filter(document=instance).values_list('note',
            #                                                        flat=True))
            document_data["notes"] = ['']
            for note in instance.notes.all():
                document_data["notes"].append(note.note)

            document_data["custom_fields"] = ['']
            document_data["has_custom_fields"] = bool(
                instance.custom_fields.all()) if instance.custom_fields else False
            for custom_field in instance.custom_fields.all():
                document_data["custom_fields"].append(str(custom_field))


            document_data["tags"] = ['']
            document_data["tag_id"] = [-1]
            document_data["has_tag_id"] = bool(
                instance.tags.all()) if instance.tags else False
            for tag in instance.tags.all():
                document_data["tags"].append(tag.name)
                document_data["tag_id"].append(tag.id)

            document_data["num_notes"] = len(document_data["notes"])
            document_data["custom_field_count"] = len(
                document_data["custom_fields"])

            # document_data["viewer_id"] = [1]
            # document_data["is_shared"] = False

            # Owner details
            if instance.owner:
                document_data["owner"] = instance.owner.username
                document_data["owner_id"] = instance.owner.id
                document_data["has_owner"] = True
            else:
                document_data["owner"] = ''
                document_data["owner_id"] = -1
                document_data["has_owner"] = False

            # document_data["viewer_id"] = viewer_ids or [-1]

            return document_data

        except Exception as e:
            logger.error(
                f"Error preparing document data for instance {instance.id}: {e}")
            raise e
            return None  # Or raise the exception if necessary
