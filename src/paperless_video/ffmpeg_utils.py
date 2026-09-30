import subprocess
from pathlib import Path

from documents.parsers import ParseError
from documents.utils import run_subprocess

_NO_AUDIO_HINTS = (
    "does not contain any stream",
    "matches no streams",
    "no audio",
    "output file is empty",
)


def _process_output(exc: BaseException) -> str:
    parts: list[str] = []
    for blob in (getattr(exc, "stderr", None), getattr(exc, "stdout", None)):
        if not blob:
            continue
        if isinstance(blob, bytes):
            text = blob.decode("utf8", errors="ignore").strip()
        else:
            text = str(blob).strip()
        if text:
            parts.append(text)
    return "\n".join(parts)


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
    except subprocess.CalledProcessError as e:
        detail = _process_output(e)
        lowered = detail.lower()
        if not detail or any(hint in lowered for hint in _NO_AUDIO_HINTS):
            message = "No audio track extracted from video"
            if detail:
                message = f"{message}: {detail}"
            raise ParseError(message) from e
        raise ParseError(f"ffmpeg audio extraction failed: {detail}") from e
    except Exception as e:
        detail = _process_output(e) or str(e)
        raise ParseError(f"ffmpeg audio extraction failed: {detail}") from e
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
        raise ParseError(
            f"ffmpeg thumbnail extraction failed: {last_error}",
        ) from last_error
    try:
        with Image.open(png) as im:
            im = im.convert("RGB")
            im.thumbnail((500, 500))
            im.save(out, format="WEBP")
    except Exception as e:
        raise ParseError(f"thumbnail image conversion failed: {e}") from e
    return out
