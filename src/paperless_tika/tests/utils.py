import pytest
from pytest_httpx import HTTPXMock


# TODO: Remove this class once paperless_mail is updated as well
class HttpxMockMixin:
    @pytest.fixture(autouse=True)
    def _httpx_mock_auto(self, httpx_mock: HTTPXMock):
        """
        Workaround for allowing use of a fixture with unittest style testing
        """
        self.httpx_mock = httpx_mock
