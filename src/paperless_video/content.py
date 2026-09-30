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
