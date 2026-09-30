from pathlib import Path

from documents.parsers import ParseError
from documents.utils import run_subprocess


def extract_audio_mp3(video_path: Path, out_dir: Path) -> Path:
    out = out_dir / "audio.mp3"
    try:
        run_subprocess(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(video_path),
                "-vn",
                "-acodec",
                "libmp3lame",
                "-q:a",
                "4",
                str(out),
            ],
        )
    except Exception as e:
        raise ParseError(f"ffmpeg audio extraction failed: {e}") from e
    if not out.is_file() or out.stat().st_size == 0:
        raise ParseError("No audio track extracted from video")
    return out


def extract_thumbnail_webp(video_path: Path, out_dir: Path) -> Path:
    from PIL import Image

    png = out_dir / "thumb_frame.png"
    out = out_dir / "thumb.webp"
    last_error: Exception | None = None
    for seek in ("00:00:01", "00:00:00"):
        try:
            run_subprocess(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(video_path),
                    "-ss",
                    seek,
                    "-vframes",
                    "1",
                    str(png),
                ],
            )
            last_error = None
            break
        except Exception as e:
            last_error = e
    if last_error is not None:
        raise ParseError(f"ffmpeg thumbnail extraction failed: {last_error}") from last_error
    with Image.open(png) as im:
        im = im.convert("RGB")
        im.thumbnail((500, 500))
        im.save(out, format="WEBP")
    return out
