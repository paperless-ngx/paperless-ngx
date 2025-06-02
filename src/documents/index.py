import logging
import math
import os
import re
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from shutil import rmtree
from typing import Optional

from dateutil.parser import isoparse
from django.conf import settings
from django.db.models.functions import Substr
from django.utils import timezone as django_timezone
from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q
from guardian.shortcuts import get_users_with_perms
from whoosh import classify
from whoosh import highlight
from whoosh import query
from whoosh.fields import BOOLEAN
from whoosh.fields import DATETIME
from whoosh.fields import KEYWORD
from whoosh.fields import NUMERIC
from whoosh.fields import Schema
from whoosh.fields import TEXT
from whoosh.highlight import HtmlFormatter
from whoosh.index import FileIndex
from whoosh.index import create_in
from whoosh.index import exists_in
from whoosh.index import open_dir
from whoosh.qparser import MultifieldParser
from whoosh.qparser import QueryParser
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.qparser.dateparse import English
from whoosh.qparser.plugins import FieldsPlugin
from whoosh.scoring import TF_IDF
from whoosh.searching import ResultsPage
from whoosh.searching import Searcher
from whoosh.util.times import timespan
from whoosh.writing import AsyncWriter

from documents.documents import DocumentDocument
from documents.models import CustomFieldInstance, Warehouse, Folder, Tag, \
    DocumentType
from documents.models import Document
from documents.models import Note
from documents.models import User
from edoc.settings import ELASTIC_SEARCH_DOCUMENT_INDEX, ELASTIC_SEARCH_HOST

logger = logging.getLogger("edoc.index")


def get_schema():
    return Schema(
        id=NUMERIC(stored=True, unique=True),
        title=TEXT(sortable=True),
        content=TEXT(),
        asn=NUMERIC(sortable=True, signed=False),
        correspondent=TEXT(sortable=True),
        correspondent_id=NUMERIC(),
        has_correspondent=BOOLEAN(),
        tag=KEYWORD(commas=True, scorable=True, lowercase=True),
        tag_id=KEYWORD(commas=True, scorable=True),
        has_tag=BOOLEAN(),
        type=TEXT(sortable=True),
        type_id=NUMERIC(),
        has_type=BOOLEAN(),
        warehouse=TEXT(sortable=True),
        warehouse_id=NUMERIC(),
        has_warehouse=BOOLEAN(),
        folder=TEXT(sortable=True),
        folder_id=NUMERIC(),
        has_folder=BOOLEAN(),
        created=DATETIME(sortable=True),
        modified=DATETIME(sortable=True),
        added=DATETIME(sortable=True),
        path=TEXT(sortable=True),
        path_id=NUMERIC(),
        has_path=BOOLEAN(),
        notes=TEXT(),
        num_notes=NUMERIC(sortable=True, signed=False),
        custom_fields=TEXT(),
        custom_field_count=NUMERIC(sortable=True, signed=False),
        owner=TEXT(),
        owner_id=NUMERIC(),
        has_owner=BOOLEAN(),
        viewer_id=KEYWORD(commas=True),
        checksum=TEXT(),
        page_count=NUMERIC(sortable=True),
        original_filename=TEXT(sortable=True),
        is_shared=BOOLEAN(),
    )


def open_index(recreate=False) -> FileIndex:
    try:
        if exists_in(settings.INDEX_DIR) and not recreate:
            return open_dir(settings.INDEX_DIR, schema=get_schema())
    except Exception:
        logger.exception("Error while opening the index, recreating.")

    # create_in doesn't handle corrupted indexes very well, remove the directory entirely first
    if os.path.isdir(settings.INDEX_DIR):
        rmtree(settings.INDEX_DIR)
    settings.INDEX_DIR.mkdir(parents=True, exist_ok=True)

    return create_in(settings.INDEX_DIR, get_schema())


@contextmanager
def open_index_writer(optimize=False) -> AsyncWriter:
    writer = AsyncWriter(open_index())

    try:
        yield writer
    except Exception as e:
        logger.exception(str(e))
        writer.cancel()
    finally:
        writer.commit(optimize=optimize)


@contextmanager
def open_index_searcher() -> Searcher:
    searcher = open_index().searcher()

    try:
        yield searcher
    finally:
        searcher.close()

def update_index_document(doc: Document):
    DocumentDocument().update_document(doc)

def update_index_bulk_documents(docs,batch_size):
    DocumentDocument().bulk_index_documents(docs,batch_size=batch_size)

def delete_document_index(doc: Document = None, id: int=None):
    if doc is not None:
        id = doc.id
    DocumentDocument().delete(id=str(id))


def delete_document_with_index(doc_id, es_client=None):
    """
    Delete a document from the Elasticsearch index by its ID using the Elasticsearch client.

    Args:
        doc_id (int): The ID of the document to delete.
        es_client (Elasticsearch, optional): Elasticsearch client instance.
    """
    try:
        logger.info('đã gọi hàm delete_document_with_index')
        # Initialize Elasticsearch client if not provided
        if es_client is None:
            es_client = Elasticsearch([ELASTIC_SEARCH_HOST],
                                      timeout=30)
        doc_exists = es_client.exists(index=ELASTIC_SEARCH_DOCUMENT_INDEX,
                                      id=doc_id)
        if not doc_exists:
            logger.warning(f"Tài liệu với ID {doc_id} không tồn tại.")
            return

        # Delete the document
        es_client.delete(index=ELASTIC_SEARCH_DOCUMENT_INDEX, id=doc_id)
        doc_exists_after_deletion = es_client.exists(
            index=ELASTIC_SEARCH_DOCUMENT_INDEX, id=doc_id)
        if doc_exists_after_deletion:
            logger.warning(
                f"Tài liệu với ID {doc_id} vẫn tồn tại sau khi xóa.")
        else:
            logger.info(f"Tài liệu với ID {doc_id} đã được xóa hoàn toàn.")
        logger.info(
            f"Successfully deleted document with ID {doc_id} from Elasticsearch")
    except Exception as e:
        logger.error(f"Failed to delete document with ID {doc_id}: {str(e)}")
        raise

