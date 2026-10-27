"""LLM 호출 래퍼 (추가 패키지 없이 httpx 사용).

LLM_PROVIDER 로 선택:
  - "ollama"    : Ollama /api/chat  (로컬은 키 불필요, Ollama Cloud 는 OLLAMA_API_KEY 사용)
  - "anthropic" : Claude Messages API (ANTHROPIC_API_KEY 필요)
  - "none"      : LLM 미사용 (규칙 기반)

호출이 실패하면 None 을 반환하고, 각 에이전트는 규칙 기반 결과로 계속 진행합니다.
"""
import json
import logging
import re

import httpx

from app.database import settings

log = logging.getLogger("voc.llm")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
JSON_RULE = "\n반드시 설명 없이 JSON 객체 하나만 출력하세요."


def provider() -> str:
    return (settings.llm_provider or "none").strip().lower()


def enabled() -> bool:
    p = provider()
    if p == "ollama":
        cloud = "ollama.com" in settings.ollama_base_url
        return bool(settings.ollama_model) and (bool(settings.ollama_api_key) or not cloud)
    if p == "anthropic":
        return bool(settings.anthropic_api_key)
    return False


def describe() -> str:
    p = provider()
    if p == "ollama" and enabled():
        return f"Ollama · {settings.ollama_model}"
    if p == "anthropic" and enabled():
        return f"Claude · {settings.llm_model}"
    return "규칙 기반"


def _extract_json(text: str) -> dict | None:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < 0:
            return None
        text = text[start:end + 1]
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def _ask_ollama(system: str, user: str, max_tokens: int) -> str:
    headers = {"content-type": "application/json"}
    if settings.ollama_api_key:  # Ollama Cloud (https://ollama.com)
        headers["Authorization"] = f"Bearer {settings.ollama_api_key}"
    body = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system + JSON_RULE},
            {"role": "user", "content": user},
        ],
        "format": "json",        # JSON 출력 강제
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": max_tokens},
    }
    url = settings.ollama_base_url.rstrip("/") + "/api/chat"
    resp = httpx.post(url, headers=headers, json=body, timeout=settings.llm_timeout_sec)
    if resp.status_code == 400:  # 일부 모델/환경에서 format 미지원 → 프롬프트 지시만으로 재시도
        body.pop("format")
        resp = httpx.post(url, headers=headers, json=body, timeout=settings.llm_timeout_sec)
    resp.raise_for_status()
    return resp.json().get("message", {}).get("content", "")


def _ask_anthropic(system: str, user: str, max_tokens: int) -> str:
    resp = httpx.post(
        ANTHROPIC_URL,
        headers={
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": settings.llm_model,
            "max_tokens": max_tokens,
            "system": system + JSON_RULE,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"effort": settings.llm_effort},
        },
        timeout=settings.llm_timeout_sec,
    )
    resp.raise_for_status()
    data = resp.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def ask_json(system: str, user: str, max_tokens: int = 1500) -> dict | None:
    """JSON 객체로 답하도록 요청하고 dict 로 반환. 실패 시 None."""
    if not enabled():
        return None
    try:
        text = _ask_ollama(system, user, max_tokens) if provider() == "ollama" \
            else _ask_anthropic(system, user, max_tokens)
        result = _extract_json(text)
        if result is None:
            log.warning("LLM 응답 JSON 파싱 실패: %s", text[:300])
        return result
    except Exception as e:
        log.warning("LLM 호출 실패(%s): %s", provider(), e)
        return None
