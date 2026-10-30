"""사용자관리 / 인사정보 관리 API

사용자관리 (시스템관리자 전용) — 권한: 상담사 / 센터관리자 / IT담당자 / 시스템관리자
- GET   /voc-users                 사용자 목록 (keyword, auth_role, use_yn)
- GET   /voc-users/{user_id}       사용자 상세
- POST  /voc-users                 사용자 등록
- PATCH /voc-users/{user_id}       사용자 수정 (비밀번호 초기화, 잠금 해제 포함)

인사정보 조회 API / 관리
- GET   /employees                 직원 목록 (group, keyword, error_type, on_duty, use_yn)  ← 로그인 사용자 누구나
- GET   /employees/{emp_id}        직원 상세 (연결된 로그인 계정 포함)
- POST  /employees                 직원 등록 (시스템관리자)
- PATCH /employees/{emp_id}        직원 수정 (시스템관리자)

데이터 초기화 (시스템관리자 전용)
- GET   /admin/demo-reset          마지막 시연 데이터 초기화 기록 · 현재 건수
- POST  /admin/demo-reset          시연 데이터 초기화 (confirm="초기화" 를 보내야 실행)
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import text

from app import db_init
from app.database import DB, engine
from app.services import auth

router = APIRouter(tags=["admin"])

AuthRole = Literal["상담사", "센터관리자", "IT담당자", "시스템관리자"]
EmpGroup = Literal["상담사", "센터관리자", "IT담당자"]
DutyRole = Literal["담당", "부담당", "팀장"]
ErrorType = Literal["로그인", "인증", "조회", "이체", "UI오류", "기타"]


def _update(db, table: str, pk: str, key, data: dict, user: str) -> dict | None:
    if data:
        sets = ", ".join(f"{c} = :{c}" for c in data)
        params = {**data, "_k": key, "_u": user}
        row = db.execute(text(f"UPDATE {table} SET {sets}, updated_by = :_u, updated_at = now() "
                              f"WHERE {pk} = :_k RETURNING {pk}"), params).mappings().first()
    else:
        row = db.execute(text(f"SELECT {pk} FROM {table} WHERE {pk} = :_k"), {"_k": key}).mappings().first()
    return dict(row) if row else None


# =====================================================================
# 사용자관리
# =====================================================================
class UserIn(BaseModel):
    login_id: str = Field(pattern=r"^[A-Za-z0-9_.\-]{3,30}$")
    user_name: str = Field(min_length=1, max_length=50)
    auth_role: AuthRole = "상담사"
    emp_id: int | None = None
    email: str | None = Field(None, max_length=100)
    password: str = Field(max_length=100)
    use_yn: bool = True


class UserPatch(BaseModel):
    user_name: str | None = Field(None, min_length=1, max_length=50)
    auth_role: AuthRole | None = None
    emp_id: int | None = None
    email: str | None = Field(None, max_length=100)
    use_yn: bool | None = None
    new_password: str | None = Field(None, max_length=100, description="입력 시 비밀번호 초기화")
    unlock: bool = Field(False, description="true 이면 로그인 실패 잠금 해제")


def _check_emp(db, emp_id):
    if emp_id is not None and not db.execute(text("SELECT 1 FROM employee WHERE emp_id = :e"), {"e": emp_id}).first():
        raise HTTPException(400, "연결할 직원 정보가 없습니다.")


@router.get("/voc-users", summary="사용자 목록")
def list_users(db: DB, _: auth.AdminUser, keyword: str | None = None, auth_role: AuthRole | None = None,
               use_yn: bool | None = None, limit: int = Query(200, ge=1, le=500)):
    cond, params = [], {"limit": limit}
    if keyword:
        cond.append("(u.login_id ILIKE :kw OR u.user_name ILIKE :kw OR e.dept ILIKE :kw)")
        params["kw"] = f"%{keyword.strip()}%"
    if auth_role:
        cond.append("u.auth_role = :role")
        params["role"] = auth_role
    if use_yn is not None:
        cond.append("u.use_yn = :use")
        params["use"] = use_yn
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    rows = db.execute(text(f"""SELECT {auth.USER_COLS} FROM voc_user u LEFT JOIN employee e ON e.emp_id = u.emp_id
                               {where} ORDER BY u.user_id LIMIT :limit"""), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/voc-users/{user_id}", summary="사용자 상세")
def get_user(user_id: int, db: DB, _: auth.AdminUser):
    user = auth.get_user(db, user_id)
    if not user:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    return user


@router.post("/voc-users", status_code=201, summary="사용자 등록")
def create_user(body: UserIn, db: DB, admin: auth.AdminUser):
    if db.execute(text("SELECT 1 FROM voc_user WHERE login_id = :l"), {"l": body.login_id}).first():
        raise HTTPException(409, f"이미 사용 중인 아이디입니다: {body.login_id}")
    auth.check_password_rule(body.password)
    _check_emp(db, body.emp_id)
    row = db.execute(text("""
        INSERT INTO voc_user (login_id, password_hash, user_name, auth_role, emp_id, email, use_yn, created_by, updated_by)
        VALUES (:login_id, :pw, :user_name, :auth_role, :emp_id, :email, :use_yn, :by, :by) RETURNING user_id"""),
        {**body.model_dump(exclude={"password"}), "pw": auth.hash_password(body.password),
         "by": admin["login_id"]}).mappings().first()
    db.commit()
    return auth.get_user(db, row["user_id"])


@router.patch("/voc-users/{user_id}", summary="사용자 수정")
def update_user(user_id: int, body: UserPatch, db: DB, admin: auth.AdminUser):
    data = body.model_dump(exclude_unset=True, exclude={"new_password", "unlock"})
    is_self = admin.get("user_id") == user_id
    demote = "auth_role" in data and data["auth_role"] != auth.SYS_ADMIN
    if is_self and (data.get("use_yn") is False or demote):
        raise HTTPException(400, "본인 계정의 사용 중지나 시스템관리자 권한 해제는 할 수 없습니다.")
    target = db.execute(text("SELECT auth_role FROM voc_user WHERE user_id = :id"), {"id": user_id}).scalar()
    if target == auth.SYS_ADMIN and (data.get("use_yn") is False or demote):
        others = db.execute(text("""SELECT count(*) FROM voc_user
                                     WHERE auth_role = :r AND use_yn AND user_id <> :id"""),
                            {"r": auth.SYS_ADMIN, "id": user_id}).scalar()
        if not others:
            raise HTTPException(400, "사용 중인 시스템관리자가 최소 1명은 있어야 합니다.")
    if "emp_id" in data:
        _check_emp(db, data["emp_id"])
    if body.new_password:
        auth.check_password_rule(body.new_password)
        data.update(password_hash=auth.hash_password(body.new_password), fail_count=0)
    if body.unlock:
        data["fail_count"] = 0
    if not _update(db, "voc_user", "user_id", user_id, data, admin["login_id"]):
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    if body.new_password:
        db.execute(text("UPDATE voc_user SET pw_changed_at = now() WHERE user_id = :id"), {"id": user_id})
    if body.new_password or data.get("use_yn") is False:
        auth.revoke_user_sessions(db, user_id)          # 비밀번호 초기화·사용 중지 시 기존 로그인 종료
    db.commit()
    return auth.get_user(db, user_id)


# =====================================================================
# 인사정보
# =====================================================================
EMP_COLS = """e.emp_id, e.emp_no, e.emp_name, e.emp_group, e.dept, e.position, e.duty_role, e.duty_error_types,
              e.duty_system, e.duty_detail, e.messenger_id, e.phone, e.email, e.on_duty, e.use_yn,
              e.created_at, e.updated_by, e.updated_at"""


class EmployeeIn(BaseModel):
    emp_no: str = Field(pattern=r"^[A-Za-z0-9\-]{2,20}$")
    emp_name: str = Field(min_length=1, max_length=50)
    emp_group: EmpGroup
    dept: str | None = Field(None, max_length=50)
    position: str | None = Field(None, max_length=30)
    duty_role: DutyRole | None = None
    duty_error_types: list[ErrorType] = []
    duty_system: str | None = Field(None, max_length=100)
    duty_detail: str | None = None
    messenger_id: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    on_duty: bool = True
    use_yn: bool = True


class EmployeePatch(BaseModel):
    emp_name: str | None = Field(None, min_length=1, max_length=50)
    emp_group: EmpGroup | None = None
    dept: str | None = Field(None, max_length=50)
    position: str | None = Field(None, max_length=30)
    duty_role: DutyRole | None = None
    duty_error_types: list[ErrorType] | None = None
    duty_system: str | None = Field(None, max_length=100)
    duty_detail: str | None = None
    messenger_id: str | None = Field(None, max_length=50)
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    on_duty: bool | None = None
    use_yn: bool | None = None


def _normalize_duty(data: dict, group: str) -> None:
    """IT담당자는 알림 역할·담당 오류유형·메신저ID 필수, 그 외 그룹은 알림 대상 정보를 비움."""
    if group == "IT담당자":
        if not data.get("duty_role"):
            raise HTTPException(400, "IT담당자는 알림 역할(담당/부담당/팀장)을 지정해야 합니다.")
        if not data.get("duty_error_types"):
            raise HTTPException(400, "IT담당자는 담당 오류유형을 1개 이상 지정해야 합니다.")
        if not data.get("messenger_id"):
            raise HTTPException(400, "IT담당자는 장애 알림을 받을 메신저 ID가 필요합니다.")
    else:
        data["duty_role"] = None
        data["duty_error_types"] = []


def _get_employee(db, emp_id: int) -> dict | None:
    row = db.execute(text(f"SELECT {EMP_COLS} FROM employee e WHERE e.emp_id = :id"), {"id": emp_id}).mappings().first()
    if not row:
        return None
    emp = dict(row)
    emp["users"] = [dict(r) for r in db.execute(text(
        "SELECT user_id, login_id, auth_role, use_yn FROM voc_user WHERE emp_id = :id ORDER BY user_id"),
        {"id": emp_id}).mappings().all()]
    return emp


@router.get("/employees", summary="인사정보 조회 (직원 목록)")
def list_employees(db: DB, _: auth.CurrentUser, group: EmpGroup | None = None, keyword: str | None = None,
                   error_type: ErrorType | None = None, on_duty: bool | None = None, use_yn: bool | None = None,
                   limit: int = Query(300, ge=1, le=1000)):
    cond, params = [], {"limit": limit}
    if group:
        cond.append("e.emp_group = :g")
        params["g"] = group
    if keyword:
        cond.append("(e.emp_name ILIKE :kw OR e.emp_no ILIKE :kw OR e.dept ILIKE :kw "
                    "OR e.duty_system ILIKE :kw OR e.duty_detail ILIKE :kw)")
        params["kw"] = f"%{keyword.strip()}%"
    if error_type:
        cond.append(":et = ANY(e.duty_error_types)")
        params["et"] = error_type
    if on_duty is not None:
        cond.append("e.on_duty = :od")
        params["od"] = on_duty
    if use_yn is not None:
        cond.append("e.use_yn = :use")
        params["use"] = use_yn
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    rows = db.execute(text(f"""
        SELECT {EMP_COLS} FROM employee e {where}
         ORDER BY CASE e.emp_group WHEN '센터관리자' THEN 1 WHEN '상담사' THEN 2 ELSE 3 END,
                  e.dept NULLS LAST,
                  CASE e.duty_role WHEN '팀장' THEN 1 WHEN '담당' THEN 2 WHEN '부담당' THEN 3 ELSE 4 END,
                  e.emp_no
         LIMIT :limit"""), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/employees/{emp_id}", summary="직원 상세")
def get_employee(emp_id: int, db: DB, _: auth.CurrentUser):
    emp = _get_employee(db, emp_id)
    if not emp:
        raise HTTPException(404, "직원 정보를 찾을 수 없습니다.")
    return emp


@router.post("/employees", status_code=201, summary="직원 등록")
def create_employee(body: EmployeeIn, db: DB, admin: auth.AdminUser):
    if db.execute(text("SELECT 1 FROM employee WHERE emp_no = :n"), {"n": body.emp_no}).first():
        raise HTTPException(409, f"이미 등록된 사번입니다: {body.emp_no}")
    data = body.model_dump()
    _normalize_duty(data, body.emp_group)
    data.update(created_by=admin["login_id"], updated_by=admin["login_id"])
    cols = list(data)
    row = db.execute(text(f"INSERT INTO employee ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)}) "
                          "RETURNING emp_id"), data).mappings().first()
    db.commit()
    return _get_employee(db, row["emp_id"])


@router.patch("/employees/{emp_id}", summary="직원 수정")
def update_employee(emp_id: int, body: EmployeePatch, db: DB, admin: auth.AdminUser):
    cur = _get_employee(db, emp_id)
    if not cur:
        raise HTTPException(404, "직원 정보를 찾을 수 없습니다.")
    data = body.model_dump(exclude_unset=True)
    merged = {**cur, **data}
    _normalize_duty(merged, merged["emp_group"])
    for k in ("duty_role", "duty_error_types"):        # 그룹 변경 시 정리된 값 반영
        if merged[k] != cur[k]:
            data[k] = merged[k]
    _update(db, "employee", "emp_id", emp_id, data, admin["login_id"])
    db.commit()
    return _get_employee(db, emp_id)


# =====================================================================
# 데이터 초기화 (시스템관리 > 데이터 초기화)
# =====================================================================
class DemoResetIn(BaseModel):
    confirm: str = Field(description='실수로 지우지 않도록 "초기화" 를 그대로 보내야 실행')


def _demo_counts() -> dict:
    with engine.connect() as cn:
        return {t: cn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                for t in ("stt_call", "consult_history", "incident_alert", "agent_run", "improvement_opinion")}


@router.get("/admin/demo-reset", summary="시연 데이터 초기화 기록 · 현재 건수 (시스템관리자)")
def get_demo_reset(_: auth.SysAdminUser):
    return {"last": db_init.demo_reset_info(), "counts": _demo_counts(),
            "tables": db_init.DEMO_TABLES}


@router.post("/admin/demo-reset", summary="시연 데이터 초기화: 상담·장애·알림·실행 이력·개선의견을 처음 시연 상태로 (시스템관리자)")
def run_demo_reset(body: DemoResetIn, admin: auth.SysAdminUser):
    if body.confirm.strip() != "초기화":
        raise HTTPException(400, "확인 문구가 맞지 않습니다. '초기화'를 입력하세요.")
    try:
        result = db_init.reset_demo_data(admin["login_id"])
    except Exception as e:
        raise HTTPException(500, f"초기화하지 못했습니다. 다른 화면의 조회가 끝난 뒤 다시 시도하세요. ({str(e).splitlines()[0]})")
    return {**result, "counts": _demo_counts()}