def update_document(writer: AsyncWriter, doc: Document):
    tags = ",".join([t.name for t in doc.tags.all()])
    tags_ids = ",".join([str(t.id) for t in doc.tags.all()])
    notes = ",".join([str(c.note) for c in Note.objects.filter(document=doc)])
    custom_fields = ",".join(
        [str(c) for c in CustomFieldInstance.objects.filter(document=doc)],
    )
    asn = doc.archive_serial_number
    if asn is not None and (
        asn < Document.ARCHIVE_SERIAL_NUMBER_MIN
        or asn > Document.ARCHIVE_SERIAL_NUMBER_MAX
    ):
        logger.error(
            f"Not indexing Archive Serial Number {asn} of document {doc.pk}. "
            f"ASN is out of range "
            f"[{Document.ARCHIVE_SERIAL_NUMBER_MIN:,}, "
            f"{Document.ARCHIVE_SERIAL_NUMBER_MAX:,}.",
        )
        asn = 0
    users_with_perms = get_users_with_perms(
        doc,
        only_with_perms_in=["view_document"],
    )
    viewer_ids = ",".join([str(u.id) for u in users_with_perms])
    writer.update_document(
        id=doc.pk,
        title=doc.title,
        content=doc.content,
        correspondent=doc.correspondent.name if doc.correspondent else None,
        correspondent_id=doc.correspondent.id if doc.correspondent else None,
        has_correspondent=doc.correspondent is not None,
        tag=tags if tags else None,
        tag_id=tags_ids if tags_ids else None,
        has_tag=len(tags) > 0,
        type=doc.document_type.name if doc.document_type else None,
        type_id=doc.document_type.id if doc.document_type else None,
        has_type=doc.document_type is not None,
        warehouse=doc.warehouse.name if doc.warehouse else None,
        warehouse_id=doc.warehouse.id if doc.warehouse else None,
        has_warehouse=doc.warehouse is not None,
        folder=doc.folder.name if doc.folder else None,
        folder_id=doc.folder.id if doc.folder else None,
        has_folder=doc.folder is not None,
        created=doc.created,
        added=doc.added,
        asn=asn,
        modified=doc.modified,
        path=doc.storage_path.name if doc.storage_path else None,
        path_id=doc.storage_path.id if doc.storage_path else None,
        has_path=doc.storage_path is not None,
        notes=notes,
        num_notes=len(notes),
        custom_fields=custom_fields,
        custom_field_count=len(doc.custom_fields.all()),
        owner=doc.owner.username if doc.owner else None,
        owner_id=doc.owner.id if doc.owner else None,
        has_owner=doc.owner is not None,
        viewer_id=viewer_ids if viewer_ids else None,
        checksum=doc.checksum,
        page_count=doc.page_count,
        original_filename=doc.original_filename,
        is_shared=len(viewer_ids) > 0,
    )


def remove_document(writer: AsyncWriter, doc: Document):
    # remove_document_by_id(writer, doc.pk)
    delete_document_index(doc=doc)


def remove_document_by_id(writer: AsyncWriter, doc_id):
    writer.delete_by_term("id", doc_id)


def add_or_update_document(document: Document):
    # with open_index_writer() as writer:
    # update_document(writer, document)
    update_index_document(document)


def remove_document_from_index(document: Document):
    # with open_index_writer() as writer:
    remove_document(None, document)


