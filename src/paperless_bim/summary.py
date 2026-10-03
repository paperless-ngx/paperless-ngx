"""
LLM-based IFC summary. Mirrors paperless_video.summary: load a
``Prompt`` of type ``BIM_IFC_SUMMARY`` (or fall back to a baked-in
default), POST to the default LLM's ``/chat/completions`` endpoint,
and disable upstream thinking so Qwen / MiniMax-M3 style models
don't emit ``<think>`` blocks.
"""
from __future__ import annotations

import httpx

from documents.parsers import ParseError
from paperless.models import AIModel
from paperless.models import Prompt

DEFAULT_BIM_IFC_SUMMARY_PROMPT = (
    "你是 BIM 信息助手。请根据以下从 IFC 模型抽取出的结构化文本，"
    "生成一份简洁、信息完整的中文摘要，覆盖：项目规模、楼层与空间分布、"
    "主要构件数量与材料、关键设计参数。只输出摘要正文。"
)


def summarize_ifc_text(ifc_text: str) -> str:
    llm = AIModel.objects.filter(model_type="llm", is_default=True).first()
    if not llm:
        raise ParseError("No default LLM configured for BIM summary")
    prompt = Prompt.objects.filter(type="BIM_IFC_SUMMARY").first()
    system = (
        prompt.content
        if prompt and prompt.content.strip()
        else DEFAULT_BIM_IFC_SUMMARY_PROMPT
    )

    url = f"{llm.api_domain.rstrip('/')}/chat/completions"
    payload = {
        "model": llm.base_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": ifc_text},
        ],
        "stream": False,
        # 关闭上游 thinking，避免 Qwen / MiniMax-M3 把 <think> 注入正文
        "thinking": {"type": "disabled"},
        "extra_body": {"enable_thinking": False},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {llm.api_key}",
    }
    with httpx.Client(timeout=None) as client:
        try:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise ParseError(f"BIM summary request failed: {exc}") from exc

    content = (
        data.get("choices", [{}])[0]
        .get("message", {})
        .get("content")
    )
    if not content or not str(content).strip():
        raise ParseError("LLM returned empty BIM summary")
    return str(content).strip()
