"""고객정보 관리 / 상담데이터 등록 API (신규 화면 2종)

고객정보 관리
- GET   /customers                 고객 목록 (keyword, gender) · 최근 상담 시각 포함   ← 로그인 사용자
- GET   /customers/{customer_id}   고객 상세
- POST  /customers                 고객 등록 (관리자, 고객번호 자동 채번)
- PATCH /customers/{customer_id}   고객 수정 (관리자)

상담데이터 등록
- POST  /stt                       기초 상담데이터 등록 (관리자): 통화 + 대화 생성, 상담상태 '진행'
"""
import re
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text

from app.database import DB
from app.services import auth

router = APIRouter(tags=["customer"])
KST = ZoneInfo("Asia/Seoul")
PHONE_RE = re.compile(r"^01[016789]-\d{3,4}-\d{4}$")
Gender = Literal["남", "여"]

CUST_COLS = """c.customer_id, c.customer_name, c.phone, c.gender, c.age, c.created_by, c.created_at,
               c.updated_by, c.updated_at,
               (SELECT max(s.started_at) FROM stt_call s WHERE s.customer_id = c.customer_id) AS last_call_at,
               (SELECT count(*) FROM stt_call s WHERE s.customer_id = c.customer_id) AS call_count"""


def _norm_phone(v: str | None) -> str | None:
    """숫자만 입력해도 010-0000-0000 형식으로 맞춤."""
    if v is None or not v.strip():
        return None
    d = re.sub(r"\D", "", v)
    if len(d) == 11:
        v = f"{d[:3]}-{d[3:7]}-{d[7:]}"
    elif len(d) == 10:
        v = f"{d[:3]}-{d[3:6]}-{d[6:]}"
    if not PHONE_RE.match(v):
        raise ValueError("핸드폰번호 형식이 올바르지 않습니다. (예: 010-1234-5678)")
    return v


# =====================================================================
# 고객정보 관리
# =====================================================================
class CustomerIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=50)
    phone: str = Field(description="010-0000-0000")
    gender: Gender | None = None
    age: int | None = Field(None, ge=0, le=130)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str) -> str:
        p = _norm_phone(v)
        if not p:
            raise ValueError("핸드폰번호를 입력하세요.")
        return p


class CustomerPatch(BaseModel):
    customer_name: str | None = Field(None, min_length=1, max_length=50)
    phone: str | None = None
    gender: Gender | None = None
    age: int | None = Field(None, ge=0, le=130)

    @field_validator("phone")
    @classmethod
    def _check_phone(cls, v: str | None) -> str | None:
        return _norm_phone(v)


def _get_customer(db, customer_id: str) -> dict | None:
    row = db.execute(text(f"SELECT {CUST_COLS} FROM customer c WHERE c.customer_id = :id"),
                     {"id": customer_id}).mappings().first()
    return dict(row) if row else None


def _check_phone_dup(db, phone: str | None, exclude_id: str | None = None):
    if not phone:
        return
    dup = db.execute(text("SELECT customer_id, customer_name FROM customer WHERE phone = :p AND customer_id <> :x"),
                     {"p": phone, "x": exclude_id or ""}).mappings().first()
    if dup:
        raise HTTPException(409, f"이미 등록된 핸드폰번호입니다: {dup['customer_name']} ({dup['customer_id']})")


