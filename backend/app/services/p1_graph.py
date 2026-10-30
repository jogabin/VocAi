"""P1 관계 지도 (app/data/p1_graph.json)

현업이 확인한 P1 유형에서 뽑은 '조건'과 그 연결(경로)입니다. 통계로 학습한 것이 아니라 현업 판단을 정리한 것이며,
경로의 조건이 이번 고객 발화에서 확인되고 'P1을 막는 조건'이 없을 때 P1 확인 대상으로 봅니다.
유형이나 인원수 하나만으로 P1을 확정하지 않습니다. 지도는 AI 판단의 근거·순서를 돕는 자료입니다.
파일이 없거나 깨져 있으면 빈 지도로 동작합니다.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("voc.p1_graph")
DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "p1_graph.json"


@lru_cache(maxsize=1)
def load() -> dict:
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        log.exception("P1 관계 지도 파일을 읽지 못함: %s", DATA_FILE)
        return {}


def path_ids() -> set[str]:
    return {p["id"] for p in load().get("P1 경로") or []}


def path_name(path_id: str) -> str:
    return next((p["이름"] for p in load().get("P1 경로") or [] if p["id"] == path_id), "")


def prompt_text() -> str:
    """AI 프롬프트에 넣을 지도 (조건 · P1 경로 · P1을 막는 조건). 지도가 비어 있으면 빈 문자열."""
    g = load()
    if not g:
        return ""
    lines = ["조건:"]
    lines += [f"- {k}: {v['뜻']}" for k, v in (g.get("조건") or {}).items()]
    lines.append("P1 경로 (경로의 조건을 모두 충족할 때):")
    lines += [f"- {p['id']} {p['이름']}: " + " + ".join(p["조건"]) for p in g.get("P1 경로") or []]
    lines.append("P1이 아닌 경우 (있으면 경로가 맞아도 P1 아님):")
    lines += [f"- {b['이름']}" for b in g.get("막는 조건") or []]
    return "\n".join(lines)
