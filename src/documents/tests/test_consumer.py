from django.test import TestCase

from ..consumer import Consumer


class TestAttachment(TestCase):

    def test_guess_attributes_from_name(self):
        consumer = Consumer()
        suffixes = ("pdf", "png", "jpg", "jpeg", "gif")
        tests = (
            {
                "path": "/path/to/Sender - Title - tag1,tag2,tag3.{}",
                "result": {
                    "sender": "Sender",
                    "title": "Title",
                    "tags": ("tag1", "tag2", "tag3")
                },
            },
            {
                "path": "/path/to/Spaced Sender - Title - tag1,tag2,tag3.{}",
                "result": {
                    "sender": "Spaced Sender",
                    "title": "Title",
                    "tags": ("tag1", "tag2", "tag3")
                },
            },
            {
                "path": "/path/to/Sender - Spaced Title - tag1,tag2,tag3.{}",
                "result": {
                    "sender": "Sender",
                    "title": "Spaced Title",
                    "tags": ("tag1", "tag2", "tag3")
                },
            },
            {
                "path": "/path/to/Spaced Sender - Spaced Title - tag1,tag2.{}",
                "result": {
                    "sender": "Spaced Sender",
                    "title": "Spaced Title",
                    "tags": ("tag1", "tag2")
                },
            },
            {
                "path": "/path/to/Dash-Sender - Title - tag1,tag2.{}",
                "result": {
                    "sender": "Dash-Sender",
                    "title": "Title",
                    "tags": ("tag1", "tag2")
                },
            },
            {
                "path": "/path/to/Sender - Dash-Title - tag1,tag2.{}",
                "result": {
                    "sender": "Sender",
                    "title": "Dash-Title",
                    "tags": ("tag1", "tag2")
                },
            },
            {
                "path": "/path/to/Dash-Sender - Dash-Title - tag1,tag2.{}",
                "result": {
                    "sender": "Dash-Sender",
                    "title": "Dash-Title",
                    "tags": ("tag1", "tag2")
                },
            },
        )
        for test in tests:
            for suffix in suffixes:
                f = test["path"].format(suffix)
                sender, title, tags, s = consumer._guess_attributes_from_name(f)
                self.assertEqual(sender.name, test["result"]["sender"])
                self.assertEqual(title, test["result"]["title"])
                self.assertEqual(tags, test["result"]["tags"])
                self.assertEqual(s, suffix)
