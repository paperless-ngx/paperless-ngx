import pytest
from pytest_httpx import HTTPXMock


class HttpxMockMixin:
    @pytest.fixture(autouse=True)
    def httpx_mock_auto(self, httpx_mock: HTTPXMock):
        """
        Workaround for allowing use of a fixture with unittest style testing
        """
        self.httpx_mock = httpx_mock
