import httpx

from documents.parsers import ParseError
from paperless.models import AIModel
from paperless.models import Prompt

DEFAULT_VIDEO_SUMMARY_PROMPT = (
    "你是视频内容助手。请根据语音转写文本写出简洁、信息完整的中文摘要，"
    "保留关键实体、时间与结论。只输出摘要正文。"
)


def summarize_transcript(transcript: str) -> str:
    llm = AIModel.objects.filter(model_type="llm", is_default=True).first()
    if not llm:
        raise ParseError("No default LLM configured for video summary")
    prompt = Prompt.objects.filter(type="VIDEO_ASR_SUMMARY").first()
    system = (
        prompt.content
        if prompt and prompt.content.strip()
        else DEFAULT_VIDEO_SUMMARY_PROMPT
    )
    url = f"{llm.api_domain.rstrip('/')}/chat/completions"
    payload = {
        "model": llm.base_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": transcript},
        ],
        "stream": False,
        # 关闭 MiniMax M3 的推理模式，避免 reasoning_content 进入 content
        "thinking": {"type": "disabled"},
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
