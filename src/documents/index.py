from __future__ import annotations

import logging
import math
import re
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from datetime import time
from datetime import timedelta
from datetime import timezone
from shutil import rmtree
from time import sleep
from typing import TYPE_CHECKING
from typing import Literal

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.utils import timezone as django_timezone
from django.utils.timezone import get_current_timezone
from django.utils.timezone import now
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
from whoosh.idsets import BitSet
from whoosh.idsets import DocIdSet
from whoosh.index import FileIndex
from whoosh.index import LockError
from whoosh.index import create_in
from whoosh.index import exists_in
from whoosh.index import open_dir
from whoosh.qparser import MultifieldParser
from whoosh.qparser import QueryParser
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.qparser.dateparse import English
from whoosh.qparser.plugins import FieldsPlugin
from whoosh.scoring import TF_IDF
from whoosh.util.times import timespan
from whoosh.writing import AsyncWriter

from documents.models import CustomFieldInstance
from documents.models import Document
from documents.models import Note
from documents.models import User

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from whoosh.reading import IndexReader
    from whoosh.searching import ResultsPage
    from whoosh.searching import Searcher

logger = logging.getLogger("paperless.index")


def get_schema() -> Schema:
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
        has_custom_fields=BOOLEAN(),
        custom_fields_id=KEYWORD(commas=True),
        owner=TEXT(),
        owner_id=NUMERIC(),
        has_owner=BOOLEAN(),
        viewer_id=KEYWORD(commas=True),
        checksum=TEXT(),
        page_count=NUMERIC(sortable=True),
        original_filename=TEXT(sortable=True),
        is_shared=BOOLEAN(),
    )


def open_index(*, recreate=False) -> FileIndex:
    transient_exceptions = (FileNotFoundError, LockError)
    max_retries = 3
    retry_delay = 0.1

    for attempt in range(max_retries + 1):
        try:
            if exists_in(settings.INDEX_DIR) and not recreate:
                return open_dir(settings.INDEX_DIR, schema=get_schema())
            break
        except transient_exceptions as exc:
            is_last_attempt = attempt == max_retries or recreate
            if is_last_attempt:
                logger.exception(
                    "Error while opening the index after retries, recreating.",
                )
                break

            logger.warning(
                "Transient error while opening the index (attempt %s/%s): %s. Retrying.",
                attempt + 1,
                max_retries + 1,
                exc,
            )
            sleep(retry_delay)
        except Exception:
            logger.exception("Error while opening the index, recreating.")
            break

    # create_in doesn't handle corrupted indexes very well, remove the directory entirely first
    if settings.INDEX_DIR.is_dir():
        rmtree(settings.INDEX_DIR)
    settings.INDEX_DIR.mkdir(parents=True, exist_ok=True)

    return create_in(settings.INDEX_DIR, get_schema())


@contextmanager
def open_index_writer(*, optimize=False) -> AsyncWriter:
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


def update_document(writer: AsyncWriter, doc: Document) -> None:
    tags = ",".join([t.name for t in doc.tags.all()])
    tags_ids = ",".join([str(t.id) for t in doc.tags.all()])
    notes = ",".join([str(c.note) for c in Note.objects.filter(document=doc)])
    custom_fields = ",".join(
        [str(c) for c in CustomFieldInstance.objects.filter(document=doc)],
    )
    custom_fields_ids = ",".join(
        [str(f.field.id) for f in CustomFieldInstance.objects.filter(document=doc)],
    )
    asn: int | None = doc.archive_serial_number
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
    viewer_ids: str = ",".join([str(u.id) for u in users_with_perms])
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
        created=datetime.combine(doc.created, time.min),
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
        has_custom_fields=len(custom_fields) > 0,
        custom_fields_id=custom_fields_ids if custom_fields_ids else None,
        owner=doc.owner.username if doc.owner else None,
        owner_id=doc.owner.id if doc.owner else None,
        has_owner=doc.owner is not None,
        viewer_id=viewer_ids if viewer_ids else None,
        checksum=doc.checksum,
        page_count=doc.page_count,
        original_filename=doc.original_filename,
        is_shared=len(viewer_ids) > 0,
    )
    logger.debug(f"Index updated for document {doc.pk}.")


def remove_document(writer: AsyncWriter, doc: Document) -> None:
    remove_document_by_id(writer, doc.pk)


def remove_document_by_id(writer: AsyncWriter, doc_id) -> None:
    writer.delete_by_term("id", doc_id)


def add_or_update_document(document: Document) -> None:
    with open_index_writer() as writer:
        update_document(writer, document)


