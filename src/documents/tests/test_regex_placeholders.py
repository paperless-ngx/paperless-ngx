"""
Tests for regex-based placeholder transformations in workflows.
"""
import logging
from datetime import datetime
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from documents.templating.workflows import parse_w_workflow_placeholders


class TestRegexPlaceholders(TestCase):
    """Test regex-based placeholder transformations."""

    def setUp(self):
        """Set up test data."""
        self.test_correspondent = "Sparkasse Bank"
        self.test_doc_type = "Bank Statement"
        self.test_owner = "testuser"
        self.test_added = timezone.localtime(timezone.now())
        self.test_original_filename = "Sparkasse_12_2023_statement.pdf"
        self.test_filename = "processed_document.pdf"
        self.test_created = self.test_added.date()
        self.test_title = "Test Document"
        self.test_url = "http://localhost/doc/123"

    def test_backward_compatibility_simple_placeholders(self):
        """Test that existing simple placeholders still work."""
        template = "Doc from {correspondent} type {document_type}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
            self.test_created,
            self.test_title,
            self.test_url,
        )
        expected = f"Doc from {self.test_correspondent} type {self.test_doc_type}"
        self.assertEqual(result, expected)

    def test_regex_placeholder_basic_substitution(self):
        """Test basic regex substitution functionality."""
        template = r"{original_filename:s/Sparkasse_/Bank_/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, "Bank_12_2023_statement")

    def test_regex_placeholder_with_capture_groups(self):
        """Test regex substitution with capture groups."""
        template = r"{original_filename:s/Sparkasse_(\d+)_(\d+)_/Statement $2-$1 /}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, "Statement 2023-12 statement")

    def test_regex_placeholder_case_insensitive_flag(self):
        """Test regex substitution with case insensitive flag."""
        template = r"{original_filename:s/sparkasse/Bank/i}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, "Bank_12_2023_statement")

    def test_regex_placeholder_dotall_flag(self):
        """Test regex substitution with dotall flag."""
        multiline_title = "Test\nDocument\nTitle"
        template = r"{doc_title:s/Test.*Title/New Title/s}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
            self.test_created,
            multiline_title,
            self.test_url,
        )
        self.assertEqual(result, "New Title")

    def test_regex_placeholder_combined_flags(self):
        """Test regex substitution with multiple flags."""
        template = r"{correspondent:s/sparkasse/Bank/i}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, "Bank Bank")

    def test_regex_placeholder_no_match(self):
        """Test regex substitution when pattern doesn't match."""
        template = r"{original_filename:s/NonExistent/Replacement/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        # Should return original value since pattern doesn't match
        self.assertEqual(result, "Sparkasse_12_2023_statement")

    def test_regex_placeholder_invalid_regex_pattern(self):
        """Test handling of invalid regex patterns."""
        template = r"{original_filename:s/[invalid(/Replacement/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        # Should fall back to original value
        self.assertEqual(result, "Sparkasse_12_2023_statement")

    def test_regex_placeholder_nonexistent_field(self):
        """Test regex substitution on nonexistent field."""
        template = r"{nonexistent_field:s/test/replacement/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        # Should return empty string for nonexistent field
        self.assertEqual(result, "")

    def test_regex_placeholder_empty_field(self):
        """Test regex substitution on empty field."""
        template = r"{correspondent:s/test/replacement/}"
        result = parse_w_workflow_placeholders(
            template,
            "",  # Empty correspondent
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        # Should handle empty string gracefully
        self.assertEqual(result, "")

    def test_regex_placeholder_no_trailing_slash(self):
        """Test regex substitution without trailing slash for convenience."""
        template = r"{original_filename:s/Sparkasse_/Bank_}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, "Bank_12_2023_statement")

    def test_regex_placeholder_malformed_syntax(self):
        """Test handling of malformed regex syntax."""
        # Missing closing slash
        template = r"{original_filename:s/pattern/replacement}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        # Should fall back to simple field replacement
        self.assertEqual(result, "Sparkasse_12_2023_statement")

    def test_regex_placeholder_mixed_with_simple_placeholders(self):
        """Test mixing regex and simple placeholders in the same template."""
        template = r"{correspondent} - {original_filename:s/Sparkasse_(\d+)/Statement $1/} - {document_type}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        expected = f"{self.test_correspondent} - Statement 12_2023_statement - {self.test_doc_type}"
        self.assertEqual(result, expected)

    def test_regex_placeholder_complex_example_from_problem_statement(self):
        """Test the specific example from the problem statement."""
        # The example: {filename:s/^+?Sparkasse_(\d\d)$/Kontoauszug $1}
        # Note: The original example has an error (^+?) - fixing to be a valid regex
        template = r"{original_filename:s/^.*Sparkasse_(\d\d).*$/Kontoauszug $1/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, "Kontoauszug 12")

    def test_regex_placeholder_non_string_field_handling(self):
        """Test handling of non-string fields in regex transformations."""
        # Mock a situation where a field might be non-string
        template = "{created_year:s/2023/2024/}"
        with mock.patch(
            "documents.templating.workflows.Path"
        ) as mock_path:
            mock_path.return_value.stem = "test"
            result = parse_w_workflow_placeholders(
                template,
                self.test_correspondent,
                self.test_doc_type,
                self.test_owner,
                self.test_added,
                self.test_original_filename,
                self.test_filename,
                self.test_created,
            )
            # Should convert to string and apply transformation
            expected_year = self.test_created.strftime("%Y")
            if expected_year == "2023":
                self.assertEqual(result, "2024")
            else:
                self.assertEqual(result, expected_year)

    def test_regex_placeholder_special_characters_in_replacement(self):
        """Test regex substitution with special characters in replacement."""
        template = r"{original_filename:s/Sparkasse/Bank & Trust/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, "Bank & Trust_12_2023_statement")

    def test_regex_placeholder_escape_sequences(self):
        """Test regex substitution with escape sequences."""
        template = r"{original_filename:s/Sparkasse_(\d+)/Bank_$1/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, r"Bank_12_2023_statement")

    def test_legacy_malformed_placeholder_handling(self):
        """Test that malformed placeholders are handled gracefully (backward compatibility)."""
        # This test ensures the existing error handling from the original code still works
        template = "Doc {created_year]"  # Missing opening brace - from existing test
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
            self.test_created,
        )
        # Should fall back to original text
        self.assertEqual(result, "Doc {created_year]")

    def test_regex_placeholder_edge_case_empty_pattern(self):
        """Test edge case with empty regex pattern."""
        template = r"{original_filename:s//replacement/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        # Empty pattern should match everywhere and replace with replacement
        # This might insert replacement between every character
        self.assertIn("replacement", result)

    def test_regex_placeholder_edge_case_empty_replacement(self):
        """Test edge case with empty replacement string."""
        template = r"{original_filename:s/Sparkasse_//}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        # Should remove "Sparkasse_" from the filename
        self.assertEqual(result, "12_2023_statement")

    def test_original_filename_full_placeholder(self):
        """Test the new original_filename_full placeholder with whole filename including extension."""
        template = r"{original_filename_full}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, self.test_original_filename)

    def test_content_placeholder(self):
        """Test the new content placeholder with document content."""
        test_content = "This is the extracted content of the PDF document."
        template = r"{content}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
            content=test_content,
        )
        self.assertEqual(result, test_content)

    def test_content_placeholder_with_regex(self):
        """Test regex transformation on content placeholder."""
        test_content = "Account Number: 123456789 Statement Date: 2023-12"
        template = r"{content:s/Account Number: (\d+)/Konto $1/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
            content=test_content,
        )
        self.assertEqual(result, "Konto 123456789 Statement Date: 2023-12")

    def test_original_filename_full_with_regex(self):
        """Test regex transformation on original_filename_full placeholder."""
        template = r"{original_filename_full:s/\.pdf$/\.backup/}"
        result = parse_w_workflow_placeholders(
            template,
            self.test_correspondent,
            self.test_doc_type,
            self.test_owner,
            self.test_added,
            self.test_original_filename,
            self.test_filename,
        )
        self.assertEqual(result, "Sparkasse_12_2023_statement.backup")