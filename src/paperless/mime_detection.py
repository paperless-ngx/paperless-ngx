from pathlib import Path

from magika import Magika

_magika = Magika()


def from_file(path: str | Path) -> str:
    return _magika.identify_path(path).output.mime_type


def from_buffer(data: bytes) -> str:
    return _magika.identify_bytes(data).output.mime_type
