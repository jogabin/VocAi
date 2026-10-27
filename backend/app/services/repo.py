"""DB 접근 함수 모음.

API 라우터와 에이전트가 같은 함수를 공유합니다.
(에이전트는 같은 프로세스 안에서 API와 동일한 조회/등록 로직을 직접 호출)
커밋은 호출하는 쪽(라우터/파이프라인)에서 합니다.
"""
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

OPEN_STATUSES = ("관찰", "접수", "확인중")
CLOSED_STATUSES = ("해결", "오탐")

# 화면 처리상태 ↔ 내부 상태 (sql/07_incident_process.sql 참고)
PROCESS_STATUS_SQL = """CASE i.status WHEN '확인중' THEN '진행중' WHEN '해결' THEN '처리완료'
                                  WHEN '오탐' THEN '미대상' ELSE '대기중' END AS process_status"""
PROCESS_TO_STATUS = {"진행중": "확인중", "처리완료": "해결", "미대상": "오탐"}   # 대기중은 알림 여부로 관찰/접수
PERIOD_SQL = {"today": "i.created_at >= date_trunc('day', now())",
              "7d": "i.created_at >= now() - interval '7 days'",
              "all": "TRUE"}
# 날짜별 조회 (화면 날짜 = 한국 시간 기준)
KST_DATE = "(({col}) AT TIME ZONE 'Asia/Seoul')::date"
# 모니터 건수 박스 → 목록 조건
BOX_SQL = {
    "registered": "TRUE",
    "urgent": "i.severity = :top AND i.status NOT IN ('해결', '오탐')",
    "messaged": "EXISTS (SELECT 1 FROM messenger_log m WHERE m.incident_id = i.incident_id)",
    "same_type": "i.mass_signal",
    "resolved": "i.status = '해결'",
}


def _rows(result) -> list[dict]:
    return [dict(r) for r in result.mappings().all()]


def _row(result) -> dict | None:
    r = result.mappings().first()
    return dict(r) if r else None


