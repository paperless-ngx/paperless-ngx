from pathlib import Path

import pytest
import pytest_mock
from llama_index.core.base.embeddings.base import BaseEmbedding
from pytest_django.fixtures import SettingsWrapper


@pytest.fixture
def temp_llm_index_dir(tmp_path: Path, settings: SettingsWrapper) -> Path:
    settings.LLM_INDEX_DIR = tmp_path
    settings.LLM_INDEX_LOCK = tmp_path / "index.lock"
    return tmp_path


class FakeEmbedding(BaseEmbedding):
    async def _aget_query_embedding(self, query: str) -> list[float]:
        return [0.1] * self.get_query_embedding_dim()

    def _get_query_embedding(self, query: str) -> list[float]:
        return [0.1] * self.get_query_embedding_dim()

    def _get_text_embedding(self, text: str) -> list[float]:
        return [0.1] * self.get_query_embedding_dim()

    def get_query_embedding_dim(self) -> int:
        return 384


@pytest.fixture
def mock_embed_model(mocker: pytest_mock.MockerFixture) -> pytest_mock.MockType:
    fake = FakeEmbedding()
    mocker.patch("paperless_ai.indexing.get_embedding_model", return_value=fake)
    mocker.patch("paperless_ai.embedding.get_embedding_model", return_value=fake)
    return fake
