from documents.caching import StoredLRUCache
from paperless.signed_pickle import HMAC_SIZE
from paperless.signed_pickle import signed_pickle_dumps
from paperless.signed_pickle import signed_pickle_loads


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
    assert signed_pickle_loads(data) == {"x": "X", "y": "Y"}


def test_stored_lru_cache_rejects_tampered_data(mocker) -> None:
    serialized_data = bytearray(signed_pickle_dumps({"x": "X"}))
    serialized_data[HMAC_SIZE] ^= 0xFF
    mock_backend = mocker.Mock()
    mock_backend.get.return_value = bytes(serialized_data)
    cache = StoredLRUCache("test_key", backend=mock_backend)

    cache.load()

    assert cache.get("x") is None
