from unittest import mock

from django.test import TestCase

from documents.parsers import ParseError
from paperless.models import AIModel
from paperless.models import Prompt
from paperless_video.summary import DEFAULT_VIDEO_SUMMARY_PROMPT
from paperless_video.summary import summarize_transcript


class TestSummarizeTranscript(TestCase):
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

    def test_summarize_posts_chat_completion(self):
        Prompt.objects.create(
            type="VIDEO_ASR_SUMMARY",
            content="Custom summary prompt",
        )
        transcript = "这是一段很长的转写文本。"

        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "  简短摘要  "}}],
        }

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = mock_response
            summary = summarize_transcript(transcript)

        self.assertEqual(summary, "简短摘要")
        args, kwargs = instance.post.call_args
        self.assertEqual(
            args[0],
            "https://api.example.com/v1/chat/completions",
        )
        self.assertEqual(kwargs["json"]["stream"], False)
        self.assertEqual(kwargs["json"]["model"], "gpt-4o-mini")
        self.assertEqual(
            kwargs["json"]["messages"][0]["content"],
            "Custom summary prompt",
        )
        self.assertEqual(kwargs["json"]["messages"][1]["content"], transcript)
        self.assertEqual(
            kwargs["headers"]["Authorization"],
            "Bearer sk-test",
        )

    def test_summarize_uses_default_prompt_when_empty(self):
        Prompt.objects.create(type="VIDEO_ASR_SUMMARY", content="   ")

        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "摘要"}}],
        }

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = mock_response
            summarize_transcript("转写")

        system = instance.post.call_args.kwargs["json"]["messages"][0]["content"]
        self.assertEqual(system, DEFAULT_VIDEO_SUMMARY_PROMPT)

    def test_summarize_raises_without_default_llm(self):
        self.llm.delete()
        with self.assertRaises(ParseError) as ctx:
            summarize_transcript("转写")
        self.assertIn("No default LLM", str(ctx.exception))

    def test_summarize_raises_on_empty_response(self):
        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": ""}}],
        }

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = mock_response
            with self.assertRaises(ParseError) as ctx:
                summarize_transcript("转写")
        self.assertIn("empty video summary", str(ctx.exception))

    def test_summarize_raises_on_http_error(self):
        import httpx

        mock_response = mock.Mock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error",
            request=mock.Mock(),
            response=mock.Mock(),
        )

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = mock_response
            with self.assertRaises(httpx.HTTPStatusError):
                summarize_transcript("转写")
