"""⑤ 개선의견 등록

장애감지 에이전트가 '개선의견'(해결·완료된 건에 대해 화면 문구·안내·절차를 바꿔 달라는 요청)으로
분류한 상담을 개선의견으로 기록합니다.
  - 알림·승인 대상이 아니며 메신저를 보내지 않습니다.
  - 장애 중복통합·누적 건수에 넣지 않습니다. (반복 의견이 장애로 자동 상향되지 않음)
  - 비슷한 최근 장애(해결·처리 중)가 있으면 관련 장애로 연결합니다. (기록만, 개선의견 목록 화면에는 표시하지 않음)
  - 개선의견 내용은 상담요약을 그대로 옮기지 않고 [요청]·[배경] 두 줄로 요약합니다. (LLM → 실패 시 규칙)
"""
import re

from app.agents import llm, rules
from app.services import repo

NAME = "개선의견 등록"
RELATED_MIN_SIMILARITY = 0.12
RELATED_DAYS = 30


def _related_incident(db, customer_text: str) -> tuple[dict | None, float]:
    best, best_sim = None, 0.0
    for inc in repo.recent_incidents_for_link(db, RELATED_DAYS):
        sim = rules.similarity(customer_text, f"{inc['title']} {inc.get('symptoms') or ''}")
        if sim > best_sim:
            best, best_sim = inc, sim
    return (best, best_sim) if best_sim >= RELATED_MIN_SIMILARITY else (None, best_sim)


SUMMARY_SYSTEM = """당신은 금융 콜센터에서 고객 개선의견을 정리하는 담당자입니다.
상담 내용을 읽고 고객이 바꿔 달라고 한 것을 개선의견 목록에 올릴 요약으로 쓰세요.
작성 규칙:
- 아래 2줄 형식을 지키세요. 각 줄은 한 문장, 40~70자 안팎.
  [요청] 어떤 화면·안내·절차의 무엇을 어떻게 바꿔 달라는지 (~요청 으로 끝냄)
  [배경] 고객이 겪은 불편과 지금 상태 (예: 오류는 해결됨, 신청은 정상 완료)
- 상담사의 응대 멘트는 넣지 말고, 대화에 없는 내용은 추측하지 마세요. 고객 개인정보는 적지 마세요.
출력 JSON 스키마: {"summary": "[요청] ...\\n[배경] ..."}"""


def rule_summary(title: str | None, consult_summary: str | None) -> str:
    """규칙 기반 요약: 상담요약 첫 줄에서 [요청]·[배경]을 나눔. 예) '[의견] 진행 단계 표시 요청 (신청 정상 완료).'"""
    first = (consult_summary or "").strip().splitlines()[0] if (consult_summary or "").strip() else ""
    first = re.sub(r"\[[^\]]+\]\s*", "", first).strip()
    m = re.match(r"(.+?)\s*\(([^)]+)\)\.?$", first)
    req, bg = (m.group(1), m.group(2)) if m else (re.split(r"(?<=[.다함])\s", first)[0], "")
    req = req.rstrip(". ") or (title or "개선의견")
    lines = [f"[요청] {req[:90]}"]
    if bg:
        lines.append(f"[배경] {bg.rstrip('. ')[:90]}")
    return "\n".join(lines)


def summarize(consult: dict, customer_text: str, title: str | None) -> tuple[str, str]:
    """(요약, 'LLM'|'규칙')"""
    base = rule_summary(title, consult.get("summary"))
    if llm.enabled() and customer_text.strip():
        ans = llm.ask_json(SUMMARY_SYSTEM, f"[고객 발화]\n{customer_text[:1500]}\n\n[상담요약]\n{consult.get('summary') or ''}",
                           max_tokens=300)
        text = (ans or {}).get("summary")
        if isinstance(text, str) and "[요청]" in text:
            return text.strip()[:400], "LLM"
    return base, "규칙"


def run(db, ctx: dict) -> tuple[str, str, dict]:
    det, consult = ctx["detection"], ctx["consult"]
    text = ctx.get("customer_text") or ""
    related, sim = _related_incident(db, text)
    content, source = summarize(consult, text, det.get("title"))
    row = repo.create_improvement(db, {
        "consult_id": consult["consult_id"],
        "call_id": consult.get("call_id"),
        "customer_id": consult["customer_id"],
        "customer_name": consult.get("customer_name"),
        "error_type": det.get("error_type"),
        "channel": det.get("channel"),
        "title": det.get("title") or "개선의견",
        "content": content,
        "customer_excerpt": text[:1000],
        "related_incident_id": related["incident_id"] if related else None,
    })
    out = {"improvement_id": row["improvement_id"], "sent": False,
           "related_incident_id": row["related_incident_id"]}
    msg = f"개선의견 #{row['improvement_id']} 등록 ({source} 요약) - 알림·승인 대상 아님, 장애 누적에서 제외"
    if related:
        msg += f" · 관련 장애 {repo.incident_no(related['incident_id'])} '{related['title']}' 연결 (유사도 {round(sim, 3)})"
    return "DONE", msg, out
