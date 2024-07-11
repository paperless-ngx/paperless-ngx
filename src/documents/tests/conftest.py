import zoneinfo

import pytest
from pytest_django.fixtures import SettingsWrapper


@pytest.fixture()
def settings_timezone(settings: SettingsWrapper) -> zoneinfo.ZoneInfo:
    return zoneinfo.ZoneInfo(settings.TIME_ZONE)