def _date_conds(col: str, date_from, date_to, conds: list, params: dict) -> None:
    """조회 기간(한국 날짜 기준, 양 끝 포함) 조건 추가. 비어 있으면 제한 없음."""
    if date_from:
        conds.append(f"{KST_DATE.format(col=col)} >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conds.append(f"{KST_DATE.format(col=col)} <= :date_to")
        params["date_to"] = date_to


# =====================================================================
# STT 원문
# =====================================================================
def list_stt_calls(db: Session, keyword: str | None = None, registered: bool | None = None,
                   limit: int = 50, offset: int = 0, consult_status: str | None = None,
                   date_from=None, date_to=None) -> list[dict]:
    conds, params = [], {"limit": limit, "offset": offset}
    _date_conds("c.started_at", date_from, date_to, conds, params)
    if consult_status:
        conds.append("c.consult_status = :cs")
        params["cs"] = consult_status
    if keyword:
        conds.append("""(c.customer_name ILIKE :kw OR c.call_id ILIKE :kw OR c.customer_id ILIKE :kw
                         OR EXISTS (SELECT 1 FROM stt_utterance u2
                                    WHERE u2.call_id = c.call_id AND u2.text ILIKE :kw))""")
        params["kw"] = f"%{keyword}%"
    if registered is True:
        conds.append("ch.consult_id IS NOT NULL")
    elif registered is False:
        conds.append("ch.consult_id IS NULL")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return _rows(db.execute(text(f"""
        SELECT c.*,
               ch.consult_id, ch.consult_type, ch.consult_created_at, ch.registered_by,
               (SELECT max(u.created_at) FROM stt_utterance u WHERE u.call_id = c.call_id) AS last_utterance_at,
               (SELECT u.text FROM stt_utterance u
                 WHERE u.call_id = c.call_id AND u.speaker = 'CUSTOMER'
                 ORDER BY u.seq LIMIT 1) AS preview,
               (SELECT count(*) FROM stt_utterance u WHERE u.call_id = c.call_id) AS utterance_count
          FROM stt_call c
          LEFT JOIN LATERAL (SELECT consult_id, consult_type, created_at AS consult_created_at, registered_by
                               FROM consult_history h
                              WHERE h.call_id = c.call_id ORDER BY consult_id DESC LIMIT 1) ch ON TRUE
          {where}
         ORDER BY CASE c.consult_status WHEN '진행' THEN 0 ELSE 1 END, c.started_at DESC
         LIMIT :limit OFFSET :offset
    """), params))


def get_stt_call(db: Session, call_id: str) -> dict | None:
    call = _row(db.execute(text("SELECT * FROM stt_call WHERE call_id = :id"), {"id": call_id}))
    if not call:
        return None
    call["utterances"] = _rows(db.execute(text("""
        SELECT seq, speaker, offset_sec, text, added_by FROM stt_utterance
         WHERE call_id = :id ORDER BY seq
    """), {"id": call_id}))
    call["consult"] = _row(db.execute(text("""
        SELECT h.*, r.run_id, r.status AS run_status, r.outcome AS run_outcome, r.incident_id
          FROM consult_history h
          LEFT JOIN LATERAL (SELECT run_id, status, outcome, incident_id FROM agent_run ar
                              WHERE ar.consult_id = h.consult_id ORDER BY run_id DESC LIMIT 1) r ON TRUE
         WHERE h.call_id = :id ORDER BY h.consult_id DESC LIMIT 1
    """), {"id": call_id}))
    return call


def add_utterance(db: Session, call_id: str, speaker: str, text_: str, added_by: str) -> dict:
    """관리자 대화 추가: 마지막 발화 뒤에 붙임 (발화 시각 = 마지막 발화 + 5초)."""
    return _row(db.execute(text("""
        INSERT INTO stt_utterance (call_id, seq, speaker, offset_sec, text, added_by)
        SELECT :cid, coalesce(max(seq), 0) + 1, :sp, coalesce(max(offset_sec), -5) + 5, :tx, :by
          FROM stt_utterance WHERE call_id = :cid
        RETURNING seq, speaker, offset_sec, text, added_by
    """), {"cid": call_id, "sp": speaker, "tx": text_, "by": added_by}))


def complete_call(db: Session, call_id: str) -> None:
    db.execute(text("""UPDATE stt_call SET consult_status = '상담완료', completed_at = now(),
                              duration_sec = greatest(duration_sec,
                                  coalesce((SELECT max(offset_sec) FROM stt_utterance WHERE call_id = :id), 0))
                        WHERE call_id = :id"""), {"id": call_id})


# =====================================================================
# 상담이력
# =====================================================================
def list_consults(db: Session, keyword: str | None = None, consult_type: str | None = None,
                  limit: int = 20, offset: int = 0) -> list[dict]:
    conds, params = [], {"limit": limit, "offset": offset}
    if keyword:
        conds.append("(h.customer_name ILIKE :kw OR h.summary ILIKE :kw OR h.call_id ILIKE :kw)")
        params["kw"] = f"%{keyword}%"
    if consult_type:
        conds.append("h.consult_type = :ct")
        params["ct"] = consult_type
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return _rows(db.execute(text(f"""
        SELECT h.*, r.run_id, r.status AS run_status, r.outcome AS run_outcome, r.incident_id
          FROM consult_history h
          LEFT JOIN LATERAL (SELECT run_id, status, outcome, incident_id FROM agent_run ar
                              WHERE ar.consult_id = h.consult_id ORDER BY run_id DESC LIMIT 1) r ON TRUE
          {where}
         ORDER BY h.consult_id DESC
         LIMIT :limit OFFSET :offset
    """), params))


def get_consult(db: Session, consult_id: int) -> dict | None:
    return _row(db.execute(text("SELECT * FROM consult_history WHERE consult_id = :id"), {"id": consult_id}))


def create_consult(db: Session, data: dict) -> dict:
    return _row(db.execute(text("""
        INSERT INTO consult_history (call_id, customer_id, customer_name, agent_name, consult_type,
                                     channel, summary, memo, result_status, registered_by)
        VALUES (:call_id, :customer_id, :customer_name, :agent_name, :consult_type,
                :channel, :summary, :memo, :result_status, :registered_by)
        RETURNING *
    """), {"memo": None, "registered_by": None, **data}))


# =====================================================================
# 업무담당자
# =====================================================================
def list_owners(db: Session, error_type: str | None = None, on_duty_only: bool = False) -> list[dict]:
    conds, params = [], {}
    if error_type:
        conds.append("error_type = :et")
        params["et"] = error_type
    if on_duty_only:
        conds.append("on_duty")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return _rows(db.execute(text(f"""
        SELECT * FROM biz_owner {where}
         ORDER BY error_type,
                  CASE role WHEN '담당' THEN 1 WHEN '부담당' THEN 2 WHEN '팀장' THEN 3 ELSE 9 END,
                  owner_id
    """), params))


# =====================================================================
# 인사정보 (메신저 수신자 식별) - 인사정보 조회 API(/api/employees)와 같은 테이블
# =====================================================================
_EMP_SELECT = """SELECT emp_id, emp_no, emp_name, emp_group, dept, position, duty_role, duty_error_types,
                        duty_system, messenger_id, on_duty FROM employee"""


def find_it_staff(db: Session, error_type: str) -> list[dict]:
    """해당 오류유형을 담당하는 근무 중 IT담당자 (팀장 → 담당 → 부담당 순)."""
    return _rows(db.execute(text(f"""
        {_EMP_SELECT}
         WHERE emp_group = 'IT담당자' AND use_yn AND on_duty AND messenger_id IS NOT NULL
           AND :et = ANY(duty_error_types)
         ORDER BY CASE duty_role WHEN '담당' THEN 1 WHEN '부담당' THEN 2 WHEN '팀장' THEN 3 ELSE 9 END, emp_id
    """), {"et": error_type}))


def employees_by_ids(db: Session, ids: list[int]) -> list[dict]:
    if not ids:
        return []
    return _rows(db.execute(text(f"{_EMP_SELECT} WHERE emp_id = ANY(:ids) AND use_yn ORDER BY emp_id"),
                            {"ids": list(ids)}))


def past_resolvers(db: Session, incident_ids: list[int]) -> list[dict]:
    """과거 유사 장애를 처리(해결)한 담당자. 처리자가 없으면 그 장애의 담당자."""
    if not incident_ids:
        return []
    return _rows(db.execute(text("""
        SELECT i.incident_id, i.title, coalesce(i.resolved_by_emp_id, i.owner_emp_id) AS emp_id
          FROM incident_alert i
         WHERE i.incident_id = ANY(:ids) AND i.status = '해결'
           AND coalesce(i.resolved_by_emp_id, i.owner_emp_id) IS NOT NULL
    """), {"ids": list(incident_ids)}))


# =====================================================================
# 장애 알림 정보
# =====================================================================
_INCIDENT_COLS = {
    "title", "error_type", "channel", "severity", "status", "report_count", "mass_signal",
    "symptoms", "env_info", "analysis", "similar_cases", "owner_id", "notified_severity",
    "resolution", "last_reported_at", "resolved_at", "criteria_version", "applied_rules",
    "owner_emp_id", "resolved_by_emp_id", "customer_count",
}
_JSON_COLS = {"env_info", "similar_cases", "applied_rules"}
_OPTIONAL_COLS = {"criteria_version", "applied_rules",   # sql/04_severity_criteria.sql 실행 후 생기는 컬럼
                  "customer_count"}                       # sql/10_impact_improvement.sql 실행 후 생기는 컬럼
_col_cache = {"at": 0.0, "cols": set()}


def _incident_columns(db: Session) -> set:
    """04 SQL 실행 전에도 동작하도록 incident_alert 의 실제 컬럼을 확인 (60초 캐시)."""
    import time
    if time.time() - _col_cache["at"] > 60 or not _col_cache["cols"]:
        _col_cache["cols"] = {r[0] for r in db.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'incident_alert'")).all()}
        _col_cache["at"] = time.time()
    return _col_cache["cols"]


def _prep(data: dict, existing: set | None = None) -> tuple[list[str], dict]:
    cols, params = [], {}
    for k, v in data.items():
        if k not in _INCIDENT_COLS:
            continue
        if k in _OPTIONAL_COLS and existing is not None and k not in existing:
            continue
        cols.append(k)
        params[k] = json.dumps(v, ensure_ascii=False) if k in _JSON_COLS else v
    return cols, params


def create_incident(db: Session, data: dict) -> dict:
    cols, params = _prep(data, _incident_columns(db))
    values = [f"CAST(:{c} AS jsonb)" if c in _JSON_COLS else f":{c}" for c in cols]
    return _row(db.execute(text(f"""
        INSERT INTO incident_alert ({", ".join(cols)}) VALUES ({", ".join(values)}) RETURNING *
    """), params))


def update_incident(db: Session, incident_id: int, data: dict) -> dict | None:
    cols, params = _prep(data, _incident_columns(db))
    if not cols:
        return get_incident(db, incident_id, detail=False)
    sets = [f"{c} = CAST(:{c} AS jsonb)" if c in _JSON_COLS else f"{c} = :{c}" for c in cols]
    params["id"] = incident_id
    return _row(db.execute(text(f"""
        UPDATE incident_alert SET {", ".join(sets)}, updated_at = now()
         WHERE incident_id = :id RETURNING *
    """), params))


def add_incident_report(db: Session, incident_id: int, consult_id: int, similarity: float | None) -> None:
    db.execute(text("""
        INSERT INTO incident_report (incident_id, consult_id, similarity)
        VALUES (:iid, :cid, :sim) ON CONFLICT DO NOTHING
    """), {"iid": incident_id, "cid": consult_id, "sim": similarity})


def count_incident_customers(db: Session, incident_id: int) -> int:
    """장애에 연결된 상담의 독립 고객 수 (같은 고객의 재문의·중복 등록은 1명)."""
    return int(db.execute(text("""
        SELECT count(DISTINCT h.customer_id) FROM incident_report r
          JOIN consult_history h ON h.consult_id = r.consult_id
         WHERE r.incident_id = :iid
    """), {"iid": incident_id}).scalar() or 0)


def recent_incidents_for_link(db: Session, days: int) -> list[dict]:
    """개선의견과 연결할 최근 장애 (오탐 제외)."""
    return _rows(db.execute(text("""
        SELECT incident_id, title, symptoms, status FROM incident_alert
         WHERE status <> '오탐' AND last_reported_at >= now() - make_interval(days => :d)
         ORDER BY last_reported_at DESC LIMIT 200
    """), {"d": days}))


def create_improvement(db: Session, data: dict) -> dict:
    return _row(db.execute(text("""
        INSERT INTO improvement_opinion (consult_id, call_id, customer_id, customer_name, error_type, channel,
                                         title, content, customer_excerpt, related_incident_id)
        VALUES (:consult_id, :call_id, :customer_id, :customer_name, :error_type, :channel,
                :title, :content, :customer_excerpt, :related_incident_id)
        RETURNING *
    """), data))


def list_improvements(db: Session, date_from=None, date_to=None, limit: int = 100) -> list[dict]:
    conds, params = [], {"limit": limit}
    _date_conds("o.created_at", date_from, date_to, conds, params)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return _rows(db.execute(text(f"""
        SELECT o.*, h.agent_name, i.title AS related_title, i.status AS related_status
          FROM improvement_opinion o
          LEFT JOIN consult_history h ON h.consult_id = o.consult_id
          LEFT JOIN incident_alert i ON i.incident_id = o.related_incident_id
          {where}
         ORDER BY o.created_at DESC
         LIMIT :limit
    """), params))


def find_open_incidents(db: Session, error_type: str, window_min: int) -> list[dict]:
    return _rows(db.execute(text("""
        SELECT * FROM incident_alert
         WHERE error_type = :et
           AND status IN ('관찰', '접수', '확인중')
           AND last_reported_at >= now() - make_interval(mins => :win)
         ORDER BY last_reported_at DESC
    """), {"et": error_type, "win": window_min}))


def search_knowledge(db: Session, error_type: str | None = None) -> list[dict]:
    """해결/오탐 처리된 과거 장애 (RAG 지식베이스)."""
    cond = "AND error_type = :et" if error_type else ""
    return _rows(db.execute(text(f"""
        SELECT incident_id, title, error_type, channel, severity, status, symptoms,
               env_info, analysis, resolution, report_count, first_reported_at
          FROM incident_alert
         WHERE status IN ('해결', '오탐') {cond}
         ORDER BY first_reported_at DESC
         LIMIT 200
    """), {"et": error_type} if error_type else {}))


def list_incidents(db: Session, status: str | None = None, open_only: bool = False,
                   limit: int = 50, box: str | None = None, period: str | None = None,
                   top_grade: str = "P1", date_from=None, date_to=None) -> list[dict]:
    conds, params = [], {"limit": limit}
    _date_conds("i.created_at", date_from, date_to, conds, params)
    if box in BOX_SQL:
        conds.append(BOX_SQL[box])
        params["top"] = top_grade
    if period in PERIOD_SQL:
        conds.append(PERIOD_SQL[period])
    if status:
        conds.append("i.status = :st")
        params["st"] = status
    if open_only:
        conds.append("i.status IN ('관찰', '접수', '확인중')")
    where = ("WHERE " + " AND ".join(conds)) if conds else ""
    return _rows(db.execute(text(f"""
        SELECT i.*, coalesce(e.emp_name, o.owner_name) AS owner_name, coalesce(e.dept, o.dept) AS dept,
               coalesce(e.messenger_id, o.messenger_id) AS messenger_id, rv.emp_name AS resolver_name,
               {PROCESS_STATUS_SQL},
               (SELECT count(*) FROM messenger_log m WHERE m.incident_id = i.incident_id) AS message_count
          FROM incident_alert i
          LEFT JOIN biz_owner o ON o.owner_id = i.owner_id
          LEFT JOIN employee e ON e.emp_id = i.owner_emp_id
          LEFT JOIN employee rv ON rv.emp_id = i.resolved_by_emp_id
          {where}
         ORDER BY i.last_reported_at DESC
         LIMIT :limit
    """), params))


def get_incident(db: Session, incident_id: int, detail: bool = True) -> dict | None:
    inc = _row(db.execute(text(f"""
        SELECT i.*, coalesce(e.emp_name, o.owner_name) AS owner_name, coalesce(e.dept, o.dept) AS dept,
               coalesce(e.messenger_id, o.messenger_id) AS messenger_id,
               coalesce(e.duty_system, o.system_name) AS system_name, rv.emp_name AS resolver_name,
               {PROCESS_STATUS_SQL}
          FROM incident_alert i
          LEFT JOIN biz_owner o ON o.owner_id = i.owner_id
          LEFT JOIN employee e ON e.emp_id = i.owner_emp_id
          LEFT JOIN employee rv ON rv.emp_id = i.resolved_by_emp_id
         WHERE i.incident_id = :id
    """), {"id": incident_id}))
    if not inc or not detail:
        return inc
    inc["reports"] = _rows(db.execute(text("""
        SELECT r.report_id, r.similarity, r.created_at, h.consult_id, h.call_id,
               h.customer_name, h.channel, h.summary, h.agent_name
          FROM incident_report r JOIN consult_history h ON h.consult_id = r.consult_id
         WHERE r.incident_id = :id ORDER BY r.report_id
    """), {"id": incident_id}))
    inc["messages"] = list_messenger_logs(db, incident_id=incident_id)
    inc["actions"] = list_actions(db, incident_id)
    return inc


def monitor_counts(db: Session, period: str | None = None, top_grade: str = "P1",
                   date_from=None, date_to=None) -> dict:
    """장애 알림 모니터 건수 박스 (조회 기간 date_from~date_to, 예전 방식 period: today / 7d / all)."""
    cols = ", ".join(f"count(*) FILTER (WHERE {cond}) AS {key}" for key, cond in BOX_SQL.items())
    conds, params = [PERIOD_SQL.get(period, "TRUE")], {"top": top_grade}
    _date_conds("i.created_at", date_from, date_to, conds, params)
    return _row(db.execute(text(f"SELECT {cols} FROM incident_alert i WHERE {' AND '.join(conds)}"), params))


# =====================================================================
# 장애 처리 이력 (장애 상세정보 화면에서 IT담당자 등록)
# =====================================================================
def list_actions(db: Session, incident_id: int) -> list[dict]:
    return _rows(db.execute(text("""
        SELECT a.*, e.dept FROM incident_action a LEFT JOIN employee e ON e.emp_id = a.emp_id
         WHERE a.incident_id = :id ORDER BY a.action_id DESC
    """), {"id": incident_id}))


def add_action(db: Session, data: dict) -> dict:
    return _row(db.execute(text("""
        INSERT INTO incident_action (incident_id, process_status, status_before, status_after, content,
                                     emp_id, actor_login, actor_name)
        VALUES (:incident_id, :process_status, :status_before, :status_after, :content,
                :emp_id, :actor_login, :actor_name)
        RETURNING *
    """), data))


# =====================================================================
# 메신저 이력
# =====================================================================
def insert_messenger_log(db: Session, data: dict) -> dict:
    return _row(db.execute(text("""
        INSERT INTO messenger_log (incident_id, owner_id, receiver, receiver_name, title, body,
                                   transport, status, error_message, emp_id, recipient_type, link_url)
        VALUES (:incident_id, :owner_id, :receiver, :receiver_name, :title, :body,
                :transport, :status, :error_message, :emp_id, :recipient_type, :link_url)
        RETURNING *
    """), {"owner_id": None, "emp_id": None, "recipient_type": None, "link_url": None, **data}))


def list_messenger_logs(db: Session, incident_id: int | None = None, limit: int = 50) -> list[dict]:
    cond = "WHERE m.incident_id = :iid" if incident_id else ""
    params: dict[str, Any] = {"limit": limit}
    if incident_id:
        params["iid"] = incident_id
    return _rows(db.execute(text(f"""
        SELECT m.*, coalesce(e.dept, o.dept) AS dept, coalesce(e.duty_role, o.role) AS role
          FROM messenger_log m
          LEFT JOIN biz_owner o ON o.owner_id = m.owner_id
          LEFT JOIN employee e ON e.emp_id = m.emp_id
          {cond}
         ORDER BY m.msg_id DESC LIMIT :limit
    """), params))


# =====================================================================
# 에이전트 실행 로그
# =====================================================================
def create_run(db: Session, consult_id: int) -> int:
    return db.execute(text("INSERT INTO agent_run (consult_id) VALUES (:cid) RETURNING run_id"),
                      {"cid": consult_id}).scalar_one()


def finish_run(db: Session, run_id: int, status: str, outcome: str,
               incident_id: int | None, llm_used: bool) -> None:
    db.execute(text("""
        UPDATE agent_run SET status = :st, outcome = :oc, incident_id = :iid, llm_used = :llm,
                             finished_at = now()
         WHERE run_id = :id
    """), {"st": status, "oc": outcome[:200], "iid": incident_id, "llm": llm_used, "id": run_id})


def start_step(db: Session, run_id: int, seq: int, agent_name: str, message: str) -> int:
    return db.execute(text("""
        INSERT INTO agent_step (run_id, seq, agent_name, message) VALUES (:r, :s, :a, :m) RETURNING step_id
    """), {"r": run_id, "s": seq, "a": agent_name, "m": message}).scalar_one()


def finish_step(db: Session, step_id: int, status: str, message: str, output: dict) -> None:
    db.execute(text("""
        UPDATE agent_step SET status = :st, message = :m, output = CAST(:o AS jsonb), finished_at = now()
         WHERE step_id = :id
    """), {"st": status, "m": message, "o": json.dumps(output, ensure_ascii=False, default=str),
           "id": step_id})


def _attach_steps(db: Session, runs: list[dict]) -> list[dict]:
    if not runs:
        return runs
    ids = [r["run_id"] for r in runs]
    steps = _rows(db.execute(text("""
        SELECT *, (EXTRACT(EPOCH FROM (coalesce(finished_at, now()) - started_at)) * 1000)::int AS elapsed_ms
          FROM agent_step WHERE run_id = ANY(:ids) ORDER BY run_id, seq
    """), {"ids": ids}))
    by_run: dict[int, list] = {}
    for s in steps:
        by_run.setdefault(s["run_id"], []).append(s)
    for r in runs:
        r["steps"] = by_run.get(r["run_id"], [])
    return runs


def list_runs(db: Session, limit: int = 20) -> list[dict]:
    runs = _rows(db.execute(text("""
        SELECT r.*, h.customer_name, h.call_id, h.summary, h.channel
          FROM agent_run r LEFT JOIN consult_history h ON h.consult_id = r.consult_id
         ORDER BY r.run_id DESC LIMIT :limit
    """), {"limit": limit}))
    return _attach_steps(db, runs)


def get_run(db: Session, run_id: int) -> dict | None:
    run = _row(db.execute(text("""
        SELECT r.*, h.customer_name, h.call_id, h.summary, h.channel
          FROM agent_run r LEFT JOIN consult_history h ON h.consult_id = r.consult_id
         WHERE r.run_id = :id
    """), {"id": run_id}))
    return _attach_steps(db, [run])[0] if run else None


# =====================================================================
# 모니터 요약
# =====================================================================
def dashboard_summary(db: Session) -> dict:
    return _row(db.execute(text("""
        SELECT
          (SELECT count(*) FROM consult_history WHERE created_at >= date_trunc('day', now())) AS consults_today,
          (SELECT count(*) FROM agent_run WHERE started_at >= date_trunc('day', now())) AS runs_today,
          (SELECT count(*) FROM incident_alert WHERE created_at >= date_trunc('day', now())) AS incidents_today,
          (SELECT count(*) FROM incident_alert WHERE status IN ('접수', '확인중')) AS open_incidents,
          (SELECT count(*) FROM incident_alert WHERE status = '관찰') AS watching_incidents,
          (SELECT count(*) FROM incident_alert WHERE mass_signal AND status IN ('관찰', '접수', '확인중')) AS mass_signals,
          (SELECT count(*) FROM messenger_log WHERE sent_at >= date_trunc('day', now())) AS messages_today,
          (SELECT count(*) FROM agent_run WHERE status = 'RUNNING') AS running
    """)))
