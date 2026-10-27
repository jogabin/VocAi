"""VOC 장애 알림 API

- STT원문조회 API        GET  /api/stt, /api/stt/{call_id}
  상담요약 초안           POST /api/stt/{call_id}/summary-draft  (상담사 관점 요약, LLM → 규칙 기반 대체)
- 상담이력조회 API        GET  /api/consults, /api/consults/{consult_id}
  상담이력 등록           POST /api/consults   (등록 후 장애 알림 에이전트 자동 실행)
- 업무담당자조회 API      GET  /api/owners
- 장애알림정보등록 API    POST /api/incidents   (+ 조회 GET, 상태변경 PATCH)
- 메신저전송 API          POST /api/messenger/send (+ 이력 GET /api/messenger/logs)
- 에이전트 실행 이력      GET  /api/agent-runs, /api/agent-runs/{run_id}, POST /api/agent-runs (재실행)
- 모니터 요약             GET  /api/monitor/summary
- 에이전트 그래프 구조    GET  /api/agent-graph   (LangGraph 흐름도 / mermaid)
- 장애등급 판별기준       GET  /api/severity-criteria, POST·PATCH .../grades | base-rules | adjust-rules
"""
from datetime import date, datetime, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.agents import graph, llm, pipeline, summary
from app.database import DB, SessionLocal
from app.services import auth, criteria, messenger, rag, repo

router = APIRouter(tags=["voc"])

ErrorType = Literal["로그인", "인증", "조회", "이체", "UI오류", "기타"]
Severity = Literal["P1", "P2", "P3", "P4"]
IncidentStatus = Literal["관찰", "접수", "확인중", "해결", "오탐"]


# =====================================================================
# STT 원문조회 API
# =====================================================================
@router.get("/stt", summary="STT 통화 목록 (상담현황: consult_status=진행|상담완료, 통화일 date_from~date_to)")
def list_stt(db: DB, keyword: str | None = None, registered: bool | None = None,
             consult_status: Literal["진행", "상담완료"] | None = None,
             date_from: date | None = None, date_to: date | None = None,
             limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)):
    return repo.list_stt_calls(db, keyword, registered, limit, offset, consult_status, date_from, date_to)


@router.get("/stt/{call_id}", summary="STT 원문 조회 (발화 목록 포함)")
def get_stt(call_id: str, db: DB):
    call = repo.get_stt_call(db, call_id)
    if not call:
        raise HTTPException(404, "STT 통화를 찾을 수 없습니다.")
    return call


@router.post("/stt/{call_id}/summary-draft", summary="상담요약 초안 작성 (STT 원문 전체 → 상담사 관점 요약)")
def summary_draft(call_id: str, db: DB, _: auth.ConsultUser):
    call = repo.get_stt_call(db, call_id)
    if not call:
        raise HTTPException(404, "STT 통화를 찾을 수 없습니다.")
    if not any(u["speaker"] == "CUSTOMER" for u in call.get("utterances") or []):
        raise HTTPException(400, "고객 대화가 없어 상담요약 초안을 만들 수 없습니다.")
    return summary.draft(call)


class UtteranceIn(BaseModel):
    speaker: Literal["CUSTOMER", "AGENT"]
    text: str = Field(min_length=1, max_length=1000)


@router.post("/stt/{call_id}/utterances", status_code=201, summary="STT 대화 추가 (시스템관리자, 상담 진행 중인 통화만)")
def add_utterance(call_id: str, body: UtteranceIn, db: DB, admin: auth.SysAdminUser):
    call = repo.get_stt_call(db, call_id)
    if not call:
        raise HTTPException(404, "STT 통화를 찾을 수 없습니다.")
    if call.get("consult_status") == "상담완료":
        raise HTTPException(409, "상담완료된 통화에는 대화를 추가할 수 없습니다.")
    row = repo.add_utterance(db, call_id, body.speaker, body.text.strip(), admin["login_id"])
    db.commit()
    return row


