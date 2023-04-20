from unittest import mock

from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from django.test import TestCase
from django.test import override_settings

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

    @mock.patch("paperless.consumers.StatusConsumer._authenticated")
    async def test_auth(self, _authenticated):
        _authenticated.return_value = True

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        await communicator.disconnect()

    @mock.patch("paperless.consumers.StatusConsumer._authenticated")
    async def test_receive(self, _authenticated):
        _authenticated.return_value = True

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        message = {"task_id": "test"}

        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            "status_updates",
            {"type": "status_update", "data": message},
        )

        response = await communicator.receive_json_from()

        self.assertEqual(response, message)

        await communicator.disconnect()