@router.get("/customers", summary="고객 목록")
def list_customers(db: DB, _: auth.CurrentUser, keyword: str | None = None, gender: Gender | None = None,
                   limit: int = Query(300, ge=1, le=1000)):
    cond, params = [], {"limit": limit}
    if keyword:
        cond.append("(c.customer_name ILIKE :kw OR c.customer_id ILIKE :kw OR c.phone ILIKE :kw "
                    "OR replace(c.phone, '-', '') ILIKE :kw)")
        params["kw"] = f"%{keyword.strip()}%"
    if gender:
        cond.append("c.gender = :g")
        params["g"] = gender
    where = ("WHERE " + " AND ".join(cond)) if cond else ""
    rows = db.execute(text(f"SELECT {CUST_COLS} FROM customer c {where} ORDER BY c.customer_id LIMIT :limit"),
                      params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/customers/{customer_id}", summary="고객 상세")
def get_customer(customer_id: str, db: DB, _: auth.CurrentUser):
    c = _get_customer(db, customer_id)
    if not c:
        raise HTTPException(404, "고객 정보를 찾을 수 없습니다.")
    return c


@router.post("/customers", status_code=201, summary="고객 등록 (고객번호 자동 채번)")
def create_customer(body: CustomerIn, db: DB, admin: auth.AdminUser):
    _check_phone_dup(db, body.phone)
    while True:                                   # 기존 고객번호와 겹치지 않는 번호
        cid = "CUST-" + str(db.execute(text("SELECT nextval('customer_no_seq')")).scalar())
        if not db.execute(text("SELECT 1 FROM customer WHERE customer_id = :id"), {"id": cid}).first():
            break
    db.execute(text("""INSERT INTO customer (customer_id, customer_name, phone, gender, age, created_by, updated_by)
                       VALUES (:id, :name, :phone, :gender, :age, :by, :by)"""),
               {"id": cid, "name": body.customer_name.strip(), "phone": body.phone, "gender": body.gender,
                "age": body.age, "by": admin["login_id"]})
    db.commit()
    return _get_customer(db, cid)


@router.patch("/customers/{customer_id}", summary="고객 수정")
def update_customer(customer_id: str, body: CustomerPatch, db: DB, admin: auth.AdminUser):
    if not _get_customer(db, customer_id):
        raise HTTPException(404, "고객 정보를 찾을 수 없습니다.")
    data = body.model_dump(exclude_unset=True)
    if "customer_name" in data and data["customer_name"] is None:
        data.pop("customer_name")
    if "phone" in data:
        if not data["phone"]:
            raise HTTPException(400, "핸드폰번호를 입력하세요.")
        _check_phone_dup(db, data["phone"], customer_id)
    if data:
        sets = ", ".join(f"{k} = :{k}" for k in data)
        db.execute(text(f"UPDATE customer SET {sets}, updated_by = :_u, updated_at = now() WHERE customer_id = :_id"),
                   {**data, "_u": admin["login_id"], "_id": customer_id})
        if "customer_name" in data:               # 진행 중인 상담에도 바뀐 이름 반영
            db.execute(text("UPDATE stt_call SET customer_name = :n WHERE customer_id = :id AND consult_status = '진행'"),
                       {"n": data["customer_name"], "id": customer_id})
    db.commit()
    return _get_customer(db, customer_id)


# =====================================================================
# 상담데이터 등록 (상담현황 기초 데이터)
# =====================================================================
class LineIn(BaseModel):
    speaker: Literal["CUSTOMER", "AGENT"]
    text: str = Field(min_length=1, max_length=1000)
    offset_sec: int | None = Field(None, ge=0, description="상담 시작 후 경과 초. 비우면 자동 계산")


class ConsultDataIn(BaseModel):
    customer_id: str
    agent_emp_id: int
    consult_date: date
    start_time: time
    utterances: list[LineIn] = Field(min_length=1, max_length=200)


def _auto_offsets(lines: list[LineIn]) -> list[int]:
    """입력이 없으면 이전 발화 길이로 경과 시간 추정 (말하는 속도 약 6자/초, 최소 4초)."""
    out, cur, prev_len = [], 0, 0
    for i, l in enumerate(lines):
        if i > 0:
            cur += max(4, round(prev_len / 6))
        if l.offset_sec is not None:
            cur = max(cur, l.offset_sec) if i > 0 else l.offset_sec
        out.append(cur)
        prev_len = len(l.text)
    return out


@router.post("/stt", status_code=201, summary="상담데이터 등록 (통화 + 대화, 상담상태 '진행')")
def create_consult_data(body: ConsultDataIn, db: DB, admin: auth.AdminUser):
    cust = _get_customer(db, body.customer_id)
    if not cust:
        raise HTTPException(400, "고객정보 관리에 등록된 고객을 선택하세요.")
    agent = db.execute(text("SELECT emp_id, emp_name, emp_group, use_yn FROM employee WHERE emp_id = :id"),
                       {"id": body.agent_emp_id}).mappings().first()
    if not agent or agent["emp_group"] != "상담사" or not agent["use_yn"]:
        raise HTTPException(400, "인사정보에 등록된 상담사를 선택하세요.")
    lines = [l for l in body.utterances if l.text.strip()]
    if not any(l.speaker == "CUSTOMER" for l in lines):
        raise HTTPException(400, "고객 대화가 1개 이상 필요합니다.")
    started = datetime.combine(body.consult_date, body.start_time, tzinfo=KST)
    if started > datetime.now(KST) + timedelta(minutes=5):
        raise HTTPException(400, "상담일자·시간이 현재보다 미래입니다.")

    offsets = _auto_offsets(lines)
    duration = offsets[-1] + max(5, round(len(lines[-1].text) / 6))
    call_id = None
    while call_id is None:                        # 기존 통화 ID와 겹치지 않는 번호
        cand = "CALL-%04d" % db.execute(text("SELECT nextval('stt_call_no_seq')")).scalar()
        if not db.execute(text("SELECT 1 FROM stt_call WHERE call_id = :id"), {"id": cand}).first():
            call_id = cand
    db.execute(text("""
        INSERT INTO stt_call (call_id, customer_id, customer_name, agent_name, agent_emp_id, inbound_channel,
                              started_at, duration_sec, consult_status, created_by)
        VALUES (:id, :cid, :cname, :aname, :aid, '콜센터', :st, :dur, '진행', :by)"""),
        {"id": call_id, "cid": cust["customer_id"], "cname": cust["customer_name"],
         "aname": f"상담사 {agent['emp_name']}", "aid": agent["emp_id"], "st": started, "dur": duration,
         "by": admin["login_id"]})
    for seq, (l, off) in enumerate(zip(lines, offsets), start=1):
        db.execute(text("""INSERT INTO stt_utterance (call_id, seq, speaker, offset_sec, text)
                           VALUES (:id, :seq, :sp, :off, :tx)"""),
                   {"id": call_id, "seq": seq, "sp": l.speaker, "off": off, "tx": l.text.strip()})
    db.commit()
    return {"call_id": call_id, "consult_status": "진행", "started_at": started, "duration_sec": duration,
            "utterance_count": len(lines)}
