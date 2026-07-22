"""
Factory-boy factories for documents app models.
"""

from __future__ import annotations

import factory
from django.contrib.auth import get_user_model
from factory.django import DjangoModelFactory

from documents.models import Correspondent
from documents.models import Document
from documents.models import DocumentType
from documents.models import MatchingModel
from documents.models import PaperlessTask
from documents.models import StoragePath
from documents.models import Tag

UserModelT = get_user_model()


class CorrespondentFactory(DjangoModelFactory[Correspondent]):
    class Meta:
        model = Correspondent

    name = factory.Sequence(lambda n: f"{factory.Faker('company')} {n}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class DocumentTypeFactory(DjangoModelFactory[DocumentType]):
    class Meta:
        model = DocumentType

    name = factory.Sequence(lambda n: f"{factory.Faker('bs')} {n}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class TagFactory(DjangoModelFactory[Tag]):
    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"{factory.Faker('word')} {n}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE
    is_inbox_tag = False


class StoragePathFactory(DjangoModelFactory[StoragePath]):
    class Meta:
        model = StoragePath

    name = factory.Sequence(
        lambda n: f"{factory.Faker('file_path', depth=2, extension='')} {n}",
    )
    path = factory.LazyAttribute(lambda o: f"{o.name}/{{title}}")
    match = ""
    matching_algorithm = MatchingModel.MATCH_NONE


class DocumentFactory(DjangoModelFactory[Document]):
    class Meta:
        model = Document

    title = factory.Faker("sentence", nb_words=4)
    checksum = factory.Faker("sha256")
    content = factory.Faker("paragraph")
    correspondent = None
    document_type = None
    storage_path = None


class UserFactory(DjangoModelFactory[UserModelT]):
    class Meta:
        model = UserModelT

    username = factory.Sequence(lambda n: f"user{n}")
    is_staff = False
    is_superuser = False
    password = factory.django.Password("test")

    class Params:
        superuser = factory.Trait(is_staff=True, is_superuser=True)
        staff = factory.Trait(is_staff=True)


class PaperlessTaskFactory(DjangoModelFactory[PaperlessTask]):
    class Meta:
        model = PaperlessTask

    task_id = factory.Faker("uuid4")
    task_type = PaperlessTask.TaskType.CONSUME_FILE
    trigger_source = PaperlessTask.TriggerSource.WEB_UI
    status = PaperlessTask.Status.PENDING
    input_data = factory.LazyFunction(dict)
    result_data = None
    acknowledged = False
