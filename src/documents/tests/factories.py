import factory

from ..models import Document, Correspondent


class CorrespondentFactory(factory.DjangoModelFactory):

    class Meta:
        model = Correspondent

    name = factory.Faker("name")


class DocumentFactory(factory.DjangoModelFactory):

    class Meta:
        model = Document
