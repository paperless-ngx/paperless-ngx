from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import call
from unittest.mock import patch

import pytest
import pytest_mock
from django.conf import settings

from paperless.models import LLMEmbeddingBackend
from paperless_ai import indexing
from paperless_ai.embedding import get_embedding_model
from paperless_ai.tests.conftest import FakeEmbedding
from paperless_testing.factories import DocumentFactory

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CACHE = str(settings.DATA_DIR / "hf_cache")


@pytest.fixture
def hf_config() -> MagicMock:
    config = MagicMock()
    config.llm_embedding_backend = LLMEmbeddingBackend.HUGGINGFACE
    config.llm_embedding_model = MODEL
    return config


@pytest.fixture
def hf_embedding(mocker: pytest_mock.MockerFixture) -> MagicMock:
    return mocker.patch("llama_index.embeddings.huggingface.HuggingFaceEmbedding")


class TestHuggingFaceLocalFirst:
    def test_uses_cached_model_without_hub(
        self,
        hf_config: MagicMock,
        hf_embedding: MagicMock,
    ) -> None:
        model = get_embedding_model(hf_config)

        hf_embedding.assert_called_once_with(
            model_name=MODEL,
            cache_folder=CACHE,
            local_files_only=True,
        )
        assert model is hf_embedding.return_value

    def test_downloads_when_not_cached(
        self,
        hf_config: MagicMock,
        hf_embedding: MagicMock,
    ) -> None:
        downloaded = MagicMock()
        hf_embedding.side_effect = [OSError("not cached"), downloaded]

        model = get_embedding_model(hf_config)

        assert hf_embedding.call_args_list == [
            call(model_name=MODEL, cache_folder=CACHE, local_files_only=True),
            call(model_name=MODEL, cache_folder=CACHE),
        ]
        assert model is downloaded

    def test_refresh_checks_the_hub(
        self,
        hf_config: MagicMock,
        hf_embedding: MagicMock,
    ) -> None:
        get_embedding_model(hf_config, refresh=True)

        hf_embedding.assert_called_once_with(model_name=MODEL, cache_folder=CACHE)


@pytest.mark.django_db
class TestIndexUpdateRefresh:
    @pytest.fixture(autouse=True)
    def _index_inputs(self, temp_llm_index_dir: Path) -> None:
        DocumentFactory.create()

    def _update(self, mock_embed_model: FakeEmbedding, *, rebuild: bool) -> MagicMock:
        mock_config = MagicMock()
        mock_config.llm_embedding_chunk_size = 512
        with (
            patch("paperless_ai.indexing.AIConfig", return_value=mock_config),
            patch("paperless_ai.indexing.build_document_node", return_value=[]),
            patch(
                "paperless_ai.indexing.get_embedding_model",
                return_value=mock_embed_model,
            ) as get_model,
        ):
            indexing.update_llm_index(rebuild=rebuild)
        get_model.assert_called_once()
        return get_model

    def test_rebuild_refreshes(self, mock_embed_model: FakeEmbedding) -> None:
        get_model = self._update(mock_embed_model, rebuild=True)

        assert get_model.call_args.kwargs == {"refresh": True}

    def test_incremental_update_stays_local(
        self,
        mock_embed_model: FakeEmbedding,
    ) -> None:
        get_model = self._update(mock_embed_model, rebuild=False)

        assert get_model.call_args.kwargs == {"refresh": False}
