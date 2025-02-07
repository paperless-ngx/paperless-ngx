from unittest import mock

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TestCase
from django.test import override_settings

from documents.plugins.helpers import DocumentsStatusManager
from documents.plugins.helpers import ProgressManager
from documents.plugins.helpers import ProgressStatusOptions
from paperless.asgi import application

TEST_CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class TestWebSockets(TestCase):
    async def test_no_auth(self):
        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    @mock.patch("paperless.consumers.StatusConsumer.close")
    @mock.patch("paperless.consumers.StatusConsumer._authenticated")
    async def test_close_on_no_auth(self, _authenticated, mock_close):
        _authenticated.return_value = True

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        message = {"type": "status_update", "data": {"task_id": "test"}}

        _authenticated.return_value = False

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "status_updates",
            message,
        )
        await communicator.receive_nothing()

        mock_close.assert_called_once()
        mock_close.reset_mock()

        message = {"type": "documents_deleted", "data": {"documents": [1, 2, 3]}}

        await channel_layer.group_send(
            "status_updates",
            message,
        )
        await communicator.receive_nothing()

        mock_close.assert_called_once()

    @mock.patch("paperless.consumers.StatusConsumer._authenticated")
    async def test_auth(self, _authenticated):
        _authenticated.return_value = True

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        await communicator.disconnect()

    @mock.patch("paperless.consumers.StatusConsumer._authenticated")
    async def test_receive_status_update(self, _authenticated):
        _authenticated.return_value = True

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        message = {"type": "status_update", "data": {"task_id": "test"}}

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "status_updates",
            message,
        )

        response = await communicator.receive_json_from()

        self.assertEqual(response, message)

        await communicator.disconnect()

    @mock.patch("paperless.consumers.StatusConsumer._authenticated")
    async def test_receive_documents_deleted(self, _authenticated):
        _authenticated.return_value = True

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        message = {"type": "documents_deleted", "data": {"documents": [1, 2, 3]}}

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "status_updates",
            message,
        )

        response = await communicator.receive_json_from()

        self.assertEqual(response, message)

        await communicator.disconnect()

    @mock.patch("channels.layers.InMemoryChannelLayer.group_send")
    def test_manager_send_progress(self, mock_group_send):
        with ProgressManager(task_id="test") as manager:
            manager.send_progress(
                ProgressStatusOptions.STARTED,
                "Test message",
                1,
                10,
                extra_args={
                    "foo": "bar",
                },
            )

        message = mock_group_send.call_args[0][1]

        self.assertEqual(
            message,
            {
                "type": "status_update",
                "data": {
                    "filename": None,
                    "task_id": "test",
                    "current_progress": 1,
                    "max_progress": 10,
                    "status": ProgressStatusOptions.STARTED,
                    "message": "Test message",
                    "foo": "bar",
                },
            },
        )

    @mock.patch("channels.layers.InMemoryChannelLayer.group_send")
    def test_manager_send_documents_deleted(self, mock_group_send):
        with DocumentsStatusManager() as manager:
            manager.send_documents_deleted([1, 2, 3])

        message = mock_group_send.call_args[0][1]

        self.assertEqual(
            message,
            {
                "type": "documents_deleted",
                "data": {
                    "documents": [1, 2, 3],
                },
            },
        )
