import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from pytest_mock import MockerFixture

from documents.plugins.helpers import DocumentsStatusManager
from documents.plugins.helpers import ProgressManager
from documents.plugins.helpers import ProgressStatusOptions
from paperless.asgi import application


class TestWebSockets:
    @pytest.fixture(autouse=True)
    def anyio_backend(self) -> str:
        return "asyncio"

    @pytest.mark.anyio
    async def test_no_auth(self) -> None:
        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, _ = await communicator.connect()
        assert not connected
        await communicator.disconnect()

    @pytest.mark.anyio
    async def test_close_on_no_auth(self, mocker: MockerFixture) -> None:
        mock_auth = mocker.patch(
            "paperless.consumers.StatusConsumer._authenticated",
            return_value=True,
        )
        mock_close = mocker.patch(
            "paperless.consumers.StatusConsumer.close",
            new_callable=mocker.AsyncMock,
        )

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, _ = await communicator.connect()
        assert connected

        mock_auth.return_value = False
        channel_layer = get_channel_layer()
        assert channel_layer is not None

        await channel_layer.group_send(
            "status_updates",
            {"type": "status_update", "data": {"task_id": "test"}},
        )
        await communicator.receive_nothing()
        mock_close.assert_awaited_once()
        mock_close.reset_mock()

        await channel_layer.group_send(
            "status_updates",
            {
                "type": "document_updated",
                "data": {"document_id": 10, "modified": "2026-02-17T00:00:00Z"},
            },
        )
        await communicator.receive_nothing()
        mock_close.assert_awaited_once()
        mock_close.reset_mock()

        await channel_layer.group_send(
            "status_updates",
            {"type": "documents_deleted", "data": {"documents": [1, 2, 3]}},
        )
        await communicator.receive_nothing()
        mock_close.assert_awaited_once()

    @pytest.mark.anyio
    async def test_auth(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "paperless.consumers.StatusConsumer._authenticated",
            return_value=True,
        )

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, _ = await communicator.connect()
        assert connected

        await communicator.disconnect()

    @pytest.mark.anyio
    async def test_receive_status_update(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "paperless.consumers.StatusConsumer._authenticated",
            return_value=True,
        )

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, _ = await communicator.connect()
        assert connected

        message = {"type": "status_update", "data": {"task_id": "test"}}
        channel_layer = get_channel_layer()
        assert channel_layer is not None
        await channel_layer.group_send("status_updates", message)

        assert await communicator.receive_json_from() == message

        await communicator.disconnect()

    @pytest.mark.anyio
    async def test_status_update_check_perms(self, mocker: MockerFixture) -> None:
        user = mocker.MagicMock()
        user.is_authenticated = True
        user.is_superuser = False
        user.id = 1

        communicator = WebsocketCommunicator(application, "/ws/status/")
        communicator.scope["user"] = user  # type: ignore[typeddict-unknown-key]
        connected, _ = await communicator.connect()
        assert connected

        channel_layer = get_channel_layer()
        assert channel_layer is not None

        # Message received as owner
        message = {"type": "status_update", "data": {"task_id": "test", "owner_id": 1}}
        await channel_layer.group_send("status_updates", message)
        assert await communicator.receive_json_from() == message

        # Message received via group membership
        user.groups.filter.return_value.aexists = mocker.AsyncMock(return_value=True)
        message = {
            "type": "status_update",
            "data": {"task_id": "test", "owner_id": 2, "groups_can_view": [1]},
        }
        await channel_layer.group_send("status_updates", message)
        assert await communicator.receive_json_from() == message

        # Message not received for different owner with no group match
        user.groups.filter.return_value.aexists = mocker.AsyncMock(return_value=False)
        message = {"type": "status_update", "data": {"task_id": "test", "owner_id": 2}}
        await channel_layer.group_send("status_updates", message)
        assert await communicator.receive_nothing()

        await communicator.disconnect()

    @pytest.mark.anyio
    async def test_receive_documents_deleted(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "paperless.consumers.StatusConsumer._authenticated",
            return_value=True,
        )

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, _ = await communicator.connect()
        assert connected

        message = {"type": "documents_deleted", "data": {"documents": [1, 2, 3]}}
        channel_layer = get_channel_layer()
        assert channel_layer is not None
        await channel_layer.group_send("status_updates", message)

        assert await communicator.receive_json_from() == message

        await communicator.disconnect()

    @pytest.mark.anyio
    async def test_receive_document_updated(self, mocker: MockerFixture) -> None:
        mocker.patch(
            "paperless.consumers.StatusConsumer._authenticated",
            return_value=True,
        )
        mocker.patch(
            "paperless.consumers.StatusConsumer._can_view",
            return_value=True,
        )

        communicator = WebsocketCommunicator(application, "/ws/status/")
        connected, _ = await communicator.connect()
        assert connected

        message = {
            "type": "document_updated",
            "data": {
                "document_id": 10,
                "modified": "2026-02-17T00:00:00Z",
                "owner_id": 1,
                "users_can_view": [1],
                "groups_can_view": [],
            },
        }
        channel_layer = get_channel_layer()
        assert channel_layer is not None
        await channel_layer.group_send("status_updates", message)

        assert await communicator.receive_json_from() == message

        await communicator.disconnect()

    def test_manager_send_progress(self, mocker: MockerFixture) -> None:
        mock_group_send = mocker.patch(
            "channels.layers.InMemoryChannelLayer.group_send",
        )

        with ProgressManager(task_id="test") as manager:
            manager.send_progress(
                ProgressStatusOptions.STARTED,
                "Test message",
                1,
                10,
                document_id=42,
                owner_id=1,
                users_can_view=[2, 3],
                groups_can_view=[4],
            )

        assert mock_group_send.call_args[0][1] == {
            "type": "status_update",
            "data": {
                "filename": None,
                "task_id": "test",
                "current_progress": 1,
                "max_progress": 10,
                "status": ProgressStatusOptions.STARTED,
                "message": "Test message",
                "document_id": 42,
                "owner_id": 1,
                "users_can_view": [2, 3],
                "groups_can_view": [4],
            },
        }

    def test_manager_send_documents_deleted(self, mocker: MockerFixture) -> None:
        mock_group_send = mocker.patch(
            "channels.layers.InMemoryChannelLayer.group_send",
        )

        with DocumentsStatusManager() as manager:
            manager.send_documents_deleted([1, 2, 3])

        assert mock_group_send.call_args[0][1] == {
            "type": "documents_deleted",
            "data": {
                "documents": [1, 2, 3],
            },
        }
