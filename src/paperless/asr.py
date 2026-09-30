from pathlib import Path

import httpx

from paperless.models import AIModel


class AsrError(Exception):
    pass


class AsrClient:
    def transcribe(self, audio_path: Path, aimodel: AIModel) -> str:
        base = aimodel.api_domain.rstrip("/")
        url = f"{base}/audio/transcriptions"
        headers = {"Authorization": f"Bearer {aimodel.api_key}"}
        with audio_path.open("rb") as audio_file:
            files = {
                "file": (audio_path.name, audio_file, "audio/mpeg"),
                "model": (None, aimodel.base_model),
            }
            with httpx.Client(timeout=None) as client:
                response = client.post(url, headers=headers, files=files)
                response.raise_for_status()
                data = response.json()
        text = (data.get("text") or "").strip()
        if not text:
            raise AsrError("ASR returned empty transcription")
        return text