# =====================================================================
# 상담이력조회 / 등록 API
# =====================================================================
class ConsultIn(BaseModel):
    call_id: str | None = None
    customer_id: str | None = Field(None, description="call_id 를 주면 STT 통화의 고객번호로 고정")
    customer_name: str | None = None
    agent_name: str | None = None
    consult_type: Literal["전산오류문의", "일반문의", "불만", "기타"] = "전산오류문의"
    channel: Literal["앱", "웹", "ARS", "기타"] | None = None
    summary: str = Field(min_length=2)
    memo: str | None = None
    result_status: Literal["완료", "이관", "보류"] = "완료"
    run_agent: bool = True


@router.get("/consults", summary="상담이력 목록")
def list_consults(db: DB, keyword: str | None = None, consult_type: str | None = None,
                  limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
    return repo.list_consults(db, keyword, consult_type, limit, offset)


@router.get("/consults/{consult_id}", summary="상담이력 단건")
def get_consult(consult_id: int, db: DB):
    row = repo.get_consult(db, consult_id)
    if not row:
        raise HTTPException(404, "상담이력을 찾을 수 없습니다.")
    return row


@router.post("/consults", status_code=201, summary="상담이력 등록 + 장애 알림 에이전트 실행")
def create_consult(body: ConsultIn, db: DB, background: BackgroundTasks, user: auth.ConsultUser):
    data = body.model_dump(exclude={"run_agent"})
    call = None
    if body.call_id:
        call = repo.get_stt_call(db, body.call_id)
        if not call:
            raise HTTPException(400, "존재하지 않는 STT 통화입니다.")
        if call.get("consult_status") == "상담완료":
            raise HTTPException(409, "이미 상담완료된 통화입니다. 등록된 상담이력만 확인할 수 있습니다.")
        # 고객번호 · 고객명 · 상담사는 STT 통화 정보로 고정 (화면에서 수정 불가 항목)
        data.update(customer_id=call["customer_id"], customer_name=call["customer_name"],
                    agent_name=call["agent_name"])
    if not data.get("customer_id"):
        raise HTTPException(400, "고객번호(customer_id)가 필요합니다.")
    data["registered_by"] = user.get("login_id")
    consult = repo.create_consult(db, data)
    if call:
        repo.complete_call(db, call["call_id"])          # 상담진행 → 상담완료
    db.commit()
    run_id = None
    if body.run_agent:
        run_id = pipeline.start_run(db, consult["consult_id"])
        background.add_task(pipeline.execute, run_id, consult["consult_id"])
    return {"consult": consult, "run_id": run_id}


# =====================================================================
# 업무담당자조회 API
# =====================================================================
@router.get("/owners", summary="업무담당자 조회 (오류유형별)")
def list_owners(db: DB, error_type: ErrorType | None = None, on_duty_only: bool = False):
    return repo.list_owners(db, error_type, on_duty_only)


# =====================================================================
# 장애알림정보등록 API
# =====================================================================
class IncidentIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    error_type: ErrorType
    channel: Literal["앱", "웹", "ARS", "기타"] | None = None
    severity: Severity = "P3"
    status: IncidentStatus = "접수"
    symptoms: str | None = None
    env_info: dict = Field(default_factory=dict)
    analysis: str | None = None
    owner_emp_id: int | None = None
    consult_id: int | None = None


class IncidentPatch(BaseModel):
    status: IncidentStatus | None = None
    severity: Severity | None = None
    owner_id: int | None = None
    resolution: str | None = None


Box = Literal["registered", "urgent", "messaged", "same_type", "resolved"]
Period = Literal["today", "7d", "all"]


@router.get("/incidents", summary="장애 알림 목록 (box: 모니터 건수 박스, 등록일 date_from~date_to)")
def list_incidents(db: DB, status: IncidentStatus | None = None, open_only: bool = False,
                   box: Box | None = None, period: Period | None = None,
                   date_from: date | None = None, date_to: date | None = None,
                   limit: int = Query(50, ge=1, le=300)):
    top = criteria.load(db).codes()[0]
    return repo.list_incidents(db, status, open_only, limit, box, period, top, date_from, date_to)


@router.get("/improvements", summary="개선의견 목록 (알림 없이 기록만, 등록일 date_from~date_to)")
def list_improvements(db: DB, date_from: date | None = None, date_to: date | None = None,
                      limit: int = Query(100, ge=1, le=300)):
    return repo.list_improvements(db, date_from, date_to, limit)


@router.get("/incidents/{incident_id}", summary="장애 알림 상세 (제보/메신저 이력 포함)")
def get_incident(incident_id: int, db: DB):
    inc = repo.get_incident(db, incident_id)
    if not inc:
        raise HTTPException(404, "장애 정보를 찾을 수 없습니다.")
    return inc


@router.post("/incidents", status_code=201, summary="장애 알림 정보 등록")
def create_incident(body: IncidentIn, db: DB):
    data = body.model_dump(exclude={"consult_id"})
    if data["owner_emp_id"] is None:              # 인사정보에서 해당 유형 담당 IT담당자
        staff = repo.find_it_staff(db, body.error_type)
        data["owner_emp_id"] = staff[0]["emp_id"] if staff else None
    inc = repo.create_incident(db, data)
    if body.consult_id:
        repo.add_incident_report(db, inc["incident_id"], body.consult_id, None)
    db.commit()
    return inc


# =====================================================================
# 장애 처리 등록 (장애 상세정보 화면: IT담당자 권한만)
# =====================================================================
class ActionIn(BaseModel):
    process_status: Literal["대기중", "진행중", "미대상", "처리완료"]
    content: str | None = Field(None, max_length=4000, description="처리 내용")


@router.post("/incidents/{incident_id}/actions", status_code=201, summary="장애 처리 상태·처리 내용 등록")
def add_incident_action(incident_id: int, body: ActionIn, db: DB, background: BackgroundTasks,
                        user: auth.CurrentUser):
    if not auth.is_it_staff(user):
        raise HTTPException(403, "장애 처리 등록은 IT담당자 권한만 할 수 있습니다.")
    inc = repo.get_incident(db, incident_id, detail=False)
    if not inc:
        raise HTTPException(404, "장애 정보를 찾을 수 없습니다.")
    content = (body.content or "").strip() or None
    if body.process_status in ("처리완료", "미대상") and not content:
        raise HTTPException(400, f"'{body.process_status}' 등록 시 처리 내용을 입력하세요. (유사 장애 분석에 사용)")
    if body.process_status == "대기중":
        new_status = "접수" if inc.get("notified_severity") else "관찰"
    else:
        new_status = repo.PROCESS_TO_STATUS[body.process_status]
    fields: dict = {"status": new_status}
    if content:
        fields["resolution"] = content
    if new_status in ("해결", "오탐"):
        fields["resolved_at"] = datetime.now(timezone.utc)
        if user.get("emp_id"):
            fields["resolved_by_emp_id"] = user["emp_id"]
    else:
        fields["resolved_at"] = None
    repo.update_incident(db, incident_id, fields)
    repo.add_action(db, {"incident_id": incident_id, "process_status": body.process_status,
                         "status_before": inc["status"], "status_after": new_status, "content": content,
                         "emp_id": user.get("emp_id"), "actor_login": user.get("login_id") or "-",
                         "actor_name": user.get("emp_name") or user.get("user_name")})
    db.commit()
    if new_status in ("해결", "오탐"):
        background.add_task(_embed_incident, incident_id)       # 처리 결과를 유사사례 검색에 반영
    return repo.get_incident(db, incident_id)


def _embed_incident(incident_id: int) -> None:
    """해결/오탐 처리된 장애를 RAG 지식베이스(임베딩)에 반영."""
    with SessionLocal() as db:
        rag.ensure_embeddings(db, [incident_id])
        db.commit()


@router.patch("/incidents/{incident_id}", summary="장애 처리 상태/결과 갱신 (IT담당자 피드백)")
def update_incident(incident_id: int, body: IncidentPatch, db: DB, background: BackgroundTasks):
    if not repo.get_incident(db, incident_id, detail=False):
        raise HTTPException(404, "장애 정보를 찾을 수 없습니다.")
    data = body.model_dump(exclude_none=True)
    if data.get("status") in ("해결", "오탐"):
        data["resolved_at"] = datetime.now(timezone.utc)
    repo.update_incident(db, incident_id, data)
    db.commit()
    if data.get("status") in ("해결", "오탐") or "resolution" in data:
        background.add_task(_embed_incident, incident_id)
    return repo.get_incident(db, incident_id)


# =====================================================================
# 메신저전송 API
# =====================================================================
class MessengerIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    incident_id: int | None = None
    emp_ids: list[int] = Field(default_factory=list, description="인사정보 employee.emp_id 목록")
    owner_ids: list[int] = Field(default_factory=list, description="(이전 방식) biz_owner.owner_id 목록")
    receivers: list[str] = Field(default_factory=list, description="메신저 ID 직접 지정")


@router.post("/messenger/send", summary="사내 메신저 전송")
def send_messenger(body: MessengerIn, db: DB):
    targets = []
    if body.emp_ids:
        emps = {e["emp_id"]: e for e in repo.employees_by_ids(db, body.emp_ids)}
        for eid in body.emp_ids:
            e = emps.get(eid)
            if not e or not e.get("messenger_id"):
                raise HTTPException(400, f"메신저 ID가 있는 직원이 아닙니다: emp_id={eid}")
            targets.append({"receiver": e["messenger_id"], "receiver_name": e["emp_name"], "emp_id": eid})
    if body.owner_ids:
        owners = {o["owner_id"]: o for o in repo.list_owners(db)}
        for oid in body.owner_ids:
            if oid not in owners:
                raise HTTPException(400, f"존재하지 않는 담당자 owner_id={oid}")
            o = owners[oid]
            targets.append({"receiver": o["messenger_id"], "receiver_name": o["owner_name"], "owner_id": oid})
    targets += [{"receiver": r, "receiver_name": None, "owner_id": None} for r in body.receivers]
    if not targets:
        raise HTTPException(400, "수신자(emp_ids 또는 receivers)를 지정하세요.")
    logs = messenger.send_message(db, targets, body.title, body.body, body.incident_id)
    db.commit()
    return logs


@router.get("/messenger/telegram/chats", summary="텔레그램 chat_id 확인 (봇에게 최근 메시지를 보낸 대화)")
def telegram_chats():
    try:
        return messenger.telegram_chats()
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.get("/messenger/logs", summary="메신저 전송 이력")
def messenger_logs(db: DB, incident_id: int | None = None, limit: int = Query(50, ge=1, le=200)):
    return repo.list_messenger_logs(db, incident_id, limit)


# =====================================================================
# 에이전트 실행 이력 / 모니터
# =====================================================================
class RerunIn(BaseModel):
    consult_id: int


@router.get("/agent-runs", summary="에이전트 실행 이력 (단계 포함)")
def list_runs(db: DB, limit: int = Query(20, ge=1, le=100)):
    return repo.list_runs(db, limit)


@router.get("/agent-runs/{run_id}", summary="에이전트 실행 단건")
def get_run(run_id: int, db: DB):
    run = repo.get_run(db, run_id)
    if not run:
        raise HTTPException(404, "실행 이력을 찾을 수 없습니다.")
    return run


@router.post("/agent-runs", status_code=201, summary="상담이력에 대해 에이전트 재실행 (시스템관리자)")
def rerun(body: RerunIn, db: DB, background: BackgroundTasks, _: auth.SysAdminUser):
    if not repo.get_consult(db, body.consult_id):
        raise HTTPException(404, "상담이력을 찾을 수 없습니다.")
    run_id = pipeline.start_run(db, body.consult_id)
    background.add_task(pipeline.execute, run_id, body.consult_id)
    return {"run_id": run_id}


@router.get("/monitor/counts", summary="장애 알림 모니터 건수 박스 (등록일 date_from~date_to)")
def monitor_counts(db: DB, period: Period | None = None, date_from: date | None = None, date_to: date | None = None):
    cr = criteria.load(db)
    top = cr.codes()[0]
    return {**repo.monitor_counts(db, period, top, date_from, date_to), "period": period,
            "date_from": date_from, "date_to": date_to, "top_grade": top, "top_grade_label": cr.label(top)}


@router.get("/monitor/summary", summary="모니터 화면 요약 지표")
def monitor_summary(db: DB):
    return {**repo.dashboard_summary(db), "llm_enabled": llm.enabled(), "llm_desc": llm.describe(),
            "rag": rag.status(db),
            "messenger_mode": messenger.provider(),
            "severity_label": {g["grade_code"]: g["grade_name"] for g in criteria.load(db).grades},
            "criteria_version": criteria.load(db).version}


@router.get("/agent-graph", summary="LangGraph 에이전트 그래프 구조 (흐름도/mermaid)")
def agent_graph():
    return {**graph.GRAPH_SPEC, "mermaid": graph.mermaid()}


# =====================================================================
# 장애등급 판별기준 (심각도 판별 에이전트가 사용하는 기준 정보)
# =====================================================================
GradeCode = str
RuleType = Literal["KEYWORD", "REPORT_COUNT", "MASS_SIGNAL", "FALSE_POSITIVE"]
ActionType = Literal["RAISE", "SET_GRADE", "RAISE_TO", "LOWER_TO", "FALSE_POSITIVE"]


class Audit(BaseModel):
    updated_by: str = Field("admin", max_length=50, description="수정자")
    change_reason: str | None = Field(None, description="변경 사유")


class GradeIn(Audit):
    grade_code: str = Field(pattern=r"^P\d$")
    grade_name: str = Field(min_length=1, max_length=20)
    grade_order: int = Field(ge=1)
    definition: str = Field(min_length=2)
    judge_examples: str | None = None
    notify_min_reports: int | None = Field(None, ge=1, description="NULL = 알림 없음")
    recipient_roles: str = Field("", description="'담당,부담당,팀장'")
    target_ack_min: int | None = Field(None, ge=0)
    target_resolve_min: int | None = Field(None, ge=0)
    message_prefix: str = "[장애알림]"
    use_yn: bool = True


class GradePatch(Audit):
    grade_name: str | None = None
    grade_order: int | None = Field(None, ge=1)
    definition: str | None = None
    judge_examples: str | None = None
    notify_min_reports: int | None = Field(None, ge=1)
    recipient_roles: str | None = None
    target_ack_min: int | None = Field(None, ge=0)
    target_resolve_min: int | None = Field(None, ge=0)
    message_prefix: str | None = None
    use_yn: bool | None = None
    valid_to: str | None = None
    clear_notify: bool = Field(False, description="true 이면 notify_min_reports 를 비워 알림 없음으로 변경")


class BaseRuleIn(Audit):
    error_type: ErrorType
    channel: Literal["앱", "웹", "ARS", "기타"] | None = None
    system_name: str | None = None
    base_grade: GradeCode
    rationale: str | None = None
    use_yn: bool = True


class BaseRulePatch(Audit):
    channel: Literal["앱", "웹", "ARS", "기타"] | None = None
    system_name: str | None = None
    base_grade: GradeCode | None = None
    rationale: str | None = None
    use_yn: bool | None = None
    valid_to: str | None = None


class AdjustRuleIn(Audit):
    rule_code: str = Field(pattern=r"^[A-Z0-9_]{2,30}$")
    rule_name: str = Field(min_length=1, max_length=100)
    rule_type: RuleType
    keywords: list[str] | None = None
    threshold: int | None = Field(None, ge=1)
    action_type: ActionType
    raise_steps: int | None = Field(None, ge=1)
    target_grade: GradeCode | None = None
    condition_grade: GradeCode | None = None
    target_error_type: ErrorType | None = None
    apply_order: int = 100
    description: str | None = None
    use_yn: bool = True


class AdjustRulePatch(Audit):
    rule_name: str | None = None
    keywords: list[str] | None = None
    threshold: int | None = Field(None, ge=1)
    action_type: ActionType | None = None
    raise_steps: int | None = Field(None, ge=1)
    target_grade: GradeCode | None = None
    condition_grade: GradeCode | None = None
    target_error_type: ErrorType | None = None
    apply_order: int | None = None
    description: str | None = None
    use_yn: bool | None = None
    valid_to: str | None = None


def _need_tables(db):
    if not criteria.tables_exist(db):
        raise HTTPException(409, "판별기준 테이블이 없습니다. sql/04_severity_criteria.sql 을 먼저 실행하세요.")


def _check_grade(db, *codes):
    valid = {g["grade_code"] for g in criteria.list_all(db)["grades"]}
    for c in codes:
        if c and c not in valid:
            raise HTTPException(400, f"존재하지 않는 등급코드: {c}")


def _audit(body: Audit, exclude: set = frozenset(), admin: dict | None = None) -> tuple[dict, str, str | None]:
    """수정자는 로그인한 관리자 아이디로 기록 (개발모드에서는 입력값)."""
    data = body.model_dump(exclude_unset=True, exclude={"updated_by", "change_reason", *exclude})
    user = admin.get("login_id") if admin and admin.get("user_id") else body.updated_by
    return data, user, body.change_reason


@router.get("/severity-criteria", summary="장애등급 판별기준 전체 조회 (현재 적용 버전 포함)")
def get_criteria(db: DB, admin: auth.CriteriaUser):
    return criteria.list_all(db)


@router.post("/severity-criteria/grades", status_code=201, summary="등급 정의 등록")
def create_grade(body: GradeIn, db: DB, admin: auth.CriteriaUser):
    _need_tables(db)
    data, user, reason = _audit(body, admin=admin)
    data.update(grade_code=body.grade_code)
    row = criteria.save_grade(db, data, user=user, reason=reason)
    db.commit()
    return row


@router.patch("/severity-criteria/grades/{grade_code}", summary="등급 정의 수정")
def update_grade(grade_code: str, body: GradePatch, db: DB, admin: auth.CriteriaUser):
    _need_tables(db)
    data, user, reason = _audit(body, {"clear_notify"}, admin=admin)
    if body.clear_notify:
        data["notify_min_reports"] = None
    row = criteria.save_grade(db, data, grade_code, user=user, reason=reason)
    if not row:
        raise HTTPException(404, "등급을 찾을 수 없습니다.")
    db.commit()
    return row


@router.post("/severity-criteria/base-rules", status_code=201, summary="기본 등급 규칙 등록")
def create_base_rule(body: BaseRuleIn, db: DB, admin: auth.CriteriaUser):
    _need_tables(db)
    _check_grade(db, body.base_grade)
    data, user, reason = _audit(body, admin=admin)
    row = criteria.save_base_rule(db, data, user=user, reason=reason)
    db.commit()
    return row


@router.patch("/severity-criteria/base-rules/{rule_id}", summary="기본 등급 규칙 수정")
def update_base_rule(rule_id: int, body: BaseRulePatch, db: DB, admin: auth.CriteriaUser):
    _need_tables(db)
    _check_grade(db, body.base_grade)
    data, user, reason = _audit(body, admin=admin)
    row = criteria.save_base_rule(db, data, rule_id, user=user, reason=reason)
    if not row:
        raise HTTPException(404, "규칙을 찾을 수 없습니다.")
    db.commit()
    return row


@router.post("/severity-criteria/adjust-rules", status_code=201, summary="등급 조정 규칙 등록")
def create_adjust_rule(body: AdjustRuleIn, db: DB, admin: auth.CriteriaUser):
    _need_tables(db)
    _check_grade(db, body.target_grade, body.condition_grade)
    data, user, reason = _audit(body, admin=admin)
    data.update(rule_code=body.rule_code)
    row = criteria.save_adjust_rule(db, data, user=user, reason=reason)
    db.commit()
    return row


@router.patch("/severity-criteria/adjust-rules/{rule_code}", summary="등급 조정 규칙 수정 (use_yn=false 로 끄기)")
def update_adjust_rule(rule_code: str, body: AdjustRulePatch, db: DB, admin: auth.CriteriaUser):
    _need_tables(db)
    _check_grade(db, body.target_grade, body.condition_grade)
    data, user, reason = _audit(body, admin=admin)
    row = criteria.save_adjust_rule(db, data, rule_code, user=user, reason=reason)
    if not row:
        raise HTTPException(404, "규칙을 찾을 수 없습니다.")
    db.commit()
    return row
