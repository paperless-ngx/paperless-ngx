import sys
import zipfile

import pytest

from documents.export import compression


class TestCompressionMethods:
    def test_choices_always_include_zstd(self) -> None:
        # zstd is offered regardless of runtime; availability is checked separately
        assert compression.COMPRESSION_CHOICES == (
            "stored",
            "deflated",
            "bzip2",
            "lzma",
            "zstd",
        )

    @pytest.mark.parametrize(
        ("name", "constant"),
        [
            ("stored", zipfile.ZIP_STORED),
            ("deflated", zipfile.ZIP_DEFLATED),
            ("bzip2", zipfile.ZIP_BZIP2),
            ("lzma", zipfile.ZIP_LZMA),
        ],
    )
    def test_method_maps_to_zipfile_constant(self, name: str, constant: int) -> None:
        assert compression.COMPRESSION_METHODS[name] == constant

    def test_stored_and_deflated_always_available(self) -> None:
        assert compression.compression_available("stored")
        assert compression.compression_available("deflated")

    def test_zstd_availability_tracks_runtime(self) -> None:
        expected: bool = sys.version_info >= (3, 14)
        assert compression.compression_available("zstd") == expected


class TestLevelError:
    @pytest.mark.parametrize(
        ("method", "level"),
        [
            ("deflated", 0),
            ("deflated", 9),
            ("bzip2", 1),
            ("bzip2", 9),
            ("deflated", None),
            ("stored", None),
        ],
    )
    def test_valid_levels_return_none(self, method: str, level: int | None) -> None:
        assert compression.level_error(method, level) is None

    @pytest.mark.parametrize(
        ("method", "level"),
        [
            ("deflated", 10),
            ("deflated", -1),
            ("bzip2", 0),
            ("bzip2", 10),
        ],
    )
    def test_out_of_range_levels_return_message(
        self,
        method: str,
        level: int,
    ) -> None:
        msg: str | None = compression.level_error(method, level)
        assert msg is not None
        assert "between" in msg

    @pytest.mark.parametrize("method", ["stored", "lzma"])
    def test_level_on_levelless_method_is_rejected(self, method: str) -> None:
        msg: str | None = compression.level_error(method, 5)
        assert msg is not None
        assert "no effect" in msg


class TestCompressTypeReadable:
    @pytest.mark.parametrize("ct", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
    def test_stored_and_deflated_always_readable(self, ct: int) -> None:
        assert compression.compress_type_readable(ct)

    def test_zstd_compress_type_readability_tracks_runtime(self) -> None:
        # 93 = ZIP_ZSTANDARD; 20 = legacy zstd method id (read-only)
        expected: bool = sys.version_info >= (3, 14)
        assert compression.compress_type_readable(93) == expected
        assert compression.compress_type_readable(20) == expected

    def test_unknown_compress_type_is_unreadable(self) -> None:
        assert not compression.compress_type_readable(9999)

    def test_unreadable_method_names_lists_methods(self) -> None:
        # An unknown method id maps to no name and is reported generically.
        names: set[str] = compression.unreadable_method_names({9999})
        assert names == {"method 9999"}
