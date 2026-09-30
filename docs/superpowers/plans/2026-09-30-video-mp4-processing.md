# Video MP4 Processing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support MP4 uploads that extract audio, call a generic ASR API, optionally LLM-summarize with a configurable prompt, write assembled text into `Document.content`, and generate a frame thumbnail—while simplifying AIModel settings and adding ASR model type.

**Architecture:** New always-on `paperless_video` parser app registers `video/mp4`. Parser uses ffmpeg for audio/thumbnail, `AsrClient` for OpenAI-compatible `/audio/transcriptions`, default LLM + `VIDEO_ASR_SUMMARY` prompt for summary, and `ApplicationConfiguration.video_content_mode` to choose transcript / summary / both. AIModel UI becomes free-text supplier/base_model/api_domain with type `asr`.

**Tech Stack:** Django, httpx, ffmpeg, Angular settings UI, existing `AIModel` / `Prompt` / `ApplicationConfiguration`

**Spec:** `docs/superpowers/specs/2026-09-30-video-mp4-processing-design.md`

## Global Constraints

- Phase 1: **MP4 / `video/mp4` only**
- Title = filename; tags unchanged (upload association)
- No in-app player, no ASR chunking, no PDF archive for video
- ASR: generic `POST {api_domain}/audio/transcriptions` (SiliconFlow-compatible)
- Content modes: `transcript` | `summary` | `both` (default `both`)
- Prompt type code: `VIDEO_ASR_SUMMARY`; UI label: **视频语音摘要提示词**
- `both` layout uses `【摘要】` / `【转写】` separators
- Audio extract format: **mp3**
- Remove advanced params from AIModel UI (keep DB `params` field unused by UI)
- `supplier` becomes free text (no enum validation)

---

## File Structure

| Path | Responsibility |
|------|----------------|
| `src/paperless/models.py` | `VideoContentModeChoices`, `video_content_mode` on `ApplicationConfiguration`; loosen `AIModel.supplier` |
| `src/paperless/migrations/0008_*.py` | Migration for above |
| `src/paperless/asr.py` | `AsrClient.transcribe(audio_path, aimodel) -> str` |
| `src/paperless/config.py` | Optional read helper for `video_content_mode` (or read model directly in parser) |
| `src/paperless_video/` | New parser app |
| `src/paperless_video/ffmpeg_utils.py` | Extract audio + thumbnail frame |
| `src/paperless_video/content.py` | Assemble content string by mode |
| `src/paperless_video/summary.py` | Call default LLM with `VIDEO_ASR_SUMMARY` |
| `src/paperless_video/parsers.py` | `VideoDocumentParser` |
| `src/paperless_video/signals.py` | MIME declaration |
| `src/paperless_video/apps.py` | Connect signal |
| `src/paperless/settings.py` | Add app to `INSTALLED_APPS` |
| `pyproject.toml` | Add `src/paperless_video/tests/` to `testpaths` |
| `Dockerfile` | Add `ffmpeg` to `RUNTIME_PACKAGES` |
| `src-ui/.../ai-model-settings/*` | Manual fields, drop advanced, add `asr` |
| `src-ui/.../prompt-settings/*` | Video speech summary prompt |
| `src-ui/.../paperless-config.ts` | Video content mode select |

---

### Task 1: Loosen AIModel.supplier + add video_content_mode

**Files:**
- Modify: `src/paperless/models.py`
- Create: `src/paperless/migrations/0008_aimodel_supplier_free_and_video_content_mode.py` (name may vary; use `makemigrations`)
- Test: `src/paperless/tests/test_aimodel_supplier.py` (new)

**Interfaces:**
- Produces: `VideoContentModeChoices` with values `transcript`, `summary`, `both`
- Produces: `ApplicationConfiguration.video_content_mode` default `"both"`
- Produces: `AIModel.supplier` as unconstrained `CharField(max_length=64)`

- [ ] **Step 1: Write failing tests**

Create `src/paperless/tests/test_aimodel_supplier.py`:

