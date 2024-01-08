from dateutil.parser import isoparse
from django.test import TestCase
from whoosh import query

from documents.index import DelayedQuery
from documents.index import get_permissions_criterias
from documents.models import User


class TestDelayedQuery(TestCase):
    def setUp(self):
        super().setUp()
        # all tests run without permission criteria, so has_no_owner query will always
        # be appended.
        self.has_no_owner = query.Or([query.Term("has_owner", False)])

    def _get_testset__id__in(self, param, field):
        return (
            {f"{param}__id__in": "42,43"},
            query.And(
                [
                    query.Or(
                        [
                            query.Term(f"{field}_id", "42"),
                            query.Term(f"{field}_id", "43"),
                        ],
                    ),
                    self.has_no_owner,
                ],
            ),
        )

    def _get_testset__id__none(self, param, field):
        return (
            {f"{param}__id__none": "42,43"},
            query.And(
                [
                    query.Not(query.Term(f"{field}_id", "42")),
                    query.Not(query.Term(f"{field}_id", "43")),
                    self.has_no_owner,
                ],
            ),
        )

    def test_get_permission_criteria(self):
        # tests contains tuples of user instances and the expected filter
        tests = (
            (None, [query.Term("has_owner", False)]),
            (User(42, username="foo", is_superuser=True), []),
            (
                User(42, username="foo", is_superuser=False),
                [
                    query.Term("has_owner", False),
                    query.Term("owner_id", 42),
                    query.Term("viewer_id", "42"),
                ],
            ),
        )
        for user, expected in tests:
            self.assertEqual(get_permissions_criterias(user), expected)

    def test_no_query_filters(self):
        dq = DelayedQuery(None, {}, None, None)
        self.assertEqual(dq._get_query_filter(), self.has_no_owner)

    def test_date_query_filters(self):
        def _get_testset(param: str):
            date_str = "1970-01-01T02:44"
            date_obj = isoparse(date_str)
            return (
                (
                    {f"{param}__date__lt": date_str},
                    query.And(
                        [
                            query.DateRange(param, start=None, end=date_obj),
                            self.has_no_owner,
                        ],
                    ),
                ),
                (
                    {f"{param}__date__gt": date_str},
                    query.And(
                        [
                            query.DateRange(param, start=date_obj, end=None),
                            self.has_no_owner,
                        ],
                    ),
                ),
            )

        query_params = ["created", "added"]
        for param in query_params:
            for params, expected in _get_testset(param):
                dq = DelayedQuery(None, params, None, None)
                got = dq._get_query_filter()
                self.assertCountEqual(got, expected)

    def test_is_tagged_query_filter(self):
        tests = (
            ("True", True),
            ("true", True),
            ("1", True),
            ("False", False),
            ("false", False),
            ("0", False),
            ("foo", False),
        )
        for param, expected in tests:
            dq = DelayedQuery(None, {"is_tagged": param}, None, None)
            self.assertEqual(
                dq._get_query_filter(),
                query.And([query.Term("has_tag", expected), self.has_no_owner]),
            )

    def test_tags_query_filters(self):
        # tests contains tuples of query_parameter dics and the expected whoosh query
        param = "tags"
        field, _ = DelayedQuery.param_map[param]
        tests = (
            (
                {f"{param}__id__all": "42,43"},
                query.And(
                    [
                        query.Term(f"{field}_id", "42"),
                        query.Term(f"{field}_id", "43"),
                        self.has_no_owner,
                    ],
                ),
            ),
            # tags does not allow __id
            (
                {f"{param}__id": "42"},
                self.has_no_owner,
            ),
            # tags does not allow __isnull
            (
                {f"{param}__isnull": "true"},
                self.has_no_owner,
            ),
            self._get_testset__id__in(param, field),
            self._get_testset__id__none(param, field),
        )

        for params, expected in tests:
            dq = DelayedQuery(None, params, None, None)
            got = dq._get_query_filter()
            self.assertCountEqual(got, expected)

    def test_generic_query_filters(self):
        def _get_testset(param: str):
            field, _ = DelayedQuery.param_map[param]
            return (
                (
                    {f"{param}__id": "42"},
                    query.And(
                        [
                            query.Term(f"{field}_id", "42"),
                            self.has_no_owner,
                        ],
                    ),
                ),
                self._get_testset__id__in(param, field),
                self._get_testset__id__none(param, field),
                (
                    {f"{param}__isnull": "true"},
                    query.And(
                        [
                            query.Term(f"has_{field}", False),
                            self.has_no_owner,
                        ],
                    ),
                ),
                (
                    {f"{param}__isnull": "false"},
                    query.And(
                        [
                            query.Term(f"has_{field}", True),
                            self.has_no_owner,
                        ],
                    ),
                ),
            )

        query_params = ["correspondent", "document_type", "storage_path", "owner"]
        for param in query_params:
            for params, expected in _get_testset(param):
                dq = DelayedQuery(None, params, None, None)
                got = dq._get_query_filter()
                self.assertCountEqual(got, expected)

    def test_char_query_filter(self):
        def _get_testset(param: str):
            return (
                (
                    {f"{param}__icontains": "foo"},
                    query.And(
                        [
                            query.Term(f"{param}", "foo"),
                            self.has_no_owner,
                        ],
                    ),
                ),
                (
                    {f"{param}__istartswith": "foo"},
                    query.And(
                        [
                            query.Prefix(f"{param}", "foo"),
                            self.has_no_owner,
                        ],
                    ),
                ),
            )

        query_params = ["checksum", "original_filename"]
        for param in query_params:
            for params, expected in _get_testset(param):
                dq = DelayedQuery(None, params, None, None)
                got = dq._get_query_filter()
                self.assertCountEqual(got, expected)
