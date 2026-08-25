from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from documents.data_models import DocumentMetadataOverrides
from documents.models import CustomField
from documents.models import CustomFieldInstance
from documents.tests.factories import DocumentFactory
from documents.tests.utils import DirectoriesMixin


class TestDocumentMetadataOverridesFromDocument(DirectoriesMixin, TestCase):
    def test_from_document_batches_custom_field_lookup_after_refresh_from_db(
        self,
    ) -> None:
        """
        GIVEN:
            - A document has several custom field values
            - The document instance has just been refreshed from the database,
              which drops any prefetched related objects (as
              send_websocket_document_updated does before building overrides)
        WHEN:
            - DocumentMetadataOverrides.from_document() reads the document's
              custom field values
        THEN:
            - The referenced CustomField objects are resolved with a single
              query, not one query per custom field
        """
        doc = DocumentFactory(mime_type="application/pdf")
        for i in range(5):
            CustomFieldInstance.objects.create(
                document=doc,
                field=CustomField.objects.create(
                    name=f"Test Custom Field {i}",
                    data_type=CustomField.FieldDataType.STRING,
                ),
                value_text="value",
            )

        doc.refresh_from_db()

        with CaptureQueriesContext(connection) as ctx:
            overrides = DocumentMetadataOverrides.from_document(doc)

        self.assertEqual(len(overrides.custom_fields), 5)
        unbatched_field_lookups = [
            query
            for query in ctx.captured_queries
            if 'FROM "documents_customfield" WHERE "documents_customfield"."id"'
            in query["sql"]
        ]
        self.assertEqual(
            unbatched_field_lookups,
            [],
            "Expected CustomField data to come from the CustomFieldInstance "
            "join, not a separate per-instance lookup, "
            f"got: {unbatched_field_lookups}",
        )
