from factory import Faker
from factory.django import DjangoModelFactory

from documents.models import Correspondent
from documents.models import Document


class CorrespondentFactory(DjangoModelFactory):
    class Meta:
        model = Correspondent

    name = Faker("name")


class DocumentFactory(DjangoModelFactory):
    class Meta:
        model = Document
