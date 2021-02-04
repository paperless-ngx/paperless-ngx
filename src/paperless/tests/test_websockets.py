from unittest import mock

from channels.testing import WebsocketCommunicator
from django.test import TestCase

from paperless.asgi import application


class TestWebSockets(TestCase):

    @mock.patch("paperless.consumers.async_to_sync")
    async def test_no_auth(self, async_to_sync):
        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertFalse(connected)
        await communicator.disconnect()

    @mock.patch("paperless.consumers.async_to_sync")
    @mock.patch("paperless.consumers.StatusConsumer._authenticated")
    async def test_auth(self, _authenticated, async_to_sync):
        _authenticated.return_value = True

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, subprotocol = await communicator.connect()
        self.assertTrue(connected)

        await communicator.disconnect()
