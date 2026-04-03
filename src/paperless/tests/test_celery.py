import hmac
import pickle
from hashlib import sha256

import pytest
from django.test import override_settings

from paperless.celery import HMAC_SIZE
from paperless.celery import signed_pickle_dumps
from paperless.celery import signed_pickle_loads


class TestSignedPickleSerializer:
    def test_roundtrip_simple_types(self):
        """Signed pickle can round-trip basic JSON-like types."""
        for obj in [42, "hello", [1, 2, 3], {"key": "value"}, None, True]:
            assert signed_pickle_loads(signed_pickle_dumps(obj)) == obj

    def test_roundtrip_complex_types(self):
        """Signed pickle can round-trip types that JSON cannot."""
        from pathlib import Path

        obj = {"path": Path("/tmp/test"), "data": {1, 2, 3}}
        result = signed_pickle_loads(signed_pickle_dumps(obj))
        assert result["path"] == Path("/tmp/test")
        assert result["data"] == {1, 2, 3}

    def test_tampered_data_rejected(self):
        """Flipping a byte in the data portion causes HMAC failure."""
        payload = signed_pickle_dumps({"task": "test"})
        tampered = bytearray(payload)
        tampered[-1] ^= 0xFF
        with pytest.raises(ValueError, match="HMAC verification failed"):
            signed_pickle_loads(bytes(tampered))

    def test_tampered_signature_rejected(self):
        """Flipping a byte in the signature portion causes HMAC failure."""
        payload = signed_pickle_dumps({"task": "test"})
        tampered = bytearray(payload)
        tampered[0] ^= 0xFF
        with pytest.raises(ValueError, match="HMAC verification failed"):
            signed_pickle_loads(bytes(tampered))

    def test_truncated_payload_rejected(self):
        """A payload shorter than HMAC_SIZE is rejected."""
        with pytest.raises(ValueError, match="too short"):
            signed_pickle_loads(b"\x00" * (HMAC_SIZE - 1))

    def test_empty_payload_rejected(self):
        with pytest.raises(ValueError, match="too short"):
            signed_pickle_loads(b"")

    @override_settings(SECRET_KEY="different-secret-key")
    def test_wrong_secret_key_rejected(self):
        """A message signed with one key cannot be loaded with another."""
        original_key = b"test-secret-key-do-not-use-in-production"
        obj = {"task": "test"}
        data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
        signature = hmac.new(original_key, data, sha256).digest()
        payload = signature + data
        with pytest.raises(ValueError, match="HMAC verification failed"):
            signed_pickle_loads(payload)

    def test_forged_pickle_rejected(self):
        """A raw pickle payload (no signature) is rejected."""
        raw_pickle = pickle.dumps({"task": "test"})
        # Raw pickle won't have a valid HMAC prefix
        with pytest.raises(ValueError, match="HMAC verification failed"):
            signed_pickle_loads(b"\x00" * HMAC_SIZE + raw_pickle)
