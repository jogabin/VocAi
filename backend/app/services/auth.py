"""로그인 / 세션 / 권한

- 비밀번호: PBKDF2-SHA256 (표준 라이브러리, 추가 패키지 없음)
- 세션: 로그인 시 임의 토큰 발급 → DB(voc_session)에는 SHA-256 해시만 저장.
  요청마다 `Authorization: Bearer <토큰>` 으로 확인하고, 사용할 때마다 만료 시각을 연장합니다.
- 권한(auth_role) 4종: 상담사 / 센터관리자 / IT담당자 / 시스템관리자  (화면 설계서 SCR-01~10 기준)
    IT담당자 = 장애 알림을 받아 장애를 처리하는 프로그램 사용자 (시스템 관리 권한 아님)
    SCR-02·03 상담현황·상담이력등록   : 상담사, 센터관리자, 시스템관리자
    SCR-04·05 장애 모니터·상세정보     : 전체
    SCR-08    판별기준 관리            : IT담당자, 시스템관리자
    SCR-06·07·09·10 사용자·인사·고객·상담데이터 : 시스템관리자
  장애 처리 등록(SCR-05)은 IT담당자 권한만 가능합니다.
- .env 의 AUTH_REQUIRED=false 이면 로그인 없이 동작 (개발용, 가상의 관리자로 처리)
"""
import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import DB, settings

_ALGO = "pbkdf2_sha256"
_ITER = 200_000
_TOUCH_SEC = 60           # 세션 만료 연장은 최대 1분에 한 번만 DB 갱신

ROLES = ("상담사", "센터관리자", "IT담당자", "시스템관리자")
CONSULT_ROLES = ("상담사", "센터관리자", "시스템관리자")      # SCR-02, SCR-03
CRITERIA_ROLES = ("IT담당자", "시스템관리자")                  # SCR-08
SYS_ADMIN = "시스템관리자"                                  # SCR-06, 07, 09, 10

DEV_USER = {"user_id": None, "login_id": "dev", "user_name": "개발모드", "auth_role": SYS_ADMIN,
            "emp_id": None, "emp_group": None, "emp_name": None}

USER_COLS = """u.user_id, u.login_id, u.user_name, u.auth_role, u.emp_id, u.email, u.use_yn,
               u.fail_count, u.last_login_at, u.pw_changed_at, u.created_at, u.updated_by, u.updated_at,
               e.emp_no, e.emp_name, e.emp_group, e.dept"""


# ---------------------------------------------------------------------
# 비밀번호
# ---------------------------------------------------------------------
def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), salt, _ITER)
    return f"{_ALGO}${_ITER}${salt.hex()}${h.hex()}"


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, it, salt, h = stored.split("$")
        if algo != _ALGO:
            return False
        calc = hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), bytes.fromhex(salt), int(it))
        return hmac.compare_digest(calc.hex(), h)
    except (ValueError, AttributeError):
        return False


def check_password_rule(pw: str) -> None:
    if len(pw) < 8 or not any(c.isdigit() for c in pw) or not any(c.isalpha() for c in pw):
        raise HTTPException(400, "비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.")


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------
# 로그인 / 세션
# ---------------------------------------------------------------------
def get_user(db: Session, user_id: int) -> dict | None:
    row = db.execute(text(f"SELECT {USER_COLS} FROM voc_user u LEFT JOIN employee e ON e.emp_id = u.emp_id "
                          "WHERE u.user_id = :id"), {"id": user_id}).mappings().first()
    return dict(row) if row else None