def remove_document_from_index(document: Document) -> None:
    with open_index_writer() as writer:
        remove_document(writer, document)


class MappedDocIdSet(DocIdSet):
    """
    A DocIdSet backed by a set of `Document` IDs.
    Supports efficiently looking up if a whoosh docnum is in the provided `filter_queryset`.
    """

    def __init__(self, filter_queryset: QuerySet, ixreader: IndexReader) -> None:
        super().__init__()
        document_ids = filter_queryset.order_by("id").values_list("id", flat=True)
        max_id = document_ids.last() or 0
        self.document_ids = BitSet(document_ids, size=max_id)
        self.ixreader = ixreader

    def __contains__(self, docnum) -> bool:
        document_id = self.ixreader.stored_fields(docnum)["id"]
        return document_id in self.document_ids

    def __bool__(self) -> Literal[True]:
        # searcher.search ignores a filter if it's "falsy".
        # We use this hack so this DocIdSet, when used as a filter, is never ignored.
        return True


class DelayedQuery:
    def _get_query(self):
        raise NotImplementedError  # pragma: no cover

    def _get_query_sortedby(self) -> tuple[None, Literal[False]] | tuple[str, bool]:
        if "ordering" not in self.query_params:
            return None, False

        field: str = self.query_params["ordering"]

        sort_fields_map: dict[str, str] = {
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

    def __init__(
        self,
        searcher: Searcher,
        query_params,
        page_size,
        filter_queryset: QuerySet,
    ) -> None:
        self.searcher = searcher
        self.query_params = query_params
        self.page_size = page_size
        self.saved_results = dict()
        self.first_score = None
        self.filter_queryset = filter_queryset
        self.suggested_correction = None
        self._manual_hits_cache: list | None = None

    def __len__(self) -> int:
        if self._manual_sort_requested():
            manual_hits = self._manual_hits()
            return len(manual_hits)

        page = self[0:1]
        return len(page)

    def _manual_sort_requested(self):
        ordering = self.query_params.get("ordering", "")
        return ordering.lstrip("-").startswith("custom_field_")

    def _manual_hits(self):
        if self._manual_hits_cache is None:
            q, mask, suggested_correction = self._get_query()
            self.suggested_correction = suggested_correction

            results = self.searcher.search(
                q,
                mask=mask,
                filter=MappedDocIdSet(self.filter_queryset, self.searcher.ixreader),
                limit=None,
            )
            results.fragmenter = highlight.ContextFragmenter(surround=50)
            results.formatter = HtmlFormatter(tagname="span", between=" ... ")

            if not self.first_score and len(results) > 0:
                self.first_score = results[0].score

            if self.first_score:
                results.top_n = [
                    (
                        (hit[0] / self.first_score) if self.first_score else None,
                        hit[1],
                    )
                    for hit in results.top_n
                ]

            hits_by_id = {hit["id"]: hit for hit in results}
            matching_ids = list(hits_by_id.keys())

            ordered_ids = list(
                self.filter_queryset.filter(id__in=matching_ids).values_list(
                    "id",
                    flat=True,
                ),
            )
            ordered_ids = list(dict.fromkeys(ordered_ids))

            self._manual_hits_cache = [
                hits_by_id[_id] for _id in ordered_ids if _id in hits_by_id
            ]
        return self._manual_hits_cache

    def __getitem__(self, item):
        if item.start in self.saved_results:
            return self.saved_results[item.start]

        if self._manual_sort_requested():
            manual_hits = self._manual_hits()
            start = 0 if item.start is None else item.start
            stop = item.stop
            hits = manual_hits[start:stop] if stop is not None else manual_hits[start:]
            page = ManualResultsPage(hits)
            self.saved_results[start] = page
            return page

        q, mask, suggested_correction = self._get_query()
        self.suggested_correction = suggested_correction
        sortedby, reverse = self._get_query_sortedby()

        page: ResultsPage = self.searcher.search_page(
            q,
            mask=mask,
            filter=MappedDocIdSet(self.filter_queryset, self.searcher.ixreader),
            pagenum=math.floor(item.start / self.page_size) + 1,
            pagelen=self.page_size,
            sortedby=sortedby,
            reverse=reverse,
        )
        page.results.fragmenter = highlight.ContextFragmenter(surround=50)
        page.results.formatter = HtmlFormatter(tagname="span", between=" ... ")

        if not self.first_score and len(page.results) > 0 and sortedby is None:
            self.first_score = page.results[0].score

        page.results.top_n = [
            (
                (hit[0] / self.first_score) if self.first_score else None,
                hit[1],
            )
            for hit in page.results.top_n
        ]

        self.saved_results[item.start] = page

        return page


class ManualResultsPage(list):
    def __init__(self, hits) -> None:
        super().__init__(hits)
        self.results = ManualResults(hits)


class ManualResults:
    def __init__(self, hits) -> None:
        self._docnums = [hit.docnum for hit in hits]

    def docs(self):
        return self._docnums


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
    def _get_query(self) -> tuple:
        q_str = self.query_params["query"]
        q_str = rewrite_natural_date_keywords(q_str)
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
        suggested_correction = None
        try:
            corrected = self.searcher.correct_query(q, q_str)
            if corrected.string != q_str:
                suggested_correction = corrected.string
        except Exception as e:
            logger.info(
                "Error while correcting query %s: %s",
                f"{q_str!r}",
                e,
            )

        return q, None, suggested_correction


class DelayedMoreLikeThisQuery(DelayedQuery):
    def _get_query(self) -> tuple:
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
        mask: set = {docnum}

        return q, mask, None


def autocomplete(
    ix: FileIndex,
    term: str,
    limit: int = 10,
    user: User | None = None,
) -> list:
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
        user_criterias: list = get_permissions_criterias(user)

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

        term_encoded: bytes = term.encode("UTF-8")
        if term_encoded in terms:
            terms.insert(0, terms.pop(terms.index(term_encoded)))

    return terms


def get_permissions_criterias(user: User | None = None) -> list:
    user_criterias = [query.Term("has_owner", text=False)]
    if user is not None:
        if user.is_superuser:  # superusers see all docs
            user_criterias = []
        else:
            user_criterias.append(query.Term("owner_id", user.id))
            user_criterias.append(
                query.Term("viewer_id", str(user.id)),
            )
    return user_criterias


def rewrite_natural_date_keywords(query_string: str) -> str:
    """
    Rewrites natural date keywords (e.g. added:today or added:"yesterday") to UTC range syntax for Whoosh.
    This resolves timezone issues with date parsing in Whoosh as well as adding support for more
    natural date keywords.
    """

    tz = get_current_timezone()
    local_now = now().astimezone(tz)
    today = local_now.date()

    # all supported Keywords
    pattern = r"(\b(?:added|created|modified))\s*:\s*[\"']?(today|yesterday|this month|previous month|previous week|previous quarter|this year|previous year)[\"']?"

    def repl(m):
        field = m.group(1)
        keyword = m.group(2).lower()

        match keyword:
            case "today":
                start = datetime.combine(today, time.min, tzinfo=tz)
                end = datetime.combine(today, time.max, tzinfo=tz)

            case "yesterday":
                yesterday = today - timedelta(days=1)
                start = datetime.combine(yesterday, time.min, tzinfo=tz)
                end = datetime.combine(yesterday, time.max, tzinfo=tz)

            case "this month":
                start = datetime(local_now.year, local_now.month, 1, 0, 0, 0, tzinfo=tz)
                end = start + relativedelta(months=1) - timedelta(seconds=1)

            case "previous month":
                this_month_start = datetime(
                    local_now.year,
                    local_now.month,
                    1,
                    0,
                    0,
                    0,
                    tzinfo=tz,
                )
                start = this_month_start - relativedelta(months=1)
                end = this_month_start - timedelta(seconds=1)

            case "this year":
                start = datetime(local_now.year, 1, 1, 0, 0, 0, tzinfo=tz)
                end = datetime(local_now.year, 12, 31, 23, 59, 59, tzinfo=tz)

            case "previous week":
                days_since_monday = local_now.weekday()
                this_week_start = datetime.combine(
                    today - timedelta(days=days_since_monday),
                    time.min,
                    tzinfo=tz,
                )
                start = this_week_start - timedelta(days=7)
                end = this_week_start - timedelta(seconds=1)

            case "previous quarter":
                current_quarter = (local_now.month - 1) // 3 + 1
                this_quarter_start_month = (current_quarter - 1) * 3 + 1
                this_quarter_start = datetime(
                    local_now.year,
                    this_quarter_start_month,
                    1,
                    0,
                    0,
                    0,
                    tzinfo=tz,
                )
                start = this_quarter_start - relativedelta(months=3)
                end = this_quarter_start - timedelta(seconds=1)

            case "previous year":
                start = datetime(local_now.year - 1, 1, 1, 0, 0, 0, tzinfo=tz)
                end = datetime(local_now.year - 1, 12, 31, 23, 59, 59, tzinfo=tz)

        # Convert to UTC and format
        start_str = start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        end_str = end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"{field}:[{start_str} TO {end_str}]"

    return re.sub(pattern, repl, query_string, flags=re.IGNORECASE)
