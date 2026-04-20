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
from documents.models import PaperlessTask
from documents.models import StoragePath
from documents.models import Tag


class CorrespondentFactory(DjangoModelFactory):
    class Meta:
        model = Correspondent

    name = factory.Sequence(lambda n: f"{factory.Faker('company')} {n}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class DocumentTypeFactory(DjangoModelFactory):
    class Meta:
        model = DocumentType

    name = factory.Sequence(lambda n: f"{factory.Faker('bs')} {n}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"{factory.Faker('word')} {n}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE
    is_inbox_tag = False


class StoragePathFactory(DjangoModelFactory):
    class Meta:
        model = StoragePath

    name = factory.Sequence(
        lambda n: f"{factory.Faker('file_path', depth=2, extension='')} {n}",
    )
    path = factory.LazyAttribute(lambda o: f"{o.name}/{{title}}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class DocumentFactory(DjangoModelFactory):
    class Meta:
        model = Document

    title = factory.Faker("sentence", nb_words=4)
    checksum = factory.Faker("sha256")
    content = factory.Faker("paragraph")
    correspondent = None
    document_type = None
    storage_path = None


class PaperlessTaskFactory(DjangoModelFactory):
    class Meta:
        model = PaperlessTask

    task_id = factory.Faker("uuid4")
    task_type = PaperlessTask.TaskType.CONSUME_FILE
    trigger_source = PaperlessTask.TriggerSource.WEB_UI
    status = PaperlessTask.Status.PENDING
    input_data = factory.LazyFunction(dict)
    result_data = None
    acknowledged = False
