from __future__ import annotations

import hmac
import pickle
from hashlib import sha256
from typing import Any

from django.conf import settings

HMAC_SIZE = sha256().digest_size


class SignedPickleError(ValueError):
    """Raised when a signed pickle payload cannot be authenticated."""


def _get_signing_key() -> bytes:
    return settings.SECRET_KEY.encode()


def signed_pickle_dumps(obj: object) -> bytes:
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    signature = hmac.new(_get_signing_key(), data, sha256).digest()
    return signature + data


def signed_pickle_loads(payload: bytes) -> Any:
    if len(payload) <= HMAC_SIZE:
        msg = "Signed-pickle payload too short"
        raise SignedPickleError(msg)

    signature = payload[:HMAC_SIZE]
    data = payload[HMAC_SIZE:]
    expected = hmac.new(_get_signing_key(), data, sha256).digest()
    if not hmac.compare_digest(signature, expected):
        msg = "Signed-pickle HMAC verification failed; payload may have been tampered with"
        raise SignedPickleError(msg)

    return pickle.loads(data)
