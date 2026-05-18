from pathlib import Path

import pytest
from pytest_django.fixtures import SettingsWrapper


@pytest.fixture
def temp_llm_index_dir(tmp_path: Path, settings: SettingsWrapper):
    settings.LLM_INDEX_DIR = tmp_path
    return tmp_path