class DelayedQuery:
    param_map = {
        # "title": ("title", ["icontains"]),
        # "title_content": ("title_content", ["icontains"]),
        "correspondent": ("correspondent", ["id", "id__in", "id__none", "isnull"]),
        "archive_font": ("archive_font", ["id", "id__in", "id__none", "isnull"]),
        "warehouse": ("warehouse", ["id", "id__in", "id__none", "isnull"]),
        "warehouse_w": ("warehouse", ["id", "id__in", "id__none", "isnull"]),
        "warehouse_s": ("warehouse", ["id", "id__in", "id__none", "isnull"]),
        "folder": ("folder", ["id", "id__in", "id__none", "isnull"]),
        "document_type": ("type", ["id", "id__in", "id__none", "isnull"]),
        "storage_path": ("path", ["id", "id__in", "id__none", "isnull"]),
        "owner": ("owner", ["id", "id__in", "id__none", "isnull"]),
        "shared_by": ("shared_by", ["id"]),
        "tags": ("tag", ["id__all", "id__in", "id__none"]),
        "added": ("added", ["date__lt", "date__gt"]),
        "created": ("created", ["date__lt", "date__gt"]),
        "checksum": ("checksum", ["icontains", "istartswith"]),
        "original_filename": ("original_filename", ["icontains", "istartswith"]),
        "custom_fields": ("custom_fields", ["icontains", "istartswith"]),
    }

    def _get_query(self):
        raise NotImplementedError

    def _get_query_filter(self):
        criterias = []
        for key, value in self.query_params.items():
            # is_tagged is a special case
            if key == "is_tagged":
                criterias.append(query.Term("has_tag", self.evalBoolean(value)))
                continue

            # Don't process query params without a filter
            if "__" not in key:
                continue

            # All other query params consist of a parameter and a query filter
            param, query_filter = key.split("__", 1)
            try:
                field, supported_query_filters = self.param_map[param]
            except KeyError:
                logger.error(f"Unable to build a query filter for parameter {key}")
                continue

            # We only support certain filters per parameter
            if query_filter not in supported_query_filters:
                logger.info(
                    f"Query filter {query_filter} not supported for parameter {param}",
                )
                continue

            if query_filter == "id":
                if param == "shared_by":
                    criterias.append(query.Term("is_shared", True))
                    criterias.append(query.Term("owner_id", value))
                else:
                    criterias.append(query.Term(f"{field}_id", value))
            elif query_filter == "id__in":
                in_filter = []
                for object_id in value.split(","):
                    in_filter.append(
                        query.Term(f"{field}_id", object_id),
                    )
                criterias.append(query.Or(in_filter))
            elif query_filter == "id__none":
                for object_id in value.split(","):
                    criterias.append(
                        query.Not(query.Term(f"{field}_id", object_id)),
                    )
            elif query_filter == "isnull":
                criterias.append(
                    query.Term(f"has_{field}", self.evalBoolean(value) is False),
                )
            elif query_filter == "id__all":
                for object_id in value.split(","):
                    criterias.append(query.Term(f"{field}_id", object_id))
            elif query_filter == "date__lt":
                criterias.append(
                    query.DateRange(field, start=None, end=isoparse(value)),
                )
            elif query_filter == "date__gt":
                criterias.append(
                    query.DateRange(field, start=isoparse(value), end=None),
                )
            elif query_filter == "icontains":
                criterias.append(
                    query.Term(field, value),
                )
            elif query_filter == "istartswith":
                criterias.append(
                    query.Prefix(field, value),
                )

        user_criterias = get_permissions_criterias(
            user=self.user,
        )
        if len(criterias) > 0:
            if len(user_criterias) > 0:
                criterias.append(query.Or(user_criterias))
            return query.And(criterias)
        else:
            return query.Or(user_criterias) if len(user_criterias) > 0 else None

    def evalBoolean(self, val):
        return val.lower() in {"true", "1"}

    def _get_query_sortedby(self):
        if "ordering" not in self.query_params:
            return None, False

        field: str = self.query_params["ordering"]

        sort_fields_map = {
            "created": "created",
            "modified": "modified",
            "added": "added",
            "title": "title",
            "correspondent__name": "correspondent",
            "document_type__name": "type",
            "archive_serial_number": "asn",
            "num_notes": "num_notes",
            "owner": "owner",
            "page_count": "page_count",
        }

        if field.startswith("-"):
            field = field[1:]
            reverse = True
        else:
            reverse = False

        if field not in sort_fields_map:
            return None, False
        else:
            return sort_fields_map[field], reverse

    def __init__(self, searcher: Searcher, query_params, page_size, user):
        self.searcher = searcher
        self.query_params = query_params
        self.page_size = page_size
        self.saved_results = dict()
        self.first_score = None
        self.user = user
        self.es = Elasticsearch()
        self.count_item = 0
        # if not self.es.indices.exists(index=ELASTIC_SEARCH_DOCUMENT_INDEX):
        #     DocumentDocument.init()  # Tạo index nếu chưa có
        #     logger.info(f"Index '{ELASTIC_SEARCH_DOCUMENT_INDEX}' created")
        # else:
        #     logger.info(
        #         f"Index '{ELASTIC_SEARCH_DOCUMENT_INDEX}' already exists")

    def __len__(self):
        page = self[0:1]
        return len(page)

    def __getitem__(self, item):
        if item.start in self.saved_results:
            return self.saved_results[item.start]

        q, mask = self._get_query()
        sortedby, reverse = self._get_query_sortedby()

        page: ResultsPage = self.searcher.search_page(
            q,
            mask=mask,
            filter=self._get_query_filter(),
            pagenum=math.floor(item.start / self.page_size) + 1,
            pagelen=self.page_size,
            sortedby=sortedby,
            reverse=reverse,
        )
        page.results.fragmenter = highlight.ContextFragmenter(surround=50)
        page.results.formatter = HtmlFormatter(tagname="span", between=" ... ")
        if not self.first_score and len(page.results) > 0 and sortedby is None:
            self.first_score = page.results[0].score

        page.results.top_n = list(
            map(
                lambda hit: (
                    (hit[0] / self.first_score) if self.first_score else None,
                    hit[1],
                ),
                page.results.top_n,
            ),
        )

        self.saved_results[item.start] = page
        return page


class LocalDateParser(English):
    def reverse_timezone_offset(self, d):
        return (d.replace(tzinfo=django_timezone.get_current_timezone())).astimezone(
            timezone.utc,
        )

    def date_from(self, *args, **kwargs):
        d = super().date_from(*args, **kwargs)
        if isinstance(d, timespan):
            d.start = self.reverse_timezone_offset(d.start)
            d.end = self.reverse_timezone_offset(d.end)
        elif isinstance(d, datetime):
            d = self.reverse_timezone_offset(d)
        return d

