import pytest
from pytest_django.fixtures import SettingsWrapper


@pytest.fixture(autouse=True)
def in_memory_channel_layers(settings: SettingsWrapper) -> None:
    settings.CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
