from pathlib import Path

import pytest
import pytest_mock
from PIL import Image

from documents.utils import QuerySetStream
from documents.utils import remove_alpha_channel


class TestQuerySetStream:
    def test_len_and_iter_delegate_to_streaming_queryset_methods(
        self,
        mocker: pytest_mock.MockerFixture,
    ) -> None:
        """
        GIVEN:
            - A mock queryset
        WHEN:
            - A QuerySetStream wrapping it is measured and iterated
        THEN:
            - len() uses count() (not a materializing len()), and iteration
              uses .iterator(chunk_size=...) (not plain iteration, which
              would materialize the whole queryset, plus any prefetch
              caches, into Django's own result cache at once)
        """
        mock_queryset = mocker.MagicMock()
        mock_queryset.count.return_value = 42
        mock_queryset.iterator.return_value = iter(["row-1", "row-2"])
        streamed = QuerySetStream(mock_queryset, chunk_size=1000)

        assert len(streamed) == 42
        assert list(streamed) == ["row-1", "row-2"]
        # count.call_count isn't asserted exactly: list()'s own size-hint
        # optimization calls len(streamed) again internally, on top of the
        # explicit len() call above -- both legitimately delegate to
        # count(), so only the delegation itself (not the call count) is
        # the thing being verified here.
        mock_queryset.count.assert_called_with()
        mock_queryset.iterator.assert_called_once_with(chunk_size=1000)


class TestRemoveAlphaChannel:
    @pytest.mark.parametrize(
        ("image_format", "mode", "expected_mode", "color", "expected_pixel"),
        [
            pytest.param(
                "PNG",
                "RGBA",
                "RGB",
                (10, 20, 30, 0),
                (10, 20, 30),
                id="png-rgba",
            ),
            pytest.param(
                "TIFF",
                "RGBA",
                "RGB",
                (10, 20, 30, 128),
                (10, 20, 30),
                id="tiff-rgba",
            ),
            pytest.param("PNG", "LA", "L", (40, 0), 40, id="png-la"),
        ],
    )
    def test_drops_alpha_and_keeps_format(
        self,
        tmp_path: Path,
        image_format: str,
        mode: str,
        expected_mode: str,
        color: tuple[int, ...],
        expected_pixel: int | tuple[int, ...],
    ) -> None:
        """
        GIVEN:
            - An image with an alpha channel
        WHEN:
            - The alpha channel is removed to a destination without an extension
        THEN:
            - The destination has the matching opaque mode, the same size and
              format, and the color values are kept rather than composited
        """
        source = tmp_path / "source"
        Image.new(mode, (8, 6), color).save(source, format=image_format)
        dest = tmp_path / "no-alpha"

        result = remove_alpha_channel(source, dest)

        assert result == dest
        with Image.open(dest) as out:
            assert out.mode == expected_mode
            assert out.size == (8, 6)
            assert out.format == image_format
            assert out.getpixel((0, 0)) == expected_pixel

    def test_keeps_every_frame_of_a_multi_page_tiff(self, tmp_path: Path) -> None:
        """
        GIVEN:
            - A multi-page TIFF where every page has an alpha channel
        WHEN:
            - The alpha channel is removed
        THEN:
            - All pages are kept and none has an alpha channel
        """
        source = tmp_path / "multi.tiff"
        first = Image.new("RGBA", (8, 6), (255, 0, 0, 50))
        rest = [Image.new("RGBA", (8, 6), (0, 255, 0, 50)) for _ in range(2)]
        first.save(source, save_all=True, append_images=rest)
        dest = tmp_path / "multi-no-alpha.tiff"

        remove_alpha_channel(source, dest)

        with Image.open(dest) as out:
            assert out.n_frames == 3
            for index in range(out.n_frames):
                out.seek(index)
                assert out.mode == "RGB"

    def test_keeps_dpi(self, tmp_path: Path) -> None:
        """
        GIVEN:
            - An alpha image with a DPI set
        WHEN:
            - The alpha channel is removed
        THEN:
            - The DPI is unchanged, since OCR scaling depends on it
        """
        source = tmp_path / "source.png"
        Image.new("RGBA", (8, 6)).save(source, dpi=(300, 300))
        dest = tmp_path / "dest.png"

        remove_alpha_channel(source, dest)

        with Image.open(dest) as out:
            assert round(out.info["dpi"][0]) == 300
