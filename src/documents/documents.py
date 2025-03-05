import re
from dataclasses import field

from django.contrib.sitemaps.views import index
from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from guardian.shortcuts import get_users_with_perms

from paperless.settings import ELASTIC_SEARCH_DOCUMENT_INDEX
from .models import Document as DocumentModel, Note, CustomFieldInstance


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
    type_keyword = fields.KeywordField(attr='document_type.name')
    type_id = fields.IntegerField(attr='document_type.id')
    has_type = fields.BooleanField(attr='document_type is not None')
    warehouse = fields.TextField(attr='warehouse.name')
    warehouse_keyword = fields.KeywordField(attr='warehouse.name')
    warehouse_path = fields.KeywordField(attr='warehouse.path')
    warehouse_id = fields.IntegerField(attr='warehouse.id')
    has_warehouse = fields.BooleanField(attr='warehouse is not None')
    archive_font = fields.TextField(attr='archive_font.name')
    archive_font_id = fields.IntegerField(attr='archive_font.id')
    has_archive_font = fields.BooleanField(attr='archive_font is not None')
    folder = fields.TextField(attr='folder.name')
    folder_id = fields.IntegerField(attr='folder.id')
    has_folder = fields.BooleanField(attr='folder is not None')
    created = fields.DateField(attr='created')
    added = fields.DateField(attr='added')
    modified = fields.DateField(attr='modified')
    path = fields.TextField(attr='storage_path.name')
    path_id = fields.IntegerField(attr='storage_path.id')
    has_path = fields.BooleanField(attr='storage_path is not None')
    notes = fields.ListField(fields.TextField())  # Thay đổi kiểu dữ liệu
    num_notes = fields.IntegerField(attr='num_notes')
    custom_fields = fields.TextField()  # Thay đổi kiểu dữ liệu
    # custom_field_count = fields.IntegerField(attr='custom_field_count')
    owner = fields.KeywordField(attr='owner.username')
    owner_id = fields.IntegerField(attr='owner.id')
    has_owner = fields.BooleanField(attr='owner is not None')
    viewer_id = fields.ListField(fields.IntegerField())
    checksum = fields.TextField(attr='checksum')
    page_count = fields.IntegerField(attr='page_count')
    original_filename = fields.TextField(attr='original_filename')
    is_shared = fields.BooleanField(attr='len(viewer_id) > 0')

    class Index:
        name = ELASTIC_SEARCH_DOCUMENT_INDEX
        settings = {
            'number_of_shards': 5,  # Phân đoạn cho dữ liệu lớn
            'number_of_replicas': 2,

        }

    class Django:
        model = DocumentModel
        fields = []

    def prepare_suggest_content(self, instance):
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
    @classmethod
    def update_document(cls, doc):
        document_data = {}
        users_with_perms = get_users_with_perms(doc, only_with_perms_in=["view_document"])
        tags = [t.name for t in doc.tags.all()]
        tags_ids = [t.id for t in doc.tags.all()]
        notes = list(Note.objects.filter(document=doc).values_list('note', flat=True))
        custom_fields = ",".join([str(c) for c in CustomFieldInstance.objects.filter(document=doc)],)

        viewer_ids = [u.id for u in users_with_perms]

        # document_data['id'] = doc.id or None
        document_data['title'] = doc.title or None
        document_data['content'] = doc.content or None
        document_data['suggest_content'] = cls().prepare_suggest_content(instance=doc)
        document_data['asn'] = doc.archive_serial_number or None
        document_data['correspondent'] = doc.correspondent.name if doc.correspondent else None
        document_data['correspondent_id'] = doc.correspondent.id if doc.correspondent else None
        document_data['has_correspondent'] = doc.correspondent is not None
        document_data['tags'] = tags or None
        document_data['tag_id'] = tags_ids or None
        document_data['has_tag'] = bool(tags)
        document_data['type'] = doc.document_type.name if doc.document_type else None
        document_data['type_id'] = doc.document_type.id if doc.document_type else None
        document_data['has_type'] = doc.document_type is not None
        document_data['warehouse'] = doc.warehouse.name if doc.warehouse else None
        document_data['warehouse_path'] = doc.warehouse.path if doc.warehouse else None
        document_data['warehouse_id'] = doc.warehouse.id if doc.warehouse else None
        document_data['has_warehouse'] = doc.warehouse is not None
        document_data['archive_font'] = doc.archive_font.name if doc.archive_font else None
        document_data['archive_font_id'] = doc.archive_font.id if doc.archive_font else None
        document_data['has_archive_font'] = doc.archive_font is not None
        document_data['folder'] = doc.folder.name if doc.folder else None
        document_data['folder_id'] = doc.folder.id if doc.folder else None
        document_data['has_folder'] = doc.folder is not None
        document_data['created'] = doc.created
        document_data['added'] = doc.added
        document_data['modified'] = doc.modified
        document_data['path'] = doc.storage_path.name if doc.storage_path else None
        document_data['path_id'] = doc.storage_path.id if doc.storage_path else None
        document_data['has_path'] = doc.storage_path is not None
        document_data['notes'] = notes or None  # Đảm bảo là danh sách
        document_data['num_notes'] = len(notes)
        document_data['custom_fields'] = custom_fields or None  # Đảm bảo là danh sách
        document_data['custom_field_count'] = len(custom_fields)
        document_data['owner'] = doc.owner.username if doc.owner else None
        document_data['owner_id'] = doc.owner.id if doc.owner else None
        document_data['has_owner'] = doc.owner is not None
        document_data['viewer_id'] = viewer_ids or None  # Đảm bảo là danh sách
        document_data['checksum'] = doc.checksum
        document_data['page_count'] = doc.page_count
        document_data['original_filename'] = doc.original_filename
        document_data['is_shared'] = bool(viewer_ids)
        document_instance = cls(**document_data,_id=str(doc.id))
        document_instance.save()  # Gọi save trên instance


    # @classmethod
    # def rebuild(cls):
    #     # Tái lập chỉ mục cho tất cả các tài liệu
    #     for doc in DocumentModel.objects.all():
    #         cls.update_document(doc)
