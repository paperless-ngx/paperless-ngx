from pathlib import Path

import httpx

from paperless.models import AIModel

# Spec limit for the extracted audio upload.
MAX_ASR_AUDIO_BYTES = 50 * 1024 * 1024


class AsrError(Exception):
    pass


class AsrClient:
    def transcribe(self, audio_path: Path, aimodel: AIModel) -> str:
        size = audio_path.stat().st_size
        if size > MAX_ASR_AUDIO_BYTES:
            raise AsrError(
                f"Audio file is {size} bytes, which exceeds the 50MB ASR upload limit",
            )

        base = aimodel.api_domain.rstrip("/")
        url = f"{base}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {aimodel.api_key}"}
        try:
            with audio_path.open("rb") as audio_file:
                files = {
                    "file": (audio_path.name, audio_file, "audio/mpeg"),
                    "model": (None, aimodel.base_model),
                }
                with httpx.Client(timeout=None) as client:
                    response = client.post(url, headers=headers, files=files)
                    response.raise_for_status()
                    data = response.json()
        except httpx.HTTPStatusError as e:
            body = ""
            if e.response is not None:
                body = (e.response.text or "").strip()
            status = e.response.status_code if e.response is not None else "error"
            detail = f"HTTP {status}"
            if body:
                detail = f"{detail}: {body}"
            raise AsrError(f"ASR request failed: {detail}") from e
        except httpx.HTTPError as e:
            raise AsrError(f"ASR request failed: {e}") from e

        text = (data.get("text") or "").strip()
        if not text:
            raise AsrError("ASR returned empty transcription")
        return text
