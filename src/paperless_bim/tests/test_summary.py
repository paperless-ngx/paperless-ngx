"""
Unit tests for paperless_bim.summary. We only verify that the call to the
default LLM is wired up correctly; the actual LLM response is mocked.
"""
from unittest import mock

from django.test import TestCase

from documents.parsers import ParseError
from paperless.models import AIModel
from paperless.models import Prompt
from paperless_bim.summary import DEFAULT_BIM_IFC_SUMMARY_PROMPT
from paperless_bim.summary import summarize_ifc_text


class TestSummarizeIfc(TestCase):
    def setUp(self):
        self.llm = AIModel.objects.create(
            name="default-llm",
            supplier="openai",
            model_type="llm",
            base_model="gpt-4o-mini",
            api_domain="https://api.example.com/v1",
            api_key="sk-test",
            is_default=True,
        )

    def _patched_post(self, content):
        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": content}}],
        }
        return mock_response

    def test_summarize_uses_prompt_table_when_present(self):
        Prompt.objects.create(
            type="BIM_IFC_SUMMARY",
            content="Custom BIM prompt",
        )
        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = self._patched_post(" 摘要正文 ")

            summary = summarize_ifc_text("[PROJECT] x")

        self.assertEqual(summary, "摘要正文")
        kwargs = instance.post.call_args.kwargs
        self.assertEqual(kwargs["json"]["model"], "gpt-4o-mini")
        self.assertEqual(kwargs["json"]["stream"], False)
        self.assertEqual(kwargs["json"]["thinking"], {"type": "disabled"})
        self.assertEqual(kwargs["json"]["extra_body"], {"enable_thinking": False})
        sys_msg = kwargs["json"]["messages"][0]
        self.assertEqual(sys_msg["role"], "system")
        self.assertEqual(sys_msg["content"], "Custom BIM prompt")
        user_msg = kwargs["json"]["messages"][1]
        self.assertEqual(user_msg["role"], "user")
        self.assertEqual(user_msg["content"], "[PROJECT] x")

    def test_summarize_falls_back_to_default_prompt(self):
        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = self._patched_post("OK")

            summarize_ifc_text("anything")

        sys_msg = instance.post.call_args.kwargs["json"]["messages"][0]
        self.assertEqual(sys_msg["content"], DEFAULT_BIM_IFC_SUMMARY_PROMPT)

    def test_summarize_raises_when_no_default_llm(self):
        self.llm.delete()
        with self.assertRaises(ParseError):
            summarize_ifc_text("anything")

    def test_summarize_raises_on_empty_llm_response(self):
        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = self._patched_post("   ")
            with self.assertRaises(ParseError):
                summarize_ifc_text("anything")
