import logging
import os
from contextlib import contextmanager

from django.conf import settings
from whoosh import highlight
from whoosh.fields import Schema, TEXT, NUMERIC
from whoosh.highlight import Formatter, get_text
from whoosh.index import create_in, exists_in, open_dir
from whoosh.qparser import MultifieldParser
from whoosh.writing import AsyncWriter


logger = logging.getLogger(__name__)


class JsonFormatter(Formatter):
    def __init__(self):
        self.seen = {}

    def format_token(self, text, token, replace=False):
        seen = self.seen
        ttext = self._text(get_text(text, token, replace))
        if ttext in seen:
            termnum = seen[ttext]
        else:
            termnum = len(seen)
            seen[ttext] = termnum

        return {'text': ttext, 'term': termnum}

    def format_fragment(self, fragment, replace=False):
        output = []
        index = fragment.startchar
        text = fragment.text

        for t in fragment.matches:
            if t.startchar is None:
                continue
            if t.startchar < index:
                continue
            if t.startchar > index:
                output.append({'text': text[index:t.startchar]})
            output.append(self.format_token(text, t, replace))
            index = t.endchar
        if index < fragment.endchar:
            output.append({'text': text[index:fragment.endchar]})
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
        correspondent=TEXT(stored=True)
    )


def open_index(recreate=False):
    if exists_in(settings.INDEX_DIR) and not recreate:
        return open_dir(settings.INDEX_DIR)
    else:
        # TODO: this is not thread safe. If 2 instances try to create the index
        #  at the same time, this fails. This currently prevents parallel
        #  tests.
        if not os.path.isdir(settings.INDEX_DIR):
            os.makedirs(settings.INDEX_DIR, exist_ok=True)
        return create_in(settings.INDEX_DIR, get_schema())


def update_document(writer, doc):
    logger.debug("Indexing {}...".format(doc))
    writer.update_document(
        id=doc.pk,
        title=doc.title,
        content=doc.content,
        correspondent=doc.correspondent.name if doc.correspondent else None
    )


def remove_document(writer, doc):
    logger.debug("Removing {} from index...".format(doc))
    writer.delete_by_term('id', doc.pk)


def add_or_update_document(document):
    ix = open_index()
    with AsyncWriter(ix) as writer:
        update_document(writer, document)


def remove_document_from_index(document):
    ix = open_index()
    with AsyncWriter(ix) as writer:
        remove_document(writer, document)


@contextmanager
def query_page(ix, query, page):
    searcher = ix.searcher()
    try:
        query_parser = MultifieldParser(["content", "title", "correspondent"],
                                        ix.schema).parse(query)
        result_page = searcher.search_page(query_parser, page)
        result_page.results.fragmenter = highlight.ContextFragmenter(
            surround=50)
        result_page.results.formatter = JsonFormatter()
        yield result_page
    finally:
        searcher.close()


def autocomplete(ix, term, limit=10):
    with ix.reader() as reader:
        terms = []
        for (score, t) in reader.most_distinctive_terms(
                "content", number=limit, prefix=term.lower()):
            terms.append(t)
        return terms