class StatisticElasticSearch():
    def get_statistics(self):
        query = {
            "size": 0,
            "aggs": {
                "tags_stats": {
                    "terms": {"field": "tag_id", "size": 100}
                },
                "document_type_stats": {
                    "terms": {"field": "document_type_id", "size": 100}
                },
                "warehouse_stats": {
                    "terms": {"field": "warehouse_id", "size": 100}
                }
            }
        }
        s = Search(
            index=ELASTIC_SEARCH_DOCUMENT_INDEX)
        s = s.query(query)
        response = s.execute()

        # Xử lý kết quả trả về
        return {
            "selected_tags": [
                {"id": bucket["key"], "document_count": bucket["doc_count"]}
                for bucket in response["aggregations"]["tags_stats"]["buckets"]
                if bucket["key"] != -1
            ],
            "selected_document_types": [
                {"id": bucket["key"], "document_count": bucket["doc_count"]}
                for bucket in
                response["aggregations"]["document_type_stats"]["buckets"] if
                bucket["key"] != -1

            ],
            "selected_warehouses": [
                {"id": bucket["key"], "document_count": bucket["doc_count"]}
                for bucket in
                response["aggregations"]["warehouse_stats"]["buckets"] if
                bucket["key"] != -1
            ]
        }


class DelayedFullTextQuery(DelayedQuery):
    def _get_query(self):
        q_str = self.query_params["query"]
        qp = MultifieldParser(
            [
                "content",
                "title",
                "correspondent",
                "tag",
                "type",
                "notes",
                "custom_fields",
            ],
            self.searcher.ixreader.schema,
        )
        qp.add_plugin(
            DateParserPlugin(
                basedate=django_timezone.now(),
                dateparser=LocalDateParser(),
            ),
        )
        q = qp.parse(q_str)
        corrected = self.searcher.correct_query(q, q_str)
        if corrected.query != q:
            corrected.query = corrected.string
        return q, None