```python
from django.test import TestCase

from paperless.models import AIModel
from paperless.models import ApplicationConfiguration
from paperless.models import VideoContentModeChoices


class TestAIModelSupplierFreeText(TestCase):
    def test_allows_siliconflow_supplier(self):
        m = AIModel.objects.create(
            name="sf-asr",
            supplier="siliconflow",
            model_type="asr",
            base_model="FunAudioLLM/SenseVoiceSmall",
            api_domain="https://api.siliconflow.cn/v1",
            api_key="test-key",
            is_default=True,
        )
        self.assertEqual(m.supplier, "siliconflow")


class TestVideoContentMode(TestCase):
    def test_default_is_both(self):
        cfg = ApplicationConfiguration.objects.create()
        # singleton may already exist in tests — fetch first
        cfg = ApplicationConfiguration.objects.first()
        # After migration, field default should be both when unset/new
        self.assertIn(
            cfg.video_content_mode,
            {None, VideoContentModeChoices.BOTH, "both"},
        )
```

Adjust the default assertion to match how other ApplicationConfiguration fields are tested in `src/documents/tests/test_api_app_config.py` (singleton already exists; after migration default `"both"`).

Preferred assertion after migration:

```python
cfg = ApplicationConfiguration.objects.first()
self.assertEqual(cfg.video_content_mode, VideoContentModeChoices.BOTH)
```

- [ ] **Step 2: Run tests — expect fail**

```bash
cd c:\Users\Administrator\Desktop\aigc\paperless-ngx-ai
uv run pytest src/paperless/tests/test_aimodel_supplier.py -v --no-cov -n0
```

Expected: FAIL (import / field missing)

- [ ] **Step 3: Implement model changes**

In `src/paperless/models.py`, near other Choices classes:

```python
class VideoContentModeChoices(models.TextChoices):
    TRANSCRIPT = ("transcript", _("transcript"))
    SUMMARY = ("summary", _("summary"))
    BOTH = ("both", _("both"))
```

On `ApplicationConfiguration`, after `vlm_analysis_enabled`:

```python
video_content_mode = models.CharField(
    verbose_name=_("Video content mode"),
    max_length=16,
    choices=VideoContentModeChoices.choices,
    default=VideoContentModeChoices.BOTH,
    null=True,
    blank=True,
)
```

Change `AIModel.supplier` to drop `choices=SupplierChoices.choices` (keep `SupplierChoices` class only if still referenced elsewhere; otherwise remove). Field:

```python
supplier = models.CharField(
    verbose_name=_("supplier"),
    max_length=64,
)
```

- [ ] **Step 4: Make migration**

```bash
uv run python src/manage.py makemigrations paperless --name aimodel_supplier_free_and_video_content_mode
```

- [ ] **Step 5: Run tests — expect pass**

```bash
uv run pytest src/paperless/tests/test_aimodel_supplier.py -v --no-cov -n0
```

- [ ] **Step 6: Commit**

```bash
git add src/paperless/models.py src/paperless/migrations/ src/paperless/tests/test_aimodel_supplier.py
git commit -m "feat: free-text AIModel supplier and video_content_mode"
```

---

### Task 2: Frontend AIModel settings — manual fields, ASR type, drop advanced

**Files:**
- Modify: `src-ui/src/app/components/admin/settings/ai-model-settings/ai-model-settings.component.ts`
- Modify: `src-ui/src/app/components/admin/settings/ai-model-settings/ai-model-settings.component.html`
- Modify: `src-ui/src/app/data/ai-model.ts` (optional: keep `supplierList` unused or delete dead helpers later — YAGNI: stop importing for selects)

**Interfaces:**
- Produces: `modelTypeOptions` includes `{ value: 'asr', label: ... }`
- Produces: form fields `supplier`, `base_model`, `api_domain` as free text; no `params` FormArray in submit payload UI

- [ ] **Step 1: Update model type options**

In `ai-model-settings.component.ts`, extend:

```typescript
modelTypeOptions = [
  { value: 'llm', label: $localize`Large language model` },
  { value: 'vlm', label: $localize`Vision-language model` },
  { value: 'asr', label: $localize`Speech recognition (ASR)` },
]
```

- [ ] **Step 2: Simplify form**

