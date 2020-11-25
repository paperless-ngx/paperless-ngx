import os
from unittest import mock, skipIf

from django.test import TestCase

from ..parsers import strip_excess_whitespace


class TestOCR(TestCase):

    text_cases = [
        ("simple     string", "simple string"),
        (
            "simple    newline\n   testing string",
            "simple newline\ntesting string"
        ),
        (
            "utf-8   строка с пробелами в конце  ",
            "utf-8 строка с пробелами в конце"
        )
    ]

    def test_strip_excess_whitespace(self):
        for source, result in self.text_cases:
            actual_result = strip_excess_whitespace(source)
            self.assertEqual(
                result,
                actual_result,
                "strip_exceess_whitespace({}) != '{}', but '{}'".format(
                    source,
                    result,
                    actual_result
                )
            )
