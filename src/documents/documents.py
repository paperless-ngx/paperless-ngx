from dataclasses import field

from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from .models import Document as DocumentModel

@registry.register_document
class DocumentDocument(Document):
    title = fields.TextField(attr='title')
    title_keyword = fields.KeywordField(attr='title')
    content = fields.TextField(attr='content')
    asn = fields.KeywordField(attr='archive_serial_number')
    correspondent = fields.TextField(attr='correspondent.name')
    correspondent_id = fields.IntegerField(attr='correspondent.id')
    has_correspondent = fields.BooleanField(attr='correspondent is not None')
    tags = fields.ListField(fields.ObjectField(properties={
        'id': fields.IntegerField(attr='id'),
        'name': fields.TextField(attr='name'),
    }))
    has_tag = fields.BooleanField(attr='len(tags) > 0')
    type = fields.TextField(attr='document_type.name')
    type_keyword = fields.KeywordField(attr='document_type.name')
    type_id = fields.IntegerField(attr='document_type.id')
    has_type = fields.BooleanField(attr='document_type is not None')
    warehouse_name = fields.TextField(attr='warehouse.name')
    warehouse = fields.KeywordField(attr='warehouse.name')
    warehouse_path = fields.KeywordField(attr='warehouse.path')
    warehouse_id = fields.IntegerField(attr='warehouse.id')
    has_warehouse = fields.BooleanField(attr='warehouse is not None')
    archive_font_name = fields.TextField(attr='archive_font.name')
    archive_font_id = fields.IntegerField(attr='archive_font.id')
    has_archive_font = fields.BooleanField(attr='archive_font is not None')
    folder_name = fields.TextField(attr='folder.name')
    folder_id = fields.IntegerField(attr='folder.id')
    has_folder = fields.BooleanField(attr='folder is not None')
    created = fields.DateField(attr='created')
    added = fields.DateField(attr='added')
    modified = fields.DateField(attr='modified')
    path = fields.TextField(attr='storage_path.name')
    path_id = fields.IntegerField(attr='storage_path.id')
    has_path = fields.BooleanField(attr='storage_path is not None')
    notes = fields.ListField(fields.ObjectField(
        properties={
            'content': fields.TextField(attr='note'),  # Nội dung note
        }
    ))
    num_notes = fields.IntegerField(attr='len(notes)')
    custom_fields = fields.ObjectField(attr='custom_fields')
    custom_field_count = fields.IntegerField(attr='len(custom_fields.all())')
    owner_username = fields.TextField(attr='owner.username')
    owner_keyword = fields.KeywordField(attr='owner.username')
    owner_id = fields.IntegerField(attr='owner.id')
    has_owner = fields.BooleanField(attr='owner is not None')
    viewer_id = fields.ObjectField(attr='viewer_ids')
    checksum = fields.TextField(attr='checksum')
    page_count = fields.IntegerField(attr='page_count')
    original_filename = fields.TextField(attr='original_filename')
    is_shared = fields.BooleanField(attr='len(viewer_ids) > 0')

    class Index:
        name = 'document_index'  # Tên chỉ mục trong Elasticsearch

    class Django:
        model = DocumentModel  # Mô hình Django
        fields = [

        ]
