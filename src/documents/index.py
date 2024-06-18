import logging
import math
import os
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from shutil import rmtree
from typing import Optional

from dateutil.parser import isoparse
from django.conf import settings
from django.utils import timezone as django_timezone
from guardian.shortcuts import get_users_with_perms
from whoosh import classify
from whoosh import highlight
from whoosh import query
from whoosh.fields import BOOLEAN
from whoosh.fields import DATETIME
from whoosh.fields import KEYWORD
from whoosh.fields import NUMERIC
from whoosh.fields import TEXT
from whoosh.fields import Schema
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

from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Note
from documents.models import User

logger = logging.getLogger("paperless.index")


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
        original_filename=doc.original_filename,
        is_shared=len(viewer_ids) > 0,
    )


def remove_document(writer: AsyncWriter, doc: Document):
    remove_document_by_id(writer, doc.pk)


def remove_document_by_id(writer: AsyncWriter, doc_id):
    writer.delete_by_term("id", doc_id)


def add_or_update_document(document: Document):
    with open_index_writer() as writer:
        update_document(writer, document)


def remove_document_from_index(document: Document):
    with open_index_writer() as writer:
        remove_document(writer, document)


class DelayedQuery:
    param_map = {
        "correspondent": ("correspondent", ["id", "id__in", "id__none", "isnull"]),
        "warehouse": ("warehouse", ["id", "id__in", "id__none", "isnull"]),
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
