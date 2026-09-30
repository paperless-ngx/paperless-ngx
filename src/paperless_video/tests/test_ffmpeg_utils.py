from pathlib import Path
from unittest import mock

import pytest
from PIL import Image

from documents.parsers import ParseError
from paperless_video.ffmpeg_utils import extract_audio_mp3
from paperless_video.ffmpeg_utils import extract_thumbnail_webp


@mock.patch("paperless_video.ffmpeg_utils.run_subprocess")
def test_extract_audio_writes_path(mock_run, tmp_path):
    video = tmp_path / "a.mp4"
    video.write_bytes(b"fake")

    def _fake(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"mp3")

    mock_run.side_effect = _fake
    out = extract_audio_mp3(video, tmp_path)
    assert out.name == "audio.mp3"
    assert out.is_file()
    mock_run.assert_called_once()
    cmd = mock_run.call_args[0][0]
    assert cmd[0] == "ffmpeg"
    assert str(video) in cmd


@mock.patch("paperless_video.ffmpeg_utils.run_subprocess")
def test_extract_audio_raises_on_empty_output(mock_run, tmp_path):
    video = tmp_path / "a.mp4"
    video.write_bytes(b"fake")
    mock_run.return_value = None
    with pytest.raises(ParseError, match="No audio track"):
        extract_audio_mp3(video, tmp_path)


@mock.patch("paperless_video.ffmpeg_utils.run_subprocess")
def test_extract_audio_wraps_subprocess_error(mock_run, tmp_path):
    video = tmp_path / "a.mp4"
    video.write_bytes(b"fake")
    mock_run.side_effect = RuntimeError("ffmpeg missing")
    with pytest.raises(ParseError, match="ffmpeg audio extraction failed"):
        extract_audio_mp3(video, tmp_path)


@mock.patch("paperless_video.ffmpeg_utils.run_subprocess")
def test_extract_thumbnail_webp(mock_run, tmp_path):
    video = tmp_path / "a.mp4"
    video.write_bytes(b"fake")

    def _fake(cmd, **kwargs):
        png_path = Path(cmd[-1])
        Image.new("RGB", (800, 600), color="blue").save(png_path)

    mock_run.side_effect = _fake
    out = extract_thumbnail_webp(video, tmp_path)
    assert out.name == "thumb.webp"
    assert out.is_file()
    assert out.stat().st_size > 0


@mock.patch("paperless_video.ffmpeg_utils.run_subprocess")
def test_extract_thumbnail_retries_at_zero(mock_run, tmp_path):
    video = tmp_path / "a.mp4"
    video.write_bytes(b"fake")
    calls = []

    def _fake(cmd, **kwargs):
        calls.append(cmd)
        if "-ss" in cmd and cmd[cmd.index("-ss") + 1] == "00:00:01":
            raise RuntimeError("seek failed")
        png_path = Path(cmd[-1])
        Image.new("RGB", (100, 100), color="green").save(png_path)

    mock_run.side_effect = _fake
    out = extract_thumbnail_webp(video, tmp_path)
    assert out.name == "thumb.webp"
    assert len(calls) == 2
    assert calls[0][calls[0].index("-ss") + 1] == "00:00:01"
    assert calls[1][calls[1].index("-ss") + 1] == "00:00:00"