class DelayedElasticSearch(DelayedQuery):

    def __init__(self, searcher: Searcher, query_params, page_size, user):
        super().__init__(searcher, query_params, page_size, user)
        self.response = self.search_pagination(
            self.query_params.get("query", ''), int(self.query_params['page']),
            int(self.query_params['page_size']))
    def _get_query_sortedby(self):
        if "ordering" not in self.query_params:
            return None, False

        field: str = self.query_params["ordering"]

        sort_fields_map = {
            "created": "created",
            "modified": "modified",
            "added": "added",
            "title": "title.keyword",
            "correspondent__name": "correspondent",
            "document_type__name": "type.keyword",
            "warehouse__name": "warehouse.keyword",
            "archive_serial_number": "asn",
            "num_notes": "num_notes",
            "owner": "owner.keyword",
            "page_count": "page_count",
            "score": "score"
        }

        if field.startswith("-"):
            field = field[1:]
            reverse = True
        else:
            reverse = False

        if field not in sort_fields_map:
            return None, False
        else:
            return sort_fields_map[field], reverse

    def _get_query(self):
        q_str = self.query_params.get("query", "")
        # Tìm vị trí bắt đầu của "created" và cắt chuỗi
        cleaned_string = q_str
        if "created:" in q_str:
            cleaned_string = q_str[
                             :q_str.index("created:")].rstrip(',')
        elif "added:" in q_str:
            cleaned_string = q_str[
                             :q_str.index("added:")].rstrip(',')
        exact_matches = re.findall(r'"(.*?)"', q_str)

        # Loại bỏ các chuỗi trong dấu ngoặc kép để tạo thành cleaned_string
        # cleaned_string = re.sub(r'"(.*?)"', '', q_str).strip()
        exact_queries = [Q("match_phrase", content=match) for match in
                         exact_matches]
        cleaned_string = cleaned_string.replace('"', '')
        normal_query = []

        if cleaned_string and 'query' in self.query_params:
            normal_query = [
                Q("multi_match",
                  type="phrase",
                  query=cleaned_string,
                  fields=["content^3", "title^2", "tag^1.5", "type^1",
                          "notes^0.5", "custom_fields^1"],
                  boost=5,
                  slop=1
                  )
                | Q("multi_match",
                    query=cleaned_string,
                    fields=["content^3", "title^2", "tag^1.5", "type^1",
                            "notes^0.5", "custom_fields^1"],
                    boost=1,
                    minimum_should_match="85%"
                    )
            ]

        final_query = Q("bool", must=exact_queries + normal_query)

        return final_query  # Chỉ trả về một truy vấn

    def _get_query_filter(self):
        criterias = []
        q_str = self.query_params.get("query", "")
        added = re.search(r'added:\[(.*?)\]', q_str)
        created = re.search(r'created:\[(.*?)\]', q_str)
        map_created = {'-1 week to now': "now-7d/d",
                       '-1 month to now': "now-1M",
                       '-3 month to now': "now-3M/M",
                       '-1 year to now': "now-1y", }
        if added is not None:
            criterias.append(Q("range", **{'added': {"lte": "now/d"}}))
            criterias.append(Q("range", **{'added': {"gte": map_created[added.group(1)]}}))
        if created is not None:
            criterias.append(Q("range", **{'created': {"lte": "now/d"}}))
            criterias.append(Q("range", **{'created': {"gte": map_created[created.group(1)]}}))

        for key, value in self.query_params.items():
            if key == "is_tagged":
                criterias.append(Q("term", has_tag=self.evalBoolean(value)))
                continue
            if key == "title_content":
                criterias.append(
                    Q("bool", should=[
                        Q("match_phrase_prefix", **{"title": value}),
                        Q("match_phrase_prefix", **{"content": value})
                    ])
                )
                continue
            if key == "title__icontains":
                criterias.append(
                   Q("match_phrase_prefix", **{"title": value})
                )
                continue

            if "__" not in key:
                continue

            param, query_filter = key.split("__", 1)
            try:
                field, supported_query_filters = self.param_map[param]
            except KeyError:
                continue

            if query_filter not in supported_query_filters:
                continue

            if query_filter == "id":
                if param == "shared_by":
                    criterias.append(Q("term", is_shared=True))
                    criterias.append(Q("term", owner_id=value))
                else:
                    criterias.append(Q("term", **{f"{field}_id": value}))
            elif query_filter == "id__in":
                if field in {"warehouse"}:
                    warehouses = Warehouse.objects.filter(id__in=value.split(","))
                    in_filter = [Q("prefix", **{'warehouse_path': object.path}) for
                                 object in warehouses]
                    criterias.append(Q("bool", should=in_filter))
                    continue
                elif field in {"folder"}:
                    folders = Folder.objects.filter(id__in=value.split(","))

                    if folders is not None:
                        in_filter = [
                            Q("match_phrase_prefix",
                              **{'folder_path': object.path})
                            for object in folders]
                        criterias.append(Q("bool", should=in_filter))
                        # print('in_filter', in_filter)
                    continue
                elif field in {"tag"}:
                    in_filter = [Q("term", **{f"tag_id": int(object_id)}) for
                                 object_id in value.split(",")]
                    criterias.append(Q("bool", should=in_filter))
                    continue
                in_filter = [Q("term", **{f"{field}_id": object_id}) for object_id in value.split(",")]
                criterias.append(Q("bool", should=in_filter))
            elif query_filter == "id__none":
                if field in {"warehouse"}:
                    warehouses = Warehouse.objects.filter(id__in=value.split(","))
                    in_filter = [Q("prefix", **{'warehouse_path': object.path}) for
                                 object in warehouses]
                    criterias.append(
                        Q("bool", must_not=Q("bool", should=in_filter))
                    )
                    continue
                for object_id in value.split(","):
                    criterias.append(Q("bool", must_not=Q("term", **{f"{field}_id": object_id})))
            elif query_filter == "isnull":
                criterias.append(Q("term", **{f"has_{field}": not self.evalBoolean(value)}))
            elif query_filter == "id__all":
                if field in {"tag"}:
                    in_filter = [Q("term", **{'tag_id': int(object_id)}) for
                                 object_id in value.split(",")]
                    criterias.append(
                        Q("bool", must=in_filter)
                        # Thay đổi từ 'should' thành 'must'
                    )
                    continue
                for object_id in value.split(","):
                    criterias.append(Q("term", **{f"{field}_id": object_id}))
            elif query_filter == "date__lt":
                criterias.append(Q("range", **{field: {"lt": isoparse(value)}}))
            elif query_filter == "date__gt":
                criterias.append(Q("range", **{field: {"gt": isoparse(value)}}))
            elif query_filter == "date__lte":
                criterias.append(
                    Q("range", **{field: {"lte": isoparse(value)}}))
            elif query_filter == "date__gte":
                criterias.append(
                    Q("range", **{field: {"gte": isoparse(value)}}))
            elif query_filter == "icontains":
                criterias.append(Q("match", **{field: value}))
            elif query_filter == "istartswith":
                criterias.append(Q("prefix", **{field: value}))
        user_criterias = None
        if str.__eq__(remove_time_queries(q_str), ''):
            user_criterias = get_permissions_criterias_elastic_search(user=self.user)
        print('user_criterias', user_criterias)
        if criterias:
            if user_criterias:
                criterias.append(Q("bool", should=user_criterias))
            return Q("bool", must=criterias)
        else:
            return Q("bool", should=user_criterias) if user_criterias else None

    def get_combined_query(self):
        base_query = self._get_query()  # Lấy truy vấn cơ bản
        filter_query = self._get_query_filter()  # Lấy truy vấn lọc
        # Lấy trường và chiều sắp xếp
        sort_field, reverse = self._get_query_sortedby()

        # Tạo danh sách sắp xếp
        sort_order = {sort_field: {
            "order": "desc" if reverse else "asc"}} if sort_field else None

        combined_query = base_query
        # Khởi tạo truy vấn bool
        if filter_query:
            combined_query = Q("bool", must=[base_query, filter_query])

        # Thêm phần sắp xếp vào truy vấn cuối cùng
        query_body = {
            "query": combined_query.to_dict(),
            "sort": [sort_order] if sort_order else [],

        }
        print('query_body', query_body)
        return query_body

    def count(self):
        return self.count_item

    def search_pagination(self, content, page_number, page_size):
        s = Search(
            index=ELASTIC_SEARCH_DOCUMENT_INDEX)  # Thay 'your_index_name' bằng tên chỉ mục của bạn


        query_combined = self.get_combined_query()
        print('query_combined',query_combined)
        s = s.query(query_combined['query'])  # Chỉ lấy phần query
        s = s.sort(*query_combined.get('sort', []))  # Thêm phần sắp xếp nếu có

        s = s.highlight('content', fragment_size=500, number_of_fragments=1,
                        pre_tags=['<span class="match">'],
                        post_tags=['</span>'],
                        max_analyzed_offset=900000)
        s = s.source(['id', 'warehouse_path', 'tag_id', 'custom_fields','notes'])
        s = s[page_number * page_size - page_size:page_number * page_size]
        s = s.extra(track_total_hits=True)
        response = s.execute()
        self.count_item = response.hits.total.value
        # print(self.search_statistics())
        return response



    def search_statistics(self):
        query_combined = self.get_combined_query()
        aggregations = {
            "tags_stats": {
                "terms": {"field": "tag_id", "size": 100}
            },
            "document_type_stats": {
                "terms": {"field": "type_id", "size": 100}
            },
            "warehouse_stats": {
                "terms": {"field": "warehouse_id", "size": 100}
            }
        }
        query_combined['aggs'] = aggregations
        statistics_query = {
            "query": query_combined['query'],
            "aggs": query_combined["aggs"]
        }

        # Thực hiện query
        response = Search().from_dict(statistics_query).index(
            ELASTIC_SEARCH_DOCUMENT_INDEX).execute()
        tags = Tag.objects.all()
        selected_tags_dict = {}
        selected_tags = []
        for bucket in response["aggregations"]["tags_stats"]["buckets"]:
            selected_tags_dict[bucket["key"]] = bucket["doc_count"]
        for t in tags:
            selected_tags.append({
                "id": t.id,
                "document_count": selected_tags_dict.get(t.id, 0)
            })

        document_types = DocumentType.objects.all()
        select_document_types_dict = {}
        select_document_types = []
        for bucket in response["aggregations"]["document_type_stats"][
            "buckets"]:
            select_document_types_dict[bucket["key"]] = bucket["doc_count"]
        for dt in document_types:
            select_document_types.append({
                "id": dt.id,
                "document_count": select_document_types_dict.get(dt.id, 0)
            })

        warehouses = Warehouse.objects.all()
        select_warehouses_dict = {}
        select_warehouses = []
        for bucket in response["aggregations"]["warehouse_stats"]["buckets"]:
            select_warehouses_dict[bucket["key"]] = bucket["doc_count"]
        for w in warehouses:
            select_warehouses.append({
                "id": w.id,
                "document_count": select_warehouses_dict.get(w.id, 0)
            })

        # Xử lý kết quả từ aggregations
        statistics = {
            "selected_tags": selected_tags,
            "selected_document_types": select_document_types,
            "selected_warehouses": select_warehouses,
            "selected_storage_paths": [],
            "selected_correspondents": [],
            "selected_archive_fonts": [],
            "selected_shelfs": [],
            "selected_boxcases": []
        }
        return statistics

    def search_get_all(self):
        s = Search(
            index=ELASTIC_SEARCH_DOCUMENT_INDEX)  # Thay 'your_index_name' bằng tên chỉ mục của bạn
        query_combined = self.get_combined_query()
        s = s.query(query_combined['query'])  # Chỉ lấy phần query
        s = s.source(['id'])
        response = s.scan()
        # Chuyển đổi kết quả thành danh sách các id
        start_time = time.time()
        doc_ids = [int(doc.meta.id) for doc in response]
        time_get_all = time.time()-start_time

        print('time_get_all',time_get_all)
        # doc_ids = {int(doc.meta.id) for doc in response}
        return []

    def __getitem__(self, item):
        if item.start in self.saved_results:
            return self.saved_results[item.start]

        # q, mask = self._get_query()
        sortedby, reverse = self._get_query_sortedby()

        page_num = math.floor(item.start / self.page_size) + 1
        page_len = self.page_size
        # response = convert_elastic_search(self.query_params["query"], page_num , page_len)

        if self.query_params.get("statistic", False):
            response = self.search_statistics()
            return response

        # response = self.search_pagination(self.query_params.get("query",''), page_num , page_len)
        response = self.response
        # print('tim____:',datetime.now() -start)
        doc_ids = [int(d.meta.id) for d in response]

        # print('ket qua',self.get_combined_query())
        # start = datetime.now()
        docs = (
            Document.objects.select_related(
                # "correspondent",
                # "storage_path",
                # "document_type",
                # "warehouse",
                # "folder",
                "owner",
            )
            # .prefetch_related("tags","custom_fields", "notes")
            .filter(id__in=doc_ids).annotate(
                truncated_content=Substr('content', 1, 500)  # Lấy tối đa 500 ký tự từ content
            )
            .defer(
                # 'content',
                'owner__password',  # Bỏ qua trường password
                'owner__is_staff',   # Bỏ qua trường is_staff
                'owner__is_active',  # Bỏ qua trường is_active
                'owner__date_joined' # Bỏ qua trường date_joined
            )
        )

        # print('time',datetime.now()-start)
        start_time = time.time()
        # map docs to dict
        dict_docs = dict()
        for d in docs:
            dict_docs[d.id]=d
        time_set_dict= time.time() - start_time
        print('time_set_dict', time_set_dict)
        start_time = time.time()
        # mapping docs to response
        for r in response:
            if dict_docs.get(int(r.meta.id), None):
                r.doc_obj = dict_docs[int(r.meta.id)]
        time_mapping_docs_response = time.time()-start_time
        print('time_mapping_docs_response', time_mapping_docs_response)
        start_time = time.time()
        # all_doc_ids = self.search_get_all()
        time_get_all = time.time()-start_time
        print('time_get_all', time_get_all)
        page: ResultsPage = ResultsPage(response, page_num, page_len)
        # filter = self._get_query_filter()
        # page: ResultsPage = self.searcher.search_page(
        #     q,
        #     mask=mask,
        #     filter=self._get_query_filter(),
        #     pagenum=math.floor(item.start / self.page_size) + 1,
        #     pagelen=self.page_size,
        #     sortedby=sortedby,
        #     reverse=reverse,
        # )
        page.results.fragmenter = highlight.ContextFragmenter(surround=50)
        page.results.formatter = HtmlFormatter(tagname="span", between=" ... ")

        # page.results.doc = []
        if not self.first_score and len(page.results) > 0 and sortedby is None:
            self.first_score = getattr(page.results[0].meta, 'score')
        self.saved_results[item.start] = page
        return page

