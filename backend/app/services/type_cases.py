"""팀이 확인한 유형 상담 (app/data/type_cases.json)

현업이 상담 유형마다 'P1 여부(O/X)'와 이유를 확인한 자료입니다.
새 상담이 들어오면 유형 상담을 전부 비슷한 순서(문자열 유사도)로 정렬해 장애감지 AI 판단에 제공합니다.
(벡터 검색은 상담이 늘어날 때 적용할 예정. 지금은 문자 bigram 유사도로 순위만 매깁니다.)
파일이 없거나 깨져 있으면 빈 목록으로 동작해 기존 판정을 그대로 따릅니다.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

from app.agents import rules

log = logging.getLogger("voc.type_cases")
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "type_cases.json"

# 처리 결과가 이 값이면 P1 이 아닌 건 (오탐·고객 입력 오류·상품 조건)
NOT_P1_RESULTS = {"오탐", "고객 입력 오류", "상품 조건"}
SAME_TYPE_BONUS = 0.1


@lru_cache(maxsize=1)
def load() -> list[dict]:
    try:
        return list(json.loads(DATA_FILE.read_text(encoding="utf-8")).get("유형") or [])
    except Exception:
        log.exception("유형 상담 파일을 읽지 못함: %s", DATA_FILE)
        return []


def by_id() -> dict[str, dict]:
    return {c["id"]: c for c in load()}


def is_not_p1_result(case: dict) -> bool:
    return case.get("처리결과") in NOT_P1_RESULTS


def rank(customer_text: str, error_type: str | None = None) -> list[dict]:
    """모든 유형 상담을 이번 상담과 비슷한 순서로 정렬 (유사도 내림차순, 같은 오류유형이면 가산)."""
    ranked = []
    for c in load():
        ref = f"{c.get('유형', '')} {c.get('증상', '')} {' '.join(c.get('고객 말') or [])}"
        sim = rules.similarity(customer_text, ref)
        if error_type and c.get("오류유형") == error_type:
            sim = round(min(1.0, sim + SAME_TYPE_BONUS), 3)
        ranked.append({**c, "similarity": sim})
    ranked.sort(key=lambda c: c["similarity"], reverse=True)
    return ranked


def label(case: dict) -> str:
    """AI 프롬프트용 구분 표시. 오탐 계열은 처리 결과까지."""
    g = case.get("구분", "")
    return f"{g}({case['처리결과']})" if is_not_p1_result(case) else g


def prompt_text(ranked: list[dict]) -> str:
    """AI 프롬프트에 넣을 유형 상담 목록 (비슷한 순서)."""
    lines = []
    for c in ranked:
        said = " / ".join(c.get("고객 말") or [])[:90]
        lines.append(f"[{c['id']}] {label(c)} · P1 {c.get('P1', '')} · {c.get('증상', '')[:60]} · 고객: {said}"
                     f" · 이유: {c.get('P1 판단 이유', '')}")
    return "\n".join(lines)
