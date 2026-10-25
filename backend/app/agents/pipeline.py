"""장애 알림 에이전트 실행기

상담이력 등록 시 FastAPI BackgroundTasks 로 호출되어 LangGraph 그래프(app/agents/graph.py)를 실행하고,
결과를 agent_run 테이블에 기록합니다. 상담이력 등록 응답은 바로 반환됩니다.
"""
import logging
import traceback

from sqlalchemy import text

from app.agents.graph import build_graph
from app.database import SessionLocal
from app.services import repo

log = logging.getLogger("voc.pipeline")


def start_run(db, consult_id: int) -> int:
    run_id = repo.create_run(db, consult_id)
    db.commit()
    return run_id


def execute(run_id: int, consult_id: int) -> None:
    with SessionLocal() as db:
        state: dict = {}
        try:
            consult = repo.get_consult(db, consult_id)
            call = repo.get_stt_call(db, consult["call_id"]) if consult.get("call_id") else None
            graph = build_graph(db, run_id)
            state = graph.invoke({"consult": consult, "call": call, "llm_used": False, "path": []})
            status, outcome = state.get("status", "DONE"), state.get("outcome", "")
        except Exception as e:
            db.rollback()
            log.exception("agent graph failed run_id=%s", run_id)
            status, outcome = "FAILED", f"오류: {e}"
            db.execute(text("""
                UPDATE agent_step SET status = 'FAILED', message = :m, finished_at = now()
                 WHERE run_id = :r AND status = 'RUNNING'
            """), {"m": traceback.format_exc()[-500:], "r": run_id})
        repo.finish_run(db, run_id, status, outcome, state.get("incident_id"), bool(state.get("llm_used")))
        db.commit()