- Keep `supplier`, `base_model`, `api_domain` as `FormControl` strings
- Remove `params` FormArray from form group (or leave unused but do not send UI-edited params)
- Remove `onSupplierChange` / `onBaseModelChange` auto-fill from `supplierList`
- On submit, omit `params` or send `null` / existing unchanged

Minimal form:

```typescript
form = new FormGroup({
  name: new FormControl('', [Validators.required]),
  supplier: new FormControl('', [Validators.required]),
  model_type: new FormControl('llm', [Validators.required]),
  base_model: new FormControl('', [Validators.required]),
  api_domain: new FormControl('', [Validators.required]),
  api_key: new FormControl(''),
  is_default: new FormControl(false),
})
```

Update `onCreateClick` / `onEditClick` / `onSubmit` accordingly — do not require supplier codes from `supplierList`.

- [ ] **Step 3: Update HTML**

Replace supplier `<select>` with:

```html
<input id="aiSupplier" type="text" class="form-control" formControlName="supplier" />
<small class="form-text text-muted" i18n>e.g. siliconflow, openai, deepseek</small>
```

Replace base model `<select>` with text input.

Delete the entire **Advanced parameters** block (lines ~210–252).

- [ ] **Step 4: Manual smoke check**

```bash
cd src-ui
npm start
# Open Settings → AI models → Add model: type ASR, free-text fields, save
```

- [ ] **Step 5: Commit**

```bash
git add src-ui/src/app/components/admin/settings/ai-model-settings/
git commit -m "feat(ui): free-text AI model fields and ASR type"
```

---

### Task 3: Prompt — 视频语音摘要提示词

**Files:**
- Modify: `src-ui/src/app/components/admin/settings/prompt-settings/prompt-settings.component.ts`
- Modify: `src-ui/src/app/components/admin/settings/prompt-settings/prompt-settings.component.html`

**Interfaces:**
- Produces: upsert/load `Prompt.type === 'VIDEO_ASR_SUMMARY'`
- Consumes: existing `PromptService.upsertPrompt(type, content, existing)`

- [ ] **Step 1: Extend component TS**

Add property `videoAsrSummaryPrompt: Prompt = null` and form control `videoAsrSummary: ['']`.

On load:

```typescript
this.videoAsrSummaryPrompt =
  prompts.find((p) => p.type === 'VIDEO_ASR_SUMMARY') || null
// patch form videoAsrSummary: this.videoAsrSummaryPrompt?.content || ''
```

On save, add third `upsertPrompt('VIDEO_ASR_SUMMARY', videoAsrSummary || '', this.videoAsrSummaryPrompt)`.

- [ ] **Step 2: Extend HTML**

Add section after VLM block:

```html
<div class="mb-4">
  <h5 i18n>Video speech summary prompt (VIDEO_ASR_SUMMARY)</h5>
  <!-- Prefer Chinese product label via i18n; source string can be: -->
  <!-- 视频语音摘要提示词 -->
  <textarea
    class="form-control"
    rows="6"
    formControlName="videoAsrSummary"
    placeholder="Enter system prompt for summarizing video transcripts..."
  ></textarea>
  <small class="form-text text-muted" i18n>
    Used as the system prompt when summarizing speech-to-text from videos.
  </small>
</div>
```

Ensure visible Chinese title in zh locale: set i18n source to `视频语音摘要提示词` or add xliff entry if project extracts Chinese sources differently—match existing DOC_READ / VLM pattern.

- [ ] **Step 3: Manual smoke** — save prompt, reload, value persists via `/api/prompts/`

- [ ] **Step 4: Commit**

```bash
git add src-ui/src/app/components/admin/settings/prompt-settings/
git commit -m "feat(ui): add video speech summary prompt settings"
```

---

### Task 4: Frontend + env wiring for video_content_mode

**Files:**
- Modify: `src-ui/src/app/data/paperless-config.ts`
- Modify: `src/paperless/config.py` (optional mirror like OCR fields)
- Modify: `src/paperless/settings.py` if env override pattern is used for OCR

**Interfaces:**
- Produces: UI Select under new category **Video Settings** with values `transcript` / `summary` / `both`
- Produces: API field already on ApplicationConfiguration from Task 1

