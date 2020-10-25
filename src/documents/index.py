from collections import Iterable

from django.db import models
from django.dispatch import receiver
from whoosh.fields import Schema, TEXT, NUMERIC, DATETIME, KEYWORD
from whoosh.highlight import Formatter, get_text
from whoosh.index import create_in, exists_in, open_dir
from whoosh.qparser import QueryParser
from whoosh.query import terms
from whoosh.writing import AsyncWriter

from documents.models import Document
from paperless import settings


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
        content=TEXT(stored=True)
    )


def open_index(recreate=False):
    if exists_in(settings.INDEX_DIR) and not recreate:
        return open_dir(settings.INDEX_DIR)
    else:
        return create_in(settings.INDEX_DIR, get_schema())


def update_document(writer, doc):
    writer.update_document(
        id=doc.id,
        title=doc.title,
        content=doc.content
    )

@receiver(models.signals.post_save, sender=Document)
def add_document_to_index(sender, instance, **kwargs):
    ix = open_index()
    with AsyncWriter(ix) as writer:
        update_document(writer, instance)


@receiver(models.signals.post_delete, sender=Document)
def remove_document_from_index(sender, instance, **kwargs):
    ix = open_index()
    with AsyncWriter(ix) as writer:
        writer.delete_by_term('id', instance.id)


def query_index(ix, querystr):
    with ix.searcher() as searcher:
        query = QueryParser("content", ix.schema, termclass=terms.FuzzyTerm).parse(querystr)
        results = searcher.search(query)
        results.formatter = JsonFormatter()
        results.fragmenter.surround = 50

        return [
            {'id': r['id'],
             'highlights': r.highlights("content"),
             'score': r.score,
             'title': r['title']
             } for r in results]
