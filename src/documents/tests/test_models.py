import pytest

from documents.models import Correspondent
from documents.models import Document
from documents.tests.factories import CorrespondentFactory
from documents.tests.factories import DocumentFactory


@pytest.mark.django_db
class TestDocument:
    def test_correspondent_deletion_does_not_cascade(self) -> None:
        assert Correspondent.objects.count() == 0
        correspondent = CorrespondentFactory.create()
        assert Correspondent.objects.count() == 1

        assert Document.objects.count() == 0
        DocumentFactory.create(correspondent=correspondent)
        assert Document.objects.count() == 1
        assert Document.objects.first().correspondent is not None

        correspondent.delete()
        assert Correspondent.objects.count() == 0
        assert Document.objects.count() == 1
        assert Document.objects.first().correspondent is None
