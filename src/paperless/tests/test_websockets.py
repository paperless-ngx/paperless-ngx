from unittest import mock

from channels.testing import WebsocketCommunicator
from django.test import TestCase

from paperless.asgi import application


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