class DelayedElasticSearchLikeMore(DelayedElasticSearch):


    def _get_query(self):
        q_str = self.query_params.get("more_like_id", "")
        # Tìm vị trí bắt đầu của "created" và cắt chuỗi
        cleaned_string = q_str
        if "created:" in q_str:
            cleaned_string = q_str[
                             :q_str.index("created:")].rstrip(',')
        elif "added:" in q_str:
            cleaned_string = q_str[
                             :q_str.index("added:")].rstrip(',')

        query = Q(
            "more_like_this",
            fields=[
                "content",
                "title",
                "correspondent",
                "tag",
                "type",
                "notes",
                "custom_fields",
            ],
            like={"_index": ELASTIC_SEARCH_DOCUMENT_INDEX,
                  "_id": str(cleaned_string)},
        )

        return query  # Chỉ trả về một truy vấn


    def get_combined_query(self):
        base_query = self._get_query()  # Lấy truy vấn cơ bản
        filter_query = self._get_query_filter()  # Lấy truy vấn lọc

        # Lấy trường và chiều sắp xếp
        sort_field, reverse = self._get_query_sortedby()

        # Tạo danh sách sắp xếp
        sort_order = {sort_field: {
            "order": "desc" if reverse else "asc"}} if sort_field else None

        # Khởi tạo truy vấn bool
        if filter_query:
            combined_query = Q("bool", must=[base_query, filter_query])
        else:
            combined_query = base_query

        # Thêm phần sắp xếp vào truy vấn cuối cùng
        query_body = {
            "query": combined_query.to_dict(),
            "sort": [sort_order] if sort_order else []
        }

        return query_body

    def search_pagination(self, content, page_number, page_size):
        s = Search(
            index=ELASTIC_SEARCH_DOCUMENT_INDEX)  # Thay 'your_index_name' bằng tên chỉ mục của bạn


        query_combined = self.get_combined_query()
        s = s.query(query_combined['query'])  # Chỉ lấy phần query
        s = s.sort(*query_combined.get('sort', []))  # Thêm phần sắp xếp nếu có

        s = s.highlight('content', fragment_size=500, number_of_fragments=1,
                        pre_tags=['<span class="match">'],
                        post_tags=['</span>'])
        s = s.source(['id'])
        s = s[page_number * page_size - page_size:page_number * page_size]
        response = s.execute()
        return response

    def search_get_all(self):
        s = Search(
            index=ELASTIC_SEARCH_DOCUMENT_INDEX)  # Thay 'your_index_name' bằng tên chỉ mục của bạn
        query_combined = self.get_combined_query()
        s = s.query(query_combined['query'])  # Chỉ lấy phần query
        s = s.source(['id'])
        response = s.scan()
        doc_ids = {int(doc.meta.id) for doc in response}
        return doc_ids

    def __getitem__(self, item):
        if item.start in self.saved_results:
            return self.saved_results[item.start]

        # q, mask = self._get_query()
        sortedby, reverse = self._get_query_sortedby()

        # print('ket qua',self.get_combined_query())
        page_num = math.floor(item.start / self.page_size) + 1
        page_len = self.page_size
        start = datetime.now()
        # response = convert_elastic_search(self.query_params["query"], page_num , page_len)
        response = self.search_pagination(self.query_params["more_like_id"], page_num , page_len)

        # print('tim____:',datetime.now() -start)
        doc_ids = [int(d.meta.id) for d in response]

        docs = Document.objects.select_related(
                "correspondent",
                "storage_path",
                "document_type",
                "warehouse",
                "folder",
                "owner",
            ).prefetch_related("tags", "custom_fields", "notes").filter(id__in=doc_ids).defer('content')
        # map docs to dict
        dict_docs = dict()
        for d in docs:
            dict_docs[d.id]=d

        # mapping docs to response
        for r in response:
            r.doc_obj = dict_docs[int(r.meta.id)]

        all_doc_ids = self.search_get_all()
        page: ResultsPage = ResultsPage(response, page_num, page_len)
        # filter = self._get_query_filter()
        # page: ResultsPage = self.searcher.search_page(
        #     q,
        #     mask=mask,
        #     filter=self._get_query_filter(),
        #     pagenum=math.floor(item.start / self.page_size) + 1,
        #     pagelen=self.page_size,
        #     sortedby=sortedby,
        #     reverse=reverse,
        # )
        page.results.fragmenter = highlight.ContextFragmenter(surround=50)
        page.results.formatter = HtmlFormatter(tagname="span", between=" ... ")

        page.results.doc = all_doc_ids
        if not self.first_score and len(page.results) > 0 and sortedby is None:
            self.first_score = getattr(page.results[0].meta, 'score')
        # page.results.top_n = list(
        #     map(
        #         lambda hit: (
        #             (hit[0] / self.first_score) if self.first_score else None,
        #             hit[1],
        #         ),
        #         page.results.top_n,
        #     ),
        # )
        # print(page.results)
        page.total = len(all_doc_ids)


        self.saved_results[item.start] = page
        return page


