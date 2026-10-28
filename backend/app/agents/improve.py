"""⑤ 개선의견 등록

장애감지 에이전트가 '개선의견'(해결·완료된 건에 대해 화면 문구·안내·절차를 바꿔 달라는 요청)으로
분류한 상담을 개선의견으로 기록합니다.
  - 알림·승인 대상이 아니며 메신저를 보내지 않습니다.
  - 장애 중복통합·누적 건수에 넣지 않습니다. (반복 의견이 장애로 자동 상향되지 않음)
  - 비슷한 최근 장애(해결·처리 중)가 있으면 관련 장애로 연결합니다.
"""
from app.agents import rules
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


def run(db, ctx: dict) -> tuple[str, str, dict]:
    det, consult = ctx["detection"], ctx["consult"]
    text = ctx.get("customer_text") or ""
    related, sim = _related_incident(db, text)
    row = repo.create_improvement(db, {
        "consult_id": consult["consult_id"],
        "call_id": consult.get("call_id"),
        "customer_id": consult["customer_id"],
        "customer_name": consult.get("customer_name"),
        "error_type": det.get("error_type"),
        "channel": det.get("channel"),
        "title": det.get("title") or "개선의견",
        "content": consult.get("summary") or "",
        "customer_excerpt": text[:1000],
        "related_incident_id": related["incident_id"] if related else None,
    })
    out = {"improvement_id": row["improvement_id"], "sent": False,
           "related_incident_id": row["related_incident_id"]}
    msg = f"개선의견 #{row['improvement_id']} 등록 - 알림·승인 대상 아님, 장애 누적에서 제외"
    if related:
        msg += f" · 관련 장애 {repo.incident_no(related['incident_id'])} '{related['title']}' 연결 (유사도 {round(sim, 3)})"
    return "DONE", msg, out