def login(db: Session, login_id: str, password: str, client_info: str | None = None) -> tuple[str, dict]:
    row = db.execute(text("SELECT user_id, password_hash, use_yn, fail_count FROM voc_user WHERE login_id = :l"),
                     {"l": login_id.strip()}).mappings().first()
    fail_msg = "아이디 또는 비밀번호가 올바르지 않습니다."
    if not row:
        raise HTTPException(401, fail_msg)
    if not row["use_yn"]:
        raise HTTPException(403, "사용이 중지된 계정입니다. 관리자에게 문의하세요.")
    if row["fail_count"] >= settings.login_max_fail:
        raise HTTPException(403, f"로그인 {settings.login_max_fail}회 실패로 잠긴 계정입니다. 관리자에게 잠금 해제를 요청하세요.")
    if not verify_password(password, row["password_hash"]):
        db.execute(text("UPDATE voc_user SET fail_count = fail_count + 1 WHERE user_id = :id"), {"id": row["user_id"]})
        db.commit()
        left = settings.login_max_fail - row["fail_count"] - 1
        if left <= 0:
            raise HTTPException(403, f"로그인 {settings.login_max_fail}회 실패로 계정이 잠겼습니다. 관리자에게 잠금 해제를 요청하세요.")
        raise HTTPException(401, fail_msg + (f" (잠금까지 {left}회 남음)" if left <= 2 else ""))

    token = secrets.token_urlsafe(32)
    db.execute(text("""INSERT INTO voc_session (token_hash, user_id, expires_at, client_info)
                       VALUES (:t, :u, now() + make_interval(hours => :h), :c)"""),
               {"t": _token_hash(token), "u": row["user_id"], "h": settings.session_hours,
                "c": (client_info or "")[:200]})
    db.execute(text("UPDATE voc_user SET fail_count = 0, last_login_at = now() WHERE user_id = :id"),
               {"id": row["user_id"]})
    db.execute(text("DELETE FROM voc_session WHERE expires_at < now()"))      # 만료 세션 정리
    db.commit()
    return token, get_user(db, row["user_id"])


def logout(db: Session, token: str) -> None:
    db.execute(text("DELETE FROM voc_session WHERE token_hash = :t"), {"t": _token_hash(token)})
    db.commit()


def user_by_token(db: Session, token: str) -> dict | None:
    row = db.execute(text("""
        SELECT s.user_id, s.expires_at, EXTRACT(EPOCH FROM now() - s.last_seen_at) AS idle_sec, u.use_yn
          FROM voc_session s JOIN voc_user u ON u.user_id = s.user_id
         WHERE s.token_hash = :t AND s.expires_at > now()"""), {"t": _token_hash(token)}).mappings().first()
    if not row or not row["use_yn"]:
        return None
    if float(row["idle_sec"] or 0) > _TOUCH_SEC:
        db.execute(text("""UPDATE voc_session SET last_seen_at = now(),
                                  expires_at = now() + make_interval(hours => :h)
                            WHERE token_hash = :t"""), {"t": _token_hash(token), "h": settings.session_hours})
        db.commit()
    return get_user(db, row["user_id"])


def revoke_user_sessions(db: Session, user_id: int, keep_token: str | None = None) -> None:
    db.execute(text("DELETE FROM voc_session WHERE user_id = :u AND token_hash <> :k"),
               {"u": user_id, "k": _token_hash(keep_token) if keep_token else ""})


# ---------------------------------------------------------------------
# FastAPI 의존성
# ---------------------------------------------------------------------
def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip() or None
    return None


def require_user(db: DB, token: Annotated[str | None, Depends(bearer_token)]) -> dict:
    if not settings.auth_required:
        return DEV_USER
    if not token:
        raise HTTPException(401, "로그인이 필요합니다.")
    user = user_by_token(db, token)
    if not user:
        raise HTTPException(401, "로그인 세션이 만료되었습니다. 다시 로그인하세요.")
    return user


def require_roles(*roles: str):
    """지정한 권한(auth_role)만 허용하는 FastAPI 의존성."""
    def dep(user: Annotated[dict, Depends(require_user)]) -> dict:
        if user["auth_role"] not in roles:
            raise HTTPException(403, f"{'·'.join(roles)} 권한만 사용할 수 있는 기능입니다.")
        return user
    return dep


def is_it_staff(user: dict) -> bool:
    """장애 처리 등록 가능 여부: IT담당자 권한 (개발모드는 허용)."""
    return user.get("auth_role") == "IT담당자" or (not settings.auth_required and user.get("user_id") is None)


CurrentUser = Annotated[dict, Depends(require_user)]
SysAdminUser = Annotated[dict, Depends(require_roles(SYS_ADMIN))]
AdminUser = SysAdminUser            # 이전 이름 호환 (사용자·인사·고객·상담데이터 관리 = 시스템관리자)
CriteriaUser = Annotated[dict, Depends(require_roles(*CRITERIA_ROLES))]
ConsultUser = Annotated[dict, Depends(require_roles(*CONSULT_ROLES))]
Token = Annotated[str | None, Depends(bearer_token)]
