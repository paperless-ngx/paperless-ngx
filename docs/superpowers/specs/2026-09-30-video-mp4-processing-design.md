# Video MP4 Processing Design

**Date:** 2026-09-30  
**Branch:** `feature/multi-format-support`  
**Status:** Draft for review

## Goal

Add first-phase support for **MP4 video** uploads: extract audio, transcribe via a **generic ASR API** (SiliconFlow first), optionally generate an LLM summary using a configurable prompt, assemble `Document.content`, and generate a frame thumbnail. Title and tags behave the same as other files today.

## Non-goals (Phase 1)

- Formats other than MP4 / `video/mp4`
- In-app video player
- ASR chunking / long-file splitting
- PDF or other archive derivatives for video
- Changing title (filename) or tag association behavior
- Per-upload override of content mode

## Decisions (approved)

| Topic | Choice |
|-------|--------|
| Capability | Transcript + optional LLM summary + thumbnail |
| ASR | API; OpenAI-compatible `/audio/transcriptions`; SiliconFlow first, provider-agnostic |
| Model config | Reuse `AIModel`; add type `asr` |
| Formats | MP4 only |
| Title / tags | Filename title; tags from upload association (unchanged) |
| Summary storage | Written into `content` (no new summary field) |
| Content modes | Transcript only / summary only / both |
| Mode + prompt placement | Mode in global app config; prompt in Prompt settings |
| Prompt UI name | **视频语音摘要提示词** |
| Parser approach | New `paperless_video` app + `DocumentParser` |

---

## Architecture

```
MP4 upload
  → MIME video/mp4
  → VideoDocumentParser
      1. ffmpeg: extract audio (e.g. mp3/wav)
      2. AsrClient: default AIModel(model_type=asr)
         POST {api_domain}/audio/transcriptions
      3. According to video_content_mode:
           transcript → content = transcript
           summary    → LLM + VIDEO_ASR_SUMMARY prompt → content = summary
           both       → content = summary + separator + transcript
      4. ffmpeg: extract frame → thumbnail
      5. Store original MP4 (no archive PDF)
  → Existing consume path: title from filename, tags from upload metadata
```

### Components

1. **`paperless_video`** (new Django app)  
   - `signals.py`: declare `video/mp4` → `.mp4`  
   - `parsers.py`: `VideoDocumentParser`  
   - Register via `apps.py` / `INSTALLED_APPS` like other parsers  

2. **`AsrClient`** (shared helper, e.g. under `paperless/` or `paperless_video/`)  
   - Input: audio path + `AIModel`  
   - Call: multipart `file` + `model={base_model}`, Bearer `api_key`  
   - Output: transcription `text`  
   - No SiliconFlow-specific branching; only AIModel fields  

3. **LLM summary step**  
   - Use default `AIModel(model_type=llm)`  
   - System prompt from `Prompt.type == "VIDEO_ASR_SUMMARY"` (UI: 视频语音摘要提示词)  
   - User payload: full transcript (or truncated if needed with clear logging)  
   - Fallback default Chinese system prompt if DB prompt empty  

4. **Thumbnail**  
   - ffmpeg frame extract → image used by existing thumbnail pipeline expectations  

5. **AIModel UI / model**  
   - Manual text fields: supplier, base_model, api_domain  
   - Remove advanced settings UI (`params` form)  
   - Model types: `llm` | `vlm` | `asr`  
   - Relax backend `supplier` choices so arbitrary provider names work  

---

## Data model & settings

### `ApplicationConfiguration`

Add:

- `video_content_mode` — CharField, choices:
  - `transcript` — 仅转写
  - `summary` — 仅摘要
  - `both` — 二者共存（recommended default）

Expose in admin settings UI near OCR / VLM options under a **Video** group.

### `Prompt`

New type:

- Code: `VIDEO_ASR_SUMMARY`
- UI label: **视频语音摘要提示词**
- Location: Prompt settings page (alongside DOC_READ, VLM_ANALYSIS_IMAGE)

### `AIModel`

- Add `asr` to frontend model type options  
- `supplier`, `base_model`, `api_domain`: free-text input (no preset-driven selects)  
- Remove advanced parameters UI  
- Backend: allow free-text `supplier` (drop or loosen `SupplierChoices` validation)  
- Default-per-type unchanged: one default ASR, one default LLM  

### `Document`

- No new fields  
- `content` holds summary and/or transcript per mode  
- Suggested `both` layout:

```
【摘要】
{summary}

【转写】
{transcript}
```

---

## Content mode behavior

| Mode | Requires ASR | Requires LLM + prompt | `content` |
|------|--------------|------------------------|-----------|
| `transcript` | Yes | No | Transcript only |
| `summary` | Yes (input to LLM) | Yes | Summary only |
| `both` | Yes | Yes | Summary above transcript |

Note: even `summary` mode still runs ASR first; the LLM summarizes the transcript. Raw transcript is omitted from stored `content` only in `summary` mode.

---

## Error handling

| Condition | Behavior |
|-----------|----------|
| Unsupported MIME | Existing reject |
| No default ASR model | Fail consume with clear message |
| Mode needs summary, no default LLM | Fail consume with clear message |
| ASR API error | Fail consume; do not create empty doc |
| Summary LLM fails after successful ASR | Fail consume (mode semantics must hold) |
| Audio over provider limits (e.g. ~50MB / 1h) | Fail with actionable message; chunking later |
| No audio track | Fail with clear message |
| Missing ffmpeg | Fail with clear message |

---

## Frontend

1. **AI model settings** — manual supplier / base model / API domain; drop advanced section; type filter includes ASR  
2. **Prompt settings** — add 视频语音摘要提示词  
3. **App config** — video content mode selector  
4. **Upload** — no required `accept` change in phase 1; backend enforces MP4  
5. **Player** — out of scope  

---

## Ops / dependencies

- Container / host must provide **ffmpeg** (and ffprobe if used)  
- Document SiliconFlow example AIModel:
  - API domain: `https://api.siliconflow.cn/v1` (or current docs URL)
  - Base model: e.g. `FunAudioLLM/SenseVoiceSmall`
  - Type: `asr`

---

## Testing (phase 1)

- Unit: `AsrClient` request shape / response parse (mocked HTTP)  
- Unit: content assembly for three modes  
- Unit/integration: parser fails when ASR/LLM missing as required  
- UI: model form fields; prompt save/load for `VIDEO_ASR_SUMMARY`; config mode persists  
- Manual: upload short MP4 with SiliconFlow ASR + LLM  

---

## Future (not this phase)

- More containers (MOV, WebM, MKV)  
- ASR chunking for long videos  
- In-app playback  
- Per-upload mode override  
- Keyframe gallery / chapters  

## Implementation order (suggested)

1. AIModel UI + backend supplier looseness + `asr` type  
2. Prompt type `VIDEO_ASR_SUMMARY` + settings UI  
3. `video_content_mode` on ApplicationConfiguration + settings UI  
4. `AsrClient` + `paperless_video` parser (ffmpeg, thumbnail, content modes)  
5. Docs / compose note for ffmpeg  
6. Tests  

---

## Open polish (non-blocking)

- Exact separator labels `【摘要】` / `【转写】` vs blank lines only — default as above unless product prefers otherwise  
- Audio extract format (mp3 vs wav) — prefer provider-friendly small mp3 unless quality issues appear  
