"""시연 데이터 등록 (시스템관리 > 시연 데이터 등록 · /api/admin/demo-data)

대규모 장애 신호 시연 4건(sql/15_demo_large_signal.sql)을 넣습니다.
  1. SQL 실행: 이전에 등록한 같은 통화와 그 상담으로 생긴 데이터를 지우고, 4건을 '진행' 통화로 다시 넣음
  2. 사전 제보 2건(PR_P1_LG_1 · PR_P1_LG_2)은 상담이력을 등록하고 장애 알림 에이전트를 실제로 실행해 상담완료로 둠
     (상담이력 등록 화면과 같은 흐름. LLM 설정이 있으면 사용하므로 1분 정도 걸릴 수 있음.
      이때 나오는 메신저 알림은 실제로 보내지 않고, 발송 이력도 지워 시연 때 3번째 제보에서 알림이 나가게 함)
  3. 나머지 2건(PR_P1 · PR_P1_LG_3)은 상담현황에 '진행'으로 남겨 시연 때 상담이력을 등록
같은 증상 제보는 60분 안에 이어져야 하나의 장애로 묶이므로 시연 직전에 등록합니다.
"""
import logging
import threading
from pathlib import Path

from sqlalchemy import text

from app.agents import pipeline, summary
from app.database import SessionLocal, engine, settings
from app.services import repo

log = logging.getLogger(__name__)
SQL_FILE = Path(__file__).resolve().parent.parent / "sql" / "15_demo_large_signal.sql"
_lock = threading.Lock()

# 시연 시나리오 4건. pre=True 는 등록 기능이 상담이력 등록 + 에이전트 실행까지 (시연 전 사전 제보)
SCENARIOS = [
    {"call_id": "PR_P1_LG_1", "source": "대규모 신호 1 · 앱 로그인 E-1032 (앱 7.4.0)", "title": "앱 업데이트 후 로그인 오류 (같은 증상 1번째 고객)",
     "pre": True, "consult": {"consult_type": "전산오류문의", "channel": "앱", "result_status": "이관"}},
    {"call_id": "PR_P1_LG_2", "source": "대규모 신호 2 · 앱 로그인 E-1032 (앱 7.4.0)", "title": "앱 업데이트 후 로그인 오류 (같은 증상 2번째 고객)",
     "pre": True, "consult": {"consult_type": "전산오류문의", "channel": "앱", "result_status": "이관"}},
    {"call_id": "PR_P1", "source": "1.상담대화_PR_P1.xlsx", "title": "이체 지급 기한 임박 · 대체수단 없음", "pre": False},
    {"call_id": "PR_P1_LG_3", "source": "대규모 신호 3 · 앱 로그인 E-1032 (앱 7.4.0)", "title": "같은 증상 3번째 고객 → 대규모 장애 신호", "pre": False},
]
IDS = [s["call_id"] for s in SCENARIOS]


def status() -> list[dict]:
    """시나리오별 현재 상태: 통화 등록 여부 · 상담상태 · 마지막 에이전트 실행 결과."""
    with engine.connect() as cn:
        rows = {r["call_id"]: dict(r) for r in cn.execute(text("""
            SELECT c.call_id, c.customer_name, c.agent_name, c.consult_status, c.started_at,
                   h.consult_id, r.run_id, r.status AS run_status, r.outcome, r.incident_id,
                   i.severity, i.report_count, i.customer_count, i.mass_signal
              FROM stt_call c
              LEFT JOIN LATERAL (SELECT consult_id FROM consult_history WHERE call_id = c.call_id
                                  ORDER BY consult_id DESC LIMIT 1) h ON TRUE
              LEFT JOIN LATERAL (SELECT run_id, status, outcome, incident_id FROM agent_run WHERE consult_id = h.consult_id
                                  ORDER BY run_id DESC LIMIT 1) r ON TRUE
              LEFT JOIN incident_alert i ON i.incident_id = r.incident_id
             WHERE c.call_id = ANY(:ids)"""), {"ids": IDS}).mappings()}
    out = []
    for s in SCENARIOS:
        row = rows.get(s["call_id"])
        if row and row.get("incident_id"):
            row["incident_no"] = repo.incident_no(row["incident_id"])
        out.append({**{k: v for k, v in s.items() if k != "consult"}, "registered": bool(row), **(row or {})})
    return out


def register(by: str) -> list[dict]:
    """시연 데이터 4건 등록 (이미 있으면 지우고 다시). 끝난 뒤 상태를 돌려줌."""
    if not _lock.acquire(blocking=False):
        raise RuntimeError("다른 시연 데이터 등록이 진행 중입니다. 끝난 뒤 다시 시도하세요.")
    try:
        raw = engine.raw_connection()
        try:
            cur = raw.cursor()
            cur.execute("SET LOCAL lock_timeout = '15s'")
            cur.execute(SQL_FILE.read_text(encoding="utf-8"))
            raw.commit()
        except Exception:
            raw.rollback()
            raise
        finally:
            raw.close()
        log.warning("시연 데이터 등록 (%s): %s", by, ", ".join(IDS))

        # 화면 연출용 단계 지연 없이 실행하고, 사전 제보의 알림은 실제로 보내지 않고 기록만 (시연 전에 담당자에게 알림이 가지 않게)
        saved = (settings.agent_step_delay_sec, settings.messenger_provider, settings.messenger_webhook_url)
        settings.agent_step_delay_sec, settings.messenger_provider, settings.messenger_webhook_url = 0, "mock", ""
        try:
            with SessionLocal() as db:
                for s in [s for s in SCENARIOS if s["pre"]]:
                    call = repo.get_stt_call(db, s["call_id"])
                    consult = repo.create_consult(db, {
                        "call_id": call["call_id"], "customer_id": call["customer_id"],
                        "customer_name": call["customer_name"], "agent_name": call["agent_name"],
                        "summary": summary.draft(call)["summary"], "registered_by": by, **s["consult"]})
                    repo.complete_call(db, call["call_id"])                    # 상담진행 → 상담완료
                    db.commit()
                    pipeline.execute(pipeline.start_run(db, consult["consult_id"]), consult["consult_id"])
                # 사전 제보가 알림 대상(P1 등)으로 나와도 발송 이력은 지움: 시연 때 3번째 제보의 알림이
                # '이미 발송된 장애'로 생략되지 않고 실제로 나가도록 (등급·장애 정보는 에이전트 결과 그대로)
                pre_ids = [s["call_id"] for s in SCENARIOS if s["pre"]]
                db.execute(text("""
                    WITH inc AS (SELECT DISTINCT r.incident_id FROM incident_report r
                                   JOIN consult_history h ON h.consult_id = r.consult_id WHERE h.call_id = ANY(:ids))
                    DELETE FROM messenger_log WHERE incident_id IN (SELECT incident_id FROM inc)"""), {"ids": pre_ids})
                db.execute(text("""
                    UPDATE incident_alert SET notified_severity = NULL
                     WHERE incident_id IN (SELECT r.incident_id FROM incident_report r
                                             JOIN consult_history h ON h.consult_id = r.consult_id WHERE h.call_id = ANY(:ids))"""),
                           {"ids": pre_ids})
                db.commit()
        finally:
            settings.agent_step_delay_sec, settings.messenger_provider, settings.messenger_webhook_url = saved
        return status()
    finally:
        _lock.release()
