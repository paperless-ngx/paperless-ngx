from django.test import SimpleTestCase

from documents.models import MatchingModel
from documents.serialisers import CorrespondentSerializer
from documents.serialisers import DocumentTypeSerializer
from documents.serialisers import StoragePathSerializer
from documents.serialisers import TagSerializer


class TestMatchingRegexValidation(SimpleTestCase):
    serializers = (
        CorrespondentSerializer,
        DocumentTypeSerializer,
        StoragePathSerializer,
        TagSerializer,
    )

    def assert_partial_update(self, algorithm, match, data, *, valid):
        for serializer_class in self.serializers:
            with self.subTest(serializer=serializer_class.__name__, data=data):
                instance = serializer_class.Meta.model(
                    matching_algorithm=algorithm,
                    match=match,
                )
                serializer = serializer_class(instance, data=data, partial=True)
                self.assertEqual(serializer.is_valid(), valid, serializer.errors)
                if not valid:
                    self.assertEqual(
                        serializer.errors,
                        {"match": ["Invalid regular expression, see log for details."]},
                    )

    def test_invalid_pattern_only_update(self):
        self.assert_partial_update(
            MatchingModel.MATCH_REGEX,
            "foobar",
            {"match": "["},
            valid=False,
        )

    def test_switch_to_regex_with_invalid_stored_pattern(self):
        self.assert_partial_update(
            MatchingModel.MATCH_LITERAL,
            "[",
            {"matching_algorithm": MatchingModel.MATCH_REGEX},
            valid=False,
        )

    def test_invalid_pattern_with_string_algorithm(self):
        self.assert_partial_update(
            MatchingModel.MATCH_LITERAL,
            "foobar",
            {"matching_algorithm": str(MatchingModel.MATCH_REGEX), "match": "["},
            valid=False,
        )

    def test_valid_partial_updates(self):
        regex = MatchingModel.MATCH_REGEX
        literal = MatchingModel.MATCH_LITERAL
        for algorithm, match, data in (
            (regex, "foobar", {"match": "[a-z]+"}),
            (literal, "foobar", {"matching_algorithm": regex}),
            (regex, "foobar", {"match": "[", "matching_algorithm": literal}),
            (literal, "foobar", {"match": "["}),
            (regex, "foobar", {"match": "[a-z]+", "matching_algorithm": regex}),
            (regex, "[", {"is_insensitive": False}),
        ):
            self.assert_partial_update(algorithm, match, data, valid=True)