- [ ] **Step 1: Add frontend enum + option**

In `paperless-config.ts`:

```typescript
export enum VideoContentModeConfig {
  TRANSCRIPT = 'transcript',
  SUMMARY = 'summary',
  BOTH = 'both',
}

// In ConfigCategory:
Video: $localize`Video Settings`,

// In PaperlessConfigOptions:
{
  key: 'video_content_mode',
  title: $localize`Video content mode`,
  type: ConfigOptionType.Select,
  choices: [
    { id: 'transcript', name: $localize`Transcript only` },
    { id: 'summary', name: $localize`Summary only` },
    { id: 'both', name: $localize`Summary and transcript` },
  ],
  config_key: 'PAPERLESS_VIDEO_CONTENT_MODE',
  category: ConfigCategory.Video,
},

// In PaperlessConfig interface:
video_content_mode: VideoContentModeConfig
```

- [ ] **Step 2: Optional env fallback in settings/config**

If OCR fields use `PAPERLESS_OCR_*` env + DB, mirror lightly:

```python
# settings.py
VIDEO_CONTENT_MODE = os.getenv("PAPERLESS_VIDEO_CONTENT_MODE", "both")
```

Parser may read `ApplicationConfiguration.objects.first().video_content_mode or settings.VIDEO_CONTENT_MODE`.

- [ ] **Step 3: Smoke** — Application Configuration UI shows Video category; save mode via API

- [ ] **Step 4: Commit**

```bash
git add src-ui/src/app/data/paperless-config.ts src/paperless/settings.py src/paperless/config.py
git commit -m "feat(ui): add video content mode to app configuration"
```

---

### Task 5: AsrClient (generic transcriptions API)

**Files:**
- Create: `src/paperless/asr.py`
- Create: `src/paperless/tests/test_asr_client.py`

**Interfaces:**
- Produces: `class AsrClient` with `def transcribe(self, audio_path: Path, aimodel: AIModel) -> str`
- Raises: `AsrError` (or `ParseError`-friendly exception) on HTTP/empty text

- [ ] **Step 1: Write failing tests**

```python
from pathlib import Path
from unittest import mock

from django.test import TestCase

from paperless.asr import AsrClient
from paperless.asr import AsrError
from paperless.models import AIModel


class TestAsrClient(TestCase):
    def setUp(self):
        self.model = AIModel(
            name="asr",
            supplier="siliconflow",
            model_type="asr",
            base_model="FunAudioLLM/SenseVoiceSmall",
            api_domain="https://api.siliconflow.cn/v1",
            api_key="sk-test",
        )
        self.audio = Path(__file__).parent / "samples"  # create temp file in test

    def test_transcribe_posts_multipart_and_returns_text(self):
        client = AsrClient()
        audio = Path(self._temp_audio())  # helper writes tiny bytes to temp file

        mock_response = mock.Mock()
        mock_response.raise_for_status = mock.Mock()
        mock_response.json.return_value = {"text": "你好世界"}

        with mock.patch("httpx.Client") as client_cls:
            instance = client_cls.return_value.__enter__.return_value
            instance.post.return_value = mock_response
            text = client.transcribe(audio, self.model)

        self.assertEqual(text, "你好世界")
        args, kwargs = instance.post.call_args
        self.assertTrue(args[0].endswith("/audio/transcriptions"))
        self.assertIn("Authorization", kwargs["headers"])
        self.assertIn("files", kwargs)

    def test_transcribe_raises_on_empty_text(self):
        # similar mock with {"text": ""} → AsrError
        ...
```

Use `tempfile` for audio bytes instead of samples folder if easier.

- [ ] **Step 2: Run — expect fail**

```bash
uv run pytest src/paperless/tests/test_asr_client.py -v --no-cov -n0
```

- [ ] **Step 3: Implement `src/paperless/asr.py`**

```python
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
```

- [ ] **Step 4: Run — expect pass**

- [ ] **Step 5: Commit**

```bash
git add src/paperless/asr.py src/paperless/tests/test_asr_client.py
git commit -m "feat: add generic AsrClient for audio transcriptions API"
```

---

### Task 6: Content assembly helper

