import logging

from django.db import models
from django.dispatch import receiver
from whoosh.fields import Schema, TEXT, NUMERIC
from whoosh.highlight import Formatter, get_text
from whoosh.index import create_in, exists_in, open_dir
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
        content=TEXT()
    )


def open_index(recreate=False):
    if exists_in(settings.INDEX_DIR) and not recreate:
        return open_dir(settings.INDEX_DIR)
    else:
        return create_in(settings.INDEX_DIR, get_schema())


def update_document(writer, doc):
    logging.getLogger(__name__).debug("Updating index with document{}".format(str(doc)))
    writer.update_document(
        id=doc.pk,
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
    logging.getLogger(__name__).debug("Removing document {} from index".format(str(instance)))
    ix = open_index()
    with AsyncWriter(ix) as writer:
        writer.delete_by_term('id', instance.pk)


def autocomplete(ix, term, limit=10):
    with ix.reader() as reader:
        terms = []
        for (score, t) in reader.most_distinctive_terms("content", limit, term.lower()):
            terms.append(t)
        return terms
