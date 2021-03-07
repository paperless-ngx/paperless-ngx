import logging
import os
from contextlib import contextmanager

import math
from django.conf import settings
from whoosh import highlight, classify, query
from whoosh.fields import Schema, TEXT, NUMERIC, KEYWORD, DATETIME
from whoosh.highlight import Formatter, get_text
from whoosh.index import create_in, exists_in, open_dir
from whoosh.qparser import MultifieldParser
from whoosh.qparser.dateparse import DateParserPlugin
from whoosh.searching import ResultsPage
from whoosh.writing import AsyncWriter

from documents.models import Document

logger = logging.getLogger("paperless.index")


class JsonFormatter(Formatter):
    def __init__(self):
        self.seen = {}

    def format_token(self, text, token, replace=False):
        ttext = self._text(get_text(text, token, replace))
        return {'text': ttext, 'highlight': 'true'}

    def format_fragment(self, fragment, replace=False):
        output = []
        index = fragment.startchar
        text = fragment.text
        amend_token = None
        for t in fragment.matches:
            if t.startchar is None:
                continue
            if t.startchar < index:
                continue
            if t.startchar > index:
                text_inbetween = text[index:t.startchar]
                if amend_token and t.startchar - index < 10:
                    amend_token['text'] += text_inbetween
                else:
                    output.append({'text': text_inbetween,
                                   'highlight': False})
                    amend_token = None
            token = self.format_token(text, t, replace)
            if amend_token:
                amend_token['text'] += token['text']
            else:
                output.append(token)
                amend_token = token
            index = t.endchar
        if index < fragment.endchar:
            output.append({'text': text[index:fragment.endchar],
                           'highlight': False})
        return output

    def format(self, fragments, replace=False):
        output = []
        for fragment in fragments:
            output.append(self.format_fragment(fragment, replace=replace))
        return output


def get_schema():
    return Schema(
        id=NUMERIC(stored=True, unique=True, numtype=int),
        title=TEXT(stored=True),
        content=TEXT(),
        correspondent=TEXT(stored=True),
        correspondent_id=NUMERIC(stored=True, numtype=int),
        tag=KEYWORD(stored=True, commas=True, scorable=True, lowercase=True),
        type=TEXT(stored=True),
        created=DATETIME(stored=True, sortable=True),
        modified=DATETIME(stored=True, sortable=True),
        added=DATETIME(stored=True, sortable=True),
    )


def open_index(recreate=False):
    try:
        if exists_in(settings.INDEX_DIR) and not recreate:
            return open_dir(settings.INDEX_DIR, schema=get_schema())
    except Exception:
        logger.exception(f"Error while opening the index, recreating.")

    if not os.path.isdir(settings.INDEX_DIR):
        os.makedirs(settings.INDEX_DIR, exist_ok=True)
    return create_in(settings.INDEX_DIR, get_schema())


@contextmanager
def open_index_writer(ix=None, optimize=False):
    if ix:
        writer = AsyncWriter(ix)
    else:
        writer = AsyncWriter(open_index())

    try:
        yield writer
    except Exception as e:
        logger.exception(str(e))
        writer.cancel()
    finally:
        writer.commit(optimize=optimize)


def update_document(writer, doc):
    tags = ",".join([t.name for t in doc.tags.all()])
    writer.update_document(
        id=doc.pk,
        title=doc.title,
        content=doc.content,
        correspondent=doc.correspondent.name if doc.correspondent else None,
        correspondent_id=doc.correspondent.id if doc.correspondent else None,
        tag=tags if tags else None,
        type=doc.document_type.name if doc.document_type else None,
        created=doc.created,
        added=doc.added,
        modified=doc.modified,
    )


def remove_document(writer, doc):
    remove_document_by_id(writer, doc.pk)


def remove_document_by_id(writer, doc_id):
    writer.delete_by_term('id', doc_id)


def add_or_update_document(document):
    with open_index_writer() as writer:
        update_document(writer, document)


def remove_document_from_index(document):
    with open_index_writer() as writer:
        remove_document(writer, document)


@contextmanager
def query_page(ix, page, querystring, more_like_doc_id, more_like_doc_content):
    searcher = ix.searcher()
    try:
        if querystring:
            qp = MultifieldParser(
                ["content", "title", "correspondent", "tag", "type"],
                ix.schema)
            qp.add_plugin(DateParserPlugin())
            str_q = qp.parse(querystring)
            corrected = searcher.correct_query(str_q, querystring)
        else:
            str_q = None
            corrected = None

        if more_like_doc_id:
            docnum = searcher.document_number(id=more_like_doc_id)
            kts = searcher.key_terms_from_text(
                'content', more_like_doc_content, numterms=20,
                model=classify.Bo1Model, normalize=False)
            more_like_q = query.Or(
                [query.Term('content', word, boost=weight)
                 for word, weight in kts])
            result_page = searcher.search_page(
                more_like_q, page, filter=str_q, mask={docnum})
        elif str_q:
            result_page = searcher.search_page(str_q, page)
        else:
            raise ValueError(
                "Either querystring or more_like_doc_id is required."
            )

        result_page.results.fragmenter = highlight.ContextFragmenter(
            surround=50)
        result_page.results.formatter = JsonFormatter()

        if corrected and corrected.query != str_q:
            corrected_query = corrected.string
        else:
            corrected_query = None

        yield result_page, corrected_query
    finally:
        searcher.close()


class DelayedQuery:

    @property
    def _query(self):
        if 'query' in self.query_params:
            qp = MultifieldParser(
                ["content", "title", "correspondent", "tag", "type"],
                self.ix.schema)
            qp.add_plugin(DateParserPlugin())
            q = qp.parse(self.query_params['query'])
        elif 'more_like_id' in self.query_params:
            more_like_doc_id = int(self.query_params['more_like_id'])
            content = Document.objects.get(id=more_like_doc_id).content

            docnum = self.searcher.document_number(id=more_like_doc_id)
            kts = self.searcher.key_terms_from_text(
                'content', content, numterms=20,
                model=classify.Bo1Model, normalize=False)
            q = query.Or(
                [query.Term('content', word, boost=weight)
                 for word, weight in kts])
        else:
            raise ValueError(
                "Either query or more_like_id is required."
            )
        return q

    @property
    def _query_filter(self):
        criterias = []
        for k, v in self.query_params.items():
            if k == 'correspondent__id':
                criterias.append(query.Term('correspondent_id', v))
        if len(criterias) > 0:
            return query.And(criterias)
        else:
            return None

    def __init__(self, ix, searcher, query_params, page_size):
        self.ix = ix
        self.searcher = searcher
        self.query_params = query_params
        self.page_size = page_size

    def __len__(self):
        results = self.searcher.search(self._query, limit=1, filter=self._query_filter)
        return len(results)
        #return 1000

    def __getitem__(self, item):
        page: ResultsPage = self.searcher.search_page(
            self._query,
            filter=self._query_filter,
            pagenum=math.floor(item.start / self.page_size) + 1,
            pagelen=self.page_size
        )
        return page


def autocomplete(ix, term, limit=10):
    with ix.reader() as reader:
        terms = []
        for (score, t) in reader.most_distinctive_terms(
                "content", number=limit, prefix=term.lower()):
            terms.append(t)
        return terms