**Files:**
- Create: `src/paperless_video/__init__.py` (empty)
- Create: `src/paperless_video/content.py`
- Create: `src/paperless_video/tests/__init__.py`
- Create: `src/paperless_video/tests/test_content.py`
- Modify: `pyproject.toml` — add `"src/paperless_video/tests/"` to `testpaths`

**Interfaces:**
- Produces: `def assemble_video_content(mode: str, transcript: str, summary: str | None) -> str`

- [ ] **Step 1: Write failing tests**

```python
from paperless_video.content import assemble_video_content


def test_transcript_only():
    assert assemble_video_content("transcript", "全转写", None) == "全转写"


def test_summary_only():
    assert assemble_video_content("summary", "全转写", "短摘要") == "短摘要"


def test_both():
    out = assemble_video_content("both", "全转写", "短摘要")
    assert out.startswith("【摘要】")
    assert "短摘要" in out
    assert "【转写】" in out
    assert "全转写" in out
```

- [ ] **Step 2: Run — fail**

```bash
uv run pytest src/paperless_video/tests/test_content.py -v --no-cov -n0
```

- [ ] **Step 3: Implement**

```python
def assemble_video_content(mode: str, transcript: str, summary: str | None) -> str:
    transcript = (transcript or "").strip()
    summary = (summary or "").strip() if summary else ""
    if mode == "transcript":
        return transcript
    if mode == "summary":
        return summary
    if mode == "both":
        return f"【摘要】\n{summary}\n\n【转写】\n{transcript}"
    raise ValueError(f"Unknown video content mode: {mode}")
```

- [ ] **Step 4: Add testpath + run pass + commit**

```bash
git add src/paperless_video/ pyproject.toml
git commit -m "feat: video content assembly helper"
```

---

### Task 7: ffmpeg helpers

**Files:**
- Create: `src/paperless_video/ffmpeg_utils.py`
- Create: `src/paperless_video/tests/test_ffmpeg_utils.py`
- Modify: `Dockerfile` — add `ffmpeg` to `RUNTIME_PACKAGES`
- Modify: `.devcontainer/Dockerfile` if present with apt packages

**Interfaces:**
- Produces: `extract_audio_mp3(video_path: Path, out_dir: Path) -> Path`
- Produces: `extract_thumbnail_webp(video_path: Path, out_dir: Path) -> Path`
- Raises: clear error if ffmpeg missing / no audio

- [ ] **Step 1: Implement helpers using `documents.utils.run_subprocess`**

```python
from pathlib import Path

from documents.utils import run_subprocess
from documents.parsers import ParseError


def extract_audio_mp3(video_path: Path, out_dir: Path) -> Path:
    out = out_dir / "audio.mp3"
    try:
        run_subprocess(
            [
                "ffmpeg", "-y", "-i", str(video_path),
                "-vn", "-acodec", "libmp3lame", "-q:a", "4",
                str(out),
            ],
        )
    except Exception as e:
        raise ParseError(f"ffmpeg audio extraction failed: {e}") from e
    if not out.is_file() or out.stat().st_size == 0:
        raise ParseError("No audio track extracted from video")
    return out


def extract_thumbnail_webp(video_path: Path, out_dir: Path) -> Path:
    # extract one frame then convert, or ffmpeg directly to webp if available
    png = out_dir / "thumb_frame.png"
    out = out_dir / "thumb.webp"
    run_subprocess(
        [
            "ffmpeg", "-y", "-i", str(video_path),
            "-ss", "00:00:01", "-vframes", "1", str(png),
        ],
    )
    # convert via Pillow if webp preferred by pipeline
    from PIL import Image
    with Image.open(png) as im:
        im = im.convert("RGB")
        im.thumbnail((500, 500))
        im.save(out, format="WEBP")
    return out
```

Fallback: if `-ss 1` fails on short videos, retry `-ss 0`.

- [ ] **Step 2: Unit test with mocked `run_subprocess`** (do not require real ffmpeg in CI unit test)

