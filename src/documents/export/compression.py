from __future__ import annotations

import importlib
import zipfile

# ZIP_ZSTANDARD exists only on Python 3.14+ (PEP 784). None elsewhere.
ZSTD: int | None = getattr(zipfile, "ZIP_ZSTANDARD", None)

# CLI choices are fixed across runtimes so argparse never hides zstd; runtime
# availability is enforced separately in compression_available().
COMPRESSION_CHOICES: tuple[str, ...] = (
    "stored",
    "deflated",
    "bzip2",
    "lzma",
    "zstd",
)

# Method name -> zipfile compression constant (zstd only when supported).
COMPRESSION_METHODS: dict[str, int] = {
    "stored": zipfile.ZIP_STORED,
    "deflated": zipfile.ZIP_DEFLATED,
    "bzip2": zipfile.ZIP_BZIP2,
    "lzma": zipfile.ZIP_LZMA,
}
if ZSTD is not None:
    COMPRESSION_METHODS["zstd"] = ZSTD

# Inclusive (min, max) level bounds per method; None => level not applicable.
# Verified on CPython 3.14.3.
#
# zstd's raw library bounds are (-131072, 22)
# (compression.zstd.CompressionParameter.compression_level.bounds()) — the
# minimum is an internal implementation constant (-ZSTD_TARGETLENGTH_MAX),
# not a meaningful distinct "level"; deeper negative values than -22 buy
# nothing over -22 in practice. We expose the conventional zstd CLI range
# instead of the raw library bounds.
LEVEL_BOUNDS: dict[str, tuple[int, int] | None] = {
    "stored": None,
    "deflated": (0, 9),
    "bzip2": (1, 9),
    "lzma": None,
    "zstd": (-22, 22),
}

# zipfile compress_type id -> method name.
_COMPRESS_TYPE_TO_METHOD: dict[int, str] = {
    zipfile.ZIP_STORED: "stored",
    zipfile.ZIP_DEFLATED: "deflated",
    zipfile.ZIP_BZIP2: "bzip2",
    zipfile.ZIP_LZMA: "lzma",
    93: "zstd",
}


def compression_available(method: str) -> bool:
    """Whether the running interpreter can actually use the given method."""
    if method in ("stored", "deflated"):
        # zlib is a hard CPython dependency; stored needs nothing.
        return True
    if method == "bzip2":
        return _module_importable("bz2")
    if method == "lzma":
        return _module_importable("lzma")
    if method == "zstd":
        return ZSTD is not None and _module_importable("compression.zstd")
    return False  # pragma: no cover -- method is always one of COMPRESSION_CHOICES


def _module_importable(name: str) -> bool:
    try:
        importlib.import_module(name)
    except ImportError:
        return False
    return True


def level_error(method: str, level: int | None) -> str | None:
    """Return a human message if (method, level) is invalid, else None."""
    if level is None:
        return None
    bounds = LEVEL_BOUNDS[method]
    if bounds is None:
        return f"--zip-compression-level has no effect for '{method}'"
    low, high = bounds
    if not (low <= level <= high):
        return (
            f"--zip-compression-level for '{method}' must be between {low} and {high}"
        )
    return None


def compress_type_readable(compress_type: int) -> bool:
    """Whether this interpreter can decompress an entry of the given type."""
    method = _COMPRESS_TYPE_TO_METHOD.get(compress_type)
    if method is None:
        return False
    return compression_available(method)


def unreadable_method_names(compress_types: set[int]) -> set[str]:
    """Map a set of compress_type ids to human method names for error messages."""
    names: set[str] = set()
    for ct in compress_types:
        names.add(_COMPRESS_TYPE_TO_METHOD.get(ct, f"method {ct}"))
    return names
