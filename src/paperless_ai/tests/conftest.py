from pathlib import Path
from unittest.mock import patch

import pytest
from llama_index.core.base.embeddings.base import BaseEmbedding
from pytest_django.fixtures import SettingsWrapper


@pytest.fixture
def temp_llm_index_dir(tmp_path: Path, settings: SettingsWrapper) -> Path:
    settings.LLM_INDEX_DIR = tmp_path
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
def mock_embed_model():
    fake = FakeEmbedding()
    with (
        patch("paperless_ai.indexing.get_embedding_model") as mock_index,
        patch(
            "paperless_ai.embedding.get_embedding_model",
        ) as mock_embedding,
    ):
        mock_index.return_value = fake
        mock_embedding.return_value = fake
        yield mock_index