```python
@mock.patch("paperless_video.ffmpeg_utils.run_subprocess")
def test_extract_audio_writes_path(mock_run, tmp_path):
    video = tmp_path / "a.mp4"
    video.write_bytes(b"fake")
    # mock side effect: create audio.mp3
    def _fake(cmd, **kwargs):
        Path(cmd[-1]).write_bytes(b"mp3")
    mock_run.side_effect = _fake
    out = extract_audio_mp3(video, tmp_path)
    assert out.name == "audio.mp3"
```

- [ ] **Step 3: Add `ffmpeg` to Dockerfile `RUNTIME_PACKAGES`**

- [ ] **Step 4: Commit**

```bash
git add src/paperless_video/ffmpeg_utils.py src/paperless_video/tests/test_ffmpeg_utils.py Dockerfile
git commit -m "feat: ffmpeg helpers for video audio and thumbnail"
```

---

### Task 8: LLM video summary helper

**Files:**
- Create: `src/paperless_video/summary.py`
- Create: `src/paperless_video/tests/test_summary.py`

**Interfaces:**
- Produces: `def summarize_transcript(transcript: str) -> str`
- Consumes: default `AIModel(model_type="llm", is_default=True)`, `Prompt(type="VIDEO_ASR_SUMMARY")`
- Default system prompt if Prompt empty:

```text
你是视频内容助手。请根据语音转写文本写出简洁、信息完整的中文摘要，保留关键实体、时间与结论。只输出摘要正文。
```

- [ ] **Step 1: Failing test with mocked httpx**

Mock default LLM + prompt; assert POST to `{api_domain}/chat/completions` with `stream: False` and returned content.

- [ ] **Step 2: Implement non-stream chat completion** (mirror VLM block in `paperless_tesseract/parsers.py`, text-only messages)

```python
def summarize_transcript(transcript: str) -> str:
    from paperless.models import AIModel, Prompt
    import httpx

    llm = AIModel.objects.filter(model_type="llm", is_default=True).first()
    if not llm:
        raise ParseError("No default LLM configured for video summary")
    prompt = Prompt.objects.filter(type="VIDEO_ASR_SUMMARY").first()
    system = (
        prompt.content
        if prompt and prompt.content.strip()
        else "你是视频内容助手。请根据语音转写文本写出简洁、信息完整的中文摘要，保留关键实体、时间与结论。只输出摘要正文。"
    )
    url = f"{llm.api_domain.rstrip('/')}/chat/completions"
    payload = {
        "model": llm.base_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": transcript},
        ],
        "stream": False,
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm.api_key}",
    }
    with httpx.Client(timeout=None) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content")
    if not content or not str(content).strip():
        raise ParseError("LLM returned empty video summary")
    return str(content).strip()
```

- [ ] **Step 3: Tests pass + commit**

```bash
git add src/paperless_video/summary.py src/paperless_video/tests/test_summary.py
git commit -m "feat: LLM summary helper for video transcripts"
```

---

### Task 9: VideoDocumentParser + app registration

**Files:**
- Create: `src/paperless_video/parsers.py`
- Create: `src/paperless_video/signals.py`
- Create: `src/paperless_video/apps.py`
- Create: `src/paperless_video/tests/test_parser.py`
- Modify: `src/paperless/settings.py` — append `"paperless_video.apps.PaperlessVideoConfig"` next to tesseract/text

**Interfaces:**
- Produces: MIME `video/mp4` → `.mp4`
- Produces: `VideoDocumentParser.parse` sets `self.text`; `get_thumbnail` returns webp path; `get_settings` returns `None`
- Consumes: AsrClient, ffmpeg utils, assemble_video_content, summarize_transcript, ApplicationConfiguration.video_content_mode

- [ ] **Step 1: signals.py**

```python
def get_parser(*args, **kwargs):
    from paperless_video.parsers import VideoDocumentParser
    return VideoDocumentParser(*args, **kwargs)


def video_consumer_declaration(sender, **kwargs):
    return {
        "parser": get_parser,
        "weight": 10,
        "mime_types": {
            "video/mp4": ".mp4",
        },
    }
```

- [ ] **Step 2: apps.py** — connect like tesseract (always on)

- [ ] **Step 3: parsers.py parse flow**

