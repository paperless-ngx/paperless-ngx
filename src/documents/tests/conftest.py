import zoneinfo

import pytest
from django.contrib.auth import get_user_model
from pytest_django.fixtures import SettingsWrapper
from rest_framework.test import APIClient


@pytest.fixture()
def settings_timezone(settings: SettingsWrapper) -> zoneinfo.ZoneInfo:
    return zoneinfo.ZoneInfo(settings.TIME_ZONE)


@pytest.fixture
def rest_api_client():
    """
    The basic DRF ApiClient
    """
    yield APIClient()


@pytest.fixture
def authenticated_rest_api_client(rest_api_client: APIClient):
    """
    The basic DRF ApiClient which has been authenticated
    """
    UserModel = get_user_model()
    user = UserModel.objects.create_user(username="testuser", password="password")
    rest_api_client.force_authenticate(user=user)
    yield rest_api_client
