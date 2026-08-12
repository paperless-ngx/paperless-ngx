import sys
import zipfile

import pytest

from documents.export import compression


class TestCompressionMethods:
    def test_choices_always_include_zstd(self) -> None:
        """
        GIVEN:
            - The compression policy module's CLI choices list
        WHEN:
            - Read on any runtime
        THEN:
            - zstd is always present; availability is checked separately so
              argparse never hides it based on the current Python version
        """
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
        """
        GIVEN:
            - A compression method name
        WHEN:
            - Looked up in COMPRESSION_METHODS
        THEN:
            - It maps to the matching zipfile compression constant
        """
        assert compression.COMPRESSION_METHODS[name] == constant

    def test_stored_and_deflated_always_available(self) -> None:
        """
        GIVEN:
            - The stored and deflated compression methods
        WHEN:
            - Checked with compression_available()
        THEN:
            - Both are always available (zlib is a hard CPython dependency)
        """
        assert compression.compression_available("stored")
        assert compression.compression_available("deflated")

    def test_zstd_availability_tracks_runtime(self) -> None:
        """
        GIVEN:
            - The zstd compression method
        WHEN:
            - Checked with compression_available() on this runtime
        THEN:
            - Availability matches whether Python is 3.14+
        """
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
            ("zstd", -22),
            ("zstd", 22),
            ("deflated", None),
            ("stored", None),
        ],
    )
    def test_valid_levels_return_none(self, method: str, level: int | None) -> None:
        """
        GIVEN:
            - A method and a level within its valid bounds (or no level)
        WHEN:
            - Checked with level_error()
        THEN:
            - No error message is returned
        """
        assert compression.level_error(method, level) is None

    @pytest.mark.parametrize(
        ("method", "level"),
        [
            ("deflated", 10),
            ("deflated", -1),
            ("bzip2", 0),
            ("bzip2", 10),
            ("zstd", -23),
            ("zstd", 23),
        ],
    )
    def test_out_of_range_levels_return_message(
        self,
        method: str,
        level: int,
    ) -> None:
        """
        GIVEN:
            - A method and a level outside its valid bounds
        WHEN:
            - Checked with level_error()
        THEN:
            - An error message naming the valid range is returned
        """
        msg: str | None = compression.level_error(method, level)
        assert msg is not None
        assert "between" in msg

    @pytest.mark.parametrize("method", ["stored", "lzma"])
    def test_level_on_levelless_method_is_rejected(self, method: str) -> None:
        """
        GIVEN:
            - A method that ignores compression level (stored, lzma)
        WHEN:
            - A level is passed to level_error() anyway
        THEN:
            - An error message noting the level has no effect is returned
        """
        msg: str | None = compression.level_error(method, 5)
        assert msg is not None
        assert "no effect" in msg


class TestCompressTypeReadable:
    @pytest.mark.parametrize("ct", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
    def test_stored_and_deflated_always_readable(self, ct: int) -> None:
        """
        GIVEN:
            - A stored or deflated compress_type id
        WHEN:
            - Checked with compress_type_readable()
        THEN:
            - It is always readable
        """
        assert compression.compress_type_readable(ct)

    def test_zstd_compress_type_readability_tracks_runtime(self) -> None:
        """
        GIVEN:
            - The zstd compress_type id (93, ZIP_ZSTANDARD)
        WHEN:
            - Checked with compress_type_readable() on this runtime
        THEN:
            - Readability matches whether Python is 3.14+
        """
        expected: bool = sys.version_info >= (3, 14)
        assert compression.compress_type_readable(93) == expected

    def test_unknown_compress_type_is_unreadable(self) -> None:
        """
        GIVEN:
            - An unrecognized compress_type id
        WHEN:
            - Checked with compress_type_readable()
        THEN:
            - It is reported as unreadable
        """
        assert not compression.compress_type_readable(9999)

    def test_unreadable_method_names_lists_methods(self) -> None:
        """
        GIVEN:
            - A set containing an unknown compress_type id
        WHEN:
            - Passed to unreadable_method_names()
        THEN:
            - It is reported generically as "method <id>"
        """
        # An unknown method id maps to no name and is reported generically.
        names: set[str] = compression.unreadable_method_names({9999})
        assert names == {"method 9999"}