class DelayedMoreLikeThisQuery(DelayedQuery):
    def _get_query(self):
        more_like_doc_id = int(self.query_params["more_like_id"])
        content = Document.objects.get(id=more_like_doc_id).content

        docnum = self.searcher.document_number(id=more_like_doc_id)
        kts = self.searcher.key_terms_from_text(
            "content",
            content,
            numterms=20,
            model=classify.Bo1Model,
            normalize=False,
        )
        q = query.Or(
            [query.Term("content", word, boost=weight) for word, weight in kts],
        )
        mask = {docnum}
        return q, mask
def autocomplete_elastic_search(query):
    s = Search(index=settings.ELASTIC_SEARCH_DOCUMENT_INDEX)
    if query:
        # s.suggest('song-suggest',
        #           text='ne',
        #           completion={
        #               'field': 'suggest',
        #               'size': 5,
        #               'skip_duplicates': True
        #           })
        s = s.suggest('suggest', query.lower(), completion ={'field': 'suggest', 'skip_duplicates': True, 'size':10})
        s = s.source(['id'])
        response = s.execute()
        return [s.text for s in response.suggest.suggest[0].options]

def autocomplete_string_elastic_search(query):
    s = Search(index=settings.ELASTIC_SEARCH_DOCUMENT_INDEX)
    if query:
        # s.suggest('song-suggest',
        #           text='ne',
        #           completion={
        #               'field': 'suggest',
        #               'size': 5,
        #               'skip_duplicates': True
        #           })
        s = s.suggest(
            "phrase_suggest",
            text = query,
            completion={
                "field": "suggest_content",
                "size": 10,
                "skip_duplicates": True
            }
        )
        s = s.source(['id'])
        response = s.execute()
        return [s.text for s in response.suggest.phrase_suggest[0].options]

