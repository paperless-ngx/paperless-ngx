from factory import Faker
from factory.django import DjangoModelFactory

from ..models import Document, Correspondent


class CorrespondentFactory(DjangoModelFactory):

    class Meta:
        model = Correspondent

    name = Faker("name")


class DocumentFactory(DjangoModelFactory):

    class Meta:
        model = Document
