from __future__ import annotations

import hmac
import pickle
from hashlib import sha256
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings

if TYPE_CHECKING:
    from pathlib import Path
    from types import TracebackType
    from typing import BinaryIO
    from typing import Self

HMAC_SIZE = sha256().digest_size


class SignedPickleError(ValueError):
    """Raised when a signed pickle payload cannot be authenticated."""


def new_mac() -> hmac.HMAC:
    """
    A new HMAC-SHA256 keyed with the SECRET_KEY, for signing incrementally.
    """
    return hmac.new(settings.SECRET_KEY.encode(), digestmod=sha256)


def compute_signature(data: bytes | memoryview) -> bytes:
    mac = new_mac()
    mac.update(data)
    return mac.digest()


def verify_signed(payload: bytes | memoryview) -> memoryview:
    """
    Verifies a payload made of an HMAC signature followed by the data, returning
    a view of the data.

    The data is sliced through a memoryview, so a (potentially multi-GB) payload
    is not copied. The view is only returned once the whole payload has been
    verified, and callers should unpickle from it rather than from the source,
    so what is loaded is exactly what was checked.
    """
    if len(payload) <= HMAC_SIZE:
        msg = "Signed-pickle payload too short"
        raise SignedPickleError(msg)

    view = memoryview(payload)
    signature = view[:HMAC_SIZE]
    data = view[HMAC_SIZE:]
    if not hmac.compare_digest(signature, compute_signature(data)):
        msg = "Signed-pickle HMAC verification failed; payload may have been tampered with"
        raise SignedPickleError(msg)

    return data


def signed_pickle_dumps(obj: object) -> bytes:
    data = pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL)
    return compute_signature(data) + data


def signed_pickle_loads(payload: bytes) -> Any:
    return pickle.loads(verify_signed(payload))


class SignedFileWriter:
    """
    Atomically writes a file made of an HMAC signature followed by the data,
    signing the data as it streams to disk rather than holding it in memory.
    The result can be read back with verify_signed.

    The signature is only known once everything is written, so its space is
    reserved at the start of the file and filled in on exit. The target is only
    replaced once the file is complete; on error the partial file is removed.
    """

    def __init__(self, target: Path) -> None:
        self._target = target
        self._temp = target.with_name(f"{target.name}.part")
        self._mac = new_mac()
        self._file: BinaryIO

    def __enter__(self) -> Self:
        self._file = self._temp.open("wb")
        self._file.write(bytes(HMAC_SIZE))
        return self

    def write(self, data: bytes | memoryview) -> int:
        self._mac.update(data)
        return self._file.write(data)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            with self._file:
                if exc_type is None:
                    self._file.seek(0)
                    self._file.write(self._mac.digest())
            if exc_type is None:
                self._temp.rename(self._target)
        finally:
            # A no-op after a successful rename, otherwise removes the partial file
            self._temp.unlink(missing_ok=True)