```python
class VideoDocumentParser(DocumentParser):
    logging_name = "paperless.parsing.video"

    def get_settings(self):
        return None

    def parse(self, document_path: Path, mime_type, file_name=None):
        from paperless.models import AIModel, ApplicationConfiguration, VideoContentModeChoices
        from paperless.asr import AsrClient, AsrError
        from paperless_video.ffmpeg_utils import extract_audio_mp3
        from paperless_video.content import assemble_video_content
        from paperless_video.summary import summarize_transcript

        cfg = ApplicationConfiguration.objects.first()
        mode = (cfg.video_content_mode if cfg else None) or VideoContentModeChoices.BOTH

        asr_model = AIModel.objects.filter(model_type="asr", is_default=True).first()
        if not asr_model:
            raise ParseError("No default ASR model configured")

        audio = extract_audio_mp3(Path(document_path), Path(self.tempdir))
        try:
            transcript = AsrClient().transcribe(audio, asr_model)
        except AsrError as e:
            raise ParseError(str(e)) from e

        summary = None
        if mode in {VideoContentModeChoices.SUMMARY, VideoContentModeChoices.BOTH, "summary", "both"}:
            summary = summarize_transcript(transcript)

        self.text = assemble_video_content(mode, transcript, summary)
        # no archive_path for video

    def get_thumbnail(self, document_path, mime_type, file_name=None):
        from paperless_video.ffmpeg_utils import extract_thumbnail_webp
        return extract_thumbnail_webp(Path(document_path), Path(self.tempdir))
```

- [ ] **Step 4: Parser unit tests** — mock extract/ASR/summary; assert three modes; assert missing ASR raises `ParseError`

- [ ] **Step 5: Register INSTALLED_APPS + test MIME supported**

```python
from documents.parsers import is_mime_type_supported
# with django setup and app loaded:
assert is_mime_type_supported("video/mp4")
```

Clear `is_mime_type_supported` lru_cache in tests if needed:

```python
is_mime_type_supported.cache_clear()
```

- [ ] **Step 6: Commit**

```bash
git add src/paperless_video/ src/paperless/settings.py
git commit -m "feat: register VideoDocumentParser for video/mp4"
```

---

### Task 10: Docs note + verification

**Files:**
- Modify: `README.md` or `docs/configuration.md` — short section: video MP4, ffmpeg, ASR AIModel example (SiliconFlow), content modes, prompt name
- Do not invent large docs beyond what’s needed

- [ ] **Step 1: Add configuration blurb**

Document:

- `PAPERLESS_VIDEO_CONTENT_MODE` / UI Video content mode  
- Configure default ASR AIModel (`supplier=siliconflow`, domain `https://api.siliconflow.cn/v1`, model e.g. `FunAudioLLM/SenseVoiceSmall`)  
- Configure default LLM + 视频语音摘要提示词  
- Requires ffmpeg in image  

- [ ] **Step 2: Run focused test suite**

```bash
uv run pytest src/paperless/tests/test_asr_client.py src/paperless/tests/test_aimodel_supplier.py src/paperless_video/tests/ --no-cov -n0 -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add README.md docs/configuration.md
git commit -m "docs: document video MP4 processing and ASR setup"
```

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| MP4 only MIME | 9 |
| Generic ASR API / SiliconFlow-compatible | 5, 9 |
| AIModel free-text + ASR type + no advanced UI | 1, 2 |
| VIDEO_ASR_SUMMARY / 视频语音摘要提示词 | 3, 8 |
| video_content_mode transcript/summary/both | 1, 4, 6, 9 |
| content layout 【摘要】/【转写】 | 6 |
| Thumbnail via ffmpeg | 7, 9 |
| No archive PDF | 9 |
| Title/tags unchanged | N/A (existing consume) |
| ffmpeg in image | 7 |
| Fail on missing ASR/LLM / API errors | 8, 9 |
| Docs example | 10 |

## Placeholder / consistency notes

- Mode string values always `transcript` | `summary` | `both`
- Prompt type always `VIDEO_ASR_SUMMARY`
- ASR endpoint always `{api_domain}/audio/transcriptions`
- LLM endpoint always `{api_domain}/chat/completions`

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-30-video-mp4-processing.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with checkpoints  

Which approach?
