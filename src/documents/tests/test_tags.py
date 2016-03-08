from django.test import TestCase

from ..models import Tag


class TestTagMatching(TestCase):

    def test_match_all(self):

        t = Tag.objects.create(
            name="Test 0",
            match="alpha charlie gamma",
            matching_algorithm=Tag.MATCH_ALL
        )
        self.assertFalse(t.matches("I have alpha in me"))
        self.assertFalse(t.matches("I have charlie in me"))
        self.assertFalse(t.matches("I have gamma in me"))
        self.assertFalse(t.matches("I have alpha and charlie in me"))
        self.assertTrue(t.matches("I have alpha, charlie, and gamma in me"))
        self.assertFalse(t.matches("I have alphas, charlie, and gamma in me"))
        self.assertFalse(t.matches("I have alphas in me"))
        self.assertFalse(t.matches("I have bravo in me"))

        t = Tag.objects.create(
            name="Test 1",
            match="12 34 56",
            matching_algorithm=Tag.MATCH_ALL
        )
        self.assertFalse(t.matches("I have 12 in me"))
        self.assertFalse(t.matches("I have 34 in me"))
        self.assertFalse(t.matches("I have 56 in me"))
        self.assertFalse(t.matches("I have 12 and 34 in me"))
        self.assertTrue(t.matches("I have 12 34, and 56 in me"))
        self.assertFalse(t.matches("I have 120, 34, and 56 in me"))
        self.assertFalse(t.matches("I have 123456 in me"))
        self.assertFalse(t.matches("I have 01234567 in me"))

    def test_match_any(self):

        t = Tag.objects.create(
            name="Test 0",
            match="alpha charlie gamma",
            matching_algorithm=Tag.MATCH_ANY
        )

        self.assertTrue(t.matches("I have alpha in me"))
        self.assertTrue(t.matches("I have charlie in me"))
        self.assertTrue(t.matches("I have gamma in me"))
        self.assertTrue(t.matches("I have alpha and charlie in me"))
        self.assertFalse(t.matches("I have alphas in me"))
        self.assertFalse(t.matches("I have bravo in me"))

        t = Tag.objects.create(
            name="Test 1",
            match="12 34 56",
            matching_algorithm=Tag.MATCH_ANY
        )
        self.assertTrue(t.matches("I have 12 in me"))
        self.assertTrue(t.matches("I have 34 in me"))
        self.assertTrue(t.matches("I have 56 in me"))
        self.assertTrue(t.matches("I have 12 and 34 in me"))
        self.assertTrue(t.matches("I have 12 34, and 56 in me"))
        self.assertTrue(t.matches("I have 120, 34, and 560 in me"))
        self.assertFalse(t.matches("I have 120, 340, and 560 in me"))
        self.assertFalse(t.matches("I have 123456 in me"))
        self.assertFalse(t.matches("I have 01234567 in me"))

    def test_match_literal(self):

        t = Tag.objects.create(
            name="Test 0",
            match="alpha charlie gamma",
            matching_algorithm=Tag.MATCH_LITERAL
        )

        self.assertFalse(t.matches("I have alpha in me"))
        self.assertFalse(t.matches("I have charlie in me"))
        self.assertFalse(t.matches("I have gamma in me"))
        self.assertFalse(t.matches("I have alpha and charlie in me"))
        self.assertFalse(t.matches("I have alpha, charlie, and gamma in me"))
        self.assertFalse(t.matches("I have alphas, charlie, and gamma in me"))
        self.assertTrue(t.matches("I have 'alpha charlie gamma' in me"))
        self.assertFalse(t.matches("I have alphas in me"))
        self.assertFalse(t.matches("I have bravo in me"))

        t = Tag.objects.create(
            name="Test 1",
            match="12 34 56",
            matching_algorithm=Tag.MATCH_LITERAL
        )
        self.assertFalse(t.matches("I have 12 in me"))
        self.assertFalse(t.matches("I have 34 in me"))
        self.assertFalse(t.matches("I have 56 in me"))
        self.assertFalse(t.matches("I have 12 and 34 in me"))
        self.assertFalse(t.matches("I have 12 34, and 56 in me"))
        self.assertFalse(t.matches("I have 120, 34, and 560 in me"))
        self.assertFalse(t.matches("I have 120, 340, and 560 in me"))
        self.assertFalse(t.matches("I have 123456 in me"))
        self.assertFalse(t.matches("I have 01234567 in me"))
        self.assertTrue(t.matches("I have 12 34 56 in me"))

    def test_match_regex(self):

        t = Tag.objects.create(
            name="Test 0",
            match="alpha\w+gamma",
            matching_algorithm=Tag.MATCH_REGEX
        )

        self.assertFalse(t.matches("I have alpha in me"))
        self.assertFalse(t.matches("I have gamma in me"))
        self.assertFalse(t.matches("I have alpha and charlie in me"))
        self.assertTrue(t.matches("I have alpha_and_gamma in me"))
        self.assertTrue(t.matches("I have alphas_and_gamma in me"))
        self.assertFalse(t.matches("I have alpha,and,gamma in me"))
        self.assertFalse(t.matches("I have alpha and gamma in me"))
        self.assertFalse(t.matches("I have alpha, charlie, and gamma in me"))
        self.assertFalse(t.matches("I have alphas, charlie, and gamma in me"))
        self.assertFalse(t.matches("I have alphas in me"))
