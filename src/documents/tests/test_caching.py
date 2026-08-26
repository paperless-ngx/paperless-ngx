import pickle
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from threading import Lock

from documents.caching import StoredLRUCache
from documents.caching import retrieve_llm_suggestions


def test_lru_cache_entries() -> None:
    CACHE_TTL = 1
    # LRU cache with a capacity of 2 elements
    cache = StoredLRUCache("test_lru_cache_key", 2, backend_ttl=CACHE_TTL)
    cache.set(1, 1)
    cache.set(2, 2)
    assert cache.get(2) == 2
    assert cache.get(1) == 1

    # The oldest entry (2) should be removed
    cache.set(3, 3)
    assert cache.get(3) == 3
    assert not cache.get(2)
    assert cache.get(1) == 1

    # Save the cache, restore it and check it overwrites the current cache in memory
    cache.save()
    cache.set(4, 4)
    assert not cache.get(3)
    cache.load()
    assert not cache.get(4)
    assert cache.get(3) == 3
    assert cache.get(1) == 1


def test_stored_lru_cache_key_ttl(mocker) -> None:
    mock_backend = mocker.Mock()
    cache = StoredLRUCache("test_key", backend=mock_backend, backend_ttl=321)

    # Simulate storing values
    cache.set("x", "X")
    cache.set("y", "Y")
    cache.save()

    # Assert backend.set was called with pickled data, key and TTL
    mock_backend.set.assert_called_once()
    key, data, timeout = mock_backend.set.call_args[0]
    assert key == "test_key"
    assert timeout == 321
    assert pickle.loads(data) == {"x": "X", "y": "Y"}


def test_llm_suggestions_are_generated_once_for_concurrent_requests(mocker) -> None:
    generation_started = Event()
    finish_generation = Event()
    waiter_started = Event()
    call_lock = Lock()
    calls = 0
    suggestions = {"title": "Generated once"}
    document = mocker.Mock(pk=42)
    user = mocker.Mock()

    def generate(*args) -> dict:
        nonlocal calls
        with call_lock:
            calls += 1
        generation_started.set()
        assert finish_generation.wait(timeout=2)
        return suggestions

    def wait_for_generation(_interval: float) -> None:
        waiter_started.set()
        assert finish_generation.wait(timeout=2)

    mock_get_classification = mocker.patch(
        "paperless_ai.ai_classifier.get_ai_document_classification",
        side_effect=generate,
    )
    mocker.patch("documents.caching.time.sleep", side_effect=wait_for_generation)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            retrieve_llm_suggestions,
            document,
            user,
            None,
            backend="ollama:model",
            lock_timeout=10,
        )
        assert generation_started.wait(timeout=2)
        second = executor.submit(
            retrieve_llm_suggestions,
            document,
            user,
            None,
            backend="ollama:model",
            lock_timeout=10,
        )
        assert waiter_started.wait(timeout=2)
        finish_generation.set()

        assert first.result(timeout=2) == suggestions
        assert second.result(timeout=2) == suggestions

    assert calls == 1
    mock_get_classification.assert_called_once_with(document, user, None)