def autocomplete(
    ix: FileIndex,
    term: str,
    limit: int = 10,
    user: Optional[User] = None,
):
    """
    Mimics whoosh.reading.IndexReader.most_distinctive_terms with permissions
    and without scoring
    """
    terms = []

    with ix.searcher(weighting=TF_IDF()) as s:
        qp = QueryParser("content", schema=ix.schema)
        # Don't let searches with a query that happen to match a field override the
        # content field query instead and return bogus, not text data
        qp.remove_plugin_class(FieldsPlugin)
        q = qp.parse(f"{term.lower()}*")
        user_criterias = get_permissions_criterias(user)

        results = s.search(
            q,
            terms=True,
            filter=query.Or(user_criterias) if user_criterias is not None else None,
        )

        termCounts = Counter()
        if results.has_matched_terms():
            for hit in results:
                for _, match in hit.matched_terms():
                    termCounts[match] += 1
            terms = [t for t, _ in termCounts.most_common(limit)]

        term_encoded = term.encode("UTF-8")
        if term_encoded in terms:
            terms.insert(0, terms.pop(terms.index(term_encoded)))

    return terms


def get_permissions_criterias(user: Optional[User] = None):
    user_criterias = [query.Term("has_owner", False)]
    if user is not None:
        if user.is_superuser:  # superusers see all docs
            user_criterias = []
        # else:
        #     user_criterias.append(query.Term("owner_id", user.id))
        #     user_criterias.append(
        #         query.Term("viewer_id", str(user.id)),
        #     )
        user_criterias = []
    return user_criterias

def remove_time_queries(query):
    # Sử dụng regex để loại bỏ đoạn created: hoặc added: cùng giá trị của nó
    cleaned_query = re.sub(r"(created:\[.*?\]|added:\[.*?\])", "", query)
    # Loại bỏ dấu phẩy thừa hoặc khoảng trắng dư thừa
    cleaned_query = re.sub(r",\s*", ", ", cleaned_query).strip(", ")
    return cleaned_query

def get_permissions_criterias_elastic_search(user: Optional[User] = None):
    # user_criterias = [Q("term", has_owner=False)]
    user_criterias = []
    if user is not None:
        if user.is_superuser:  # Superuser có thể xem tất cả tài liệu
            user_criterias = []
        else:
            # Nếu không phải superuser, thêm điều kiện cho owner_id và viewer_id
            group_ids = user.groups.all().values_list('id', flat=True)
            user_criterias.append(Q("term", owner_id=user.id))
            user_criterias.append(Q("term", viewer_id=str(user.id)))
            # user_criterias.append(Q("term", view_groups=group_ids))
            if group_ids:
                in_filter = [Q("term", **{f"view_groups": g}) for g in
                             group_ids]
                user_criterias.append(Q("bool", should=in_filter))
            # in_filter = [Q("term", **{f"view_groups": g}) for g
            #              in group_ids]
            # user_criterias.append(Q("bool", should=in_filter))
    return Q("bool", should=user_criterias) if user_criterias else None
