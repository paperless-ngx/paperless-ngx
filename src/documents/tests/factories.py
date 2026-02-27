"""
Factory-boy factories for documents app models.
"""

from __future__ import annotations

import factory
from factory.django import DjangoModelFactory

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import StoragePath
from documents.models import Tag


class CorrespondentFactory(DjangoModelFactory):
    class Meta:
        model = Correspondent

    name = factory.Faker("company")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class DocumentTypeFactory(DjangoModelFactory):
    class Meta:
        model = DocumentType

    name = factory.Faker("bs")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Faker("word")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE
    is_inbox_tag = False


class StoragePathFactory(DjangoModelFactory):
    class Meta:
        model = StoragePath

    name = factory.Faker("file_path", depth=2, extension="")
    path = factory.LazyAttribute(lambda o: f"{o.name}/{{title}}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class DocumentFactory(DjangoModelFactory):
    class Meta:
        model = Document

    title = factory.Faker("sentence", nb_words=4)
    checksum = factory.Faker("md5")
    content = factory.Faker("paragraph")
    correspondent = None
    document_type = None
    storage_path = None
