from dataclasses import field

from django_elasticsearch_dsl import Document, fields
from django_elasticsearch_dsl.registries import registry
from .models import Document as DocumentModel

@registry.register_document
class DocumentDocument(Document):
    # correspondent = fields.ObjectField(properties={
    #     'id': fields.IntegerField(),
    #     'name': fields.TextField(),  # Giả sử bạn có trường name trong Correspondent
    # })
    #
    # storage_path = fields.ObjectField(properties={
    #     'id': fields.IntegerField(),
    #     'path': fields.TextField(),  # Giả sử bạn có trường path trong StoragePath
    # })
    #
    # folder = fields.ObjectField(properties={
    #     'id': fields.IntegerField(),
    #     'name': fields.TextField(),  # Giả sử bạn có trường name trong Folder
    # })
    #
    # dossier = fields.ObjectField(properties={
    #     'id': fields.IntegerField(),
    #     'name': fields.TextField(),  # Giả sử bạn có trường name trong Dossier
    # })
    #
    # document_type = fields.ObjectField(properties={
    #     'id': fields.IntegerField(),
    #     'name': fields.TextField(),  # Giả sử bạn có trường name trong DocumentType
    # })
    # id = fields.IntegerField()
    # title = fields.TextField()
    # content = fields.TextField()
    # correspondent_id = fields.IntegerField()
    pk = fields.IntegerField(attr='id')
    folder = fields.IntegerField(attr='folder_id')
    dossier = fields.IntegerField(attr='dossier_id')
    # dossier_form = fields.IntegerField()
    warehouse = fields.IntegerField(attr='warehouse_id')
    document_type = fields.IntegerField(attr='document_type_id')
    owner = fields.IntegerField(attr='owner_id')

    class Index:
        name = 'document_index'  # Tên chỉ mục trong Elasticsearch

    class Django:
        model = DocumentModel  # Mô hình Django
        fields = [
            'id',
            'title',
            'content',
            # Không cần thêm các trường khóa ngoại ở đây vì đã định nghĩa ở trên
        ]
