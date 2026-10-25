"""로그인 API (/api/auth)

- POST /auth/login     아이디·비밀번호 → 세션 토큰 + 사용자 정보
- GET  /auth/me        현재 로그인 사용자 (토큰 확인, 새로고침 시 로그인 유지용)
- POST /auth/logout    세션 종료
- POST /auth/password  본인 비밀번호 변경
"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.database import DB, settings
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    login_id: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=100)


class PasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(max_length=100)


@router.post("/login", summary="로그인")
def login(body: LoginIn, request: Request, db: DB):
    token, user = auth.login(db, body.login_id, body.password, request.headers.get("user-agent"))
    return {"token": token, "user": user, "session_hours": settings.session_hours}


@router.get("/me", summary="현재 로그인 사용자")
def me(user: auth.CurrentUser):
    return {"user": user, "auth_required": settings.auth_required}


@router.post("/logout", summary="로그아웃")
def logout(db: DB, token: auth.Token):
    if token:
        auth.logout(db, token)
    return {"ok": True}


@router.post("/password", summary="본인 비밀번호 변경")
def change_password(body: PasswordIn, db: DB, user: auth.CurrentUser, token: auth.Token):
    if not user.get("user_id"):
        raise HTTPException(400, "개발모드(AUTH_REQUIRED=false)에서는 변경할 수 없습니다.")
    stored = db.execute(text("SELECT password_hash FROM voc_user WHERE user_id = :id"),
                        {"id": user["user_id"]}).scalar()
    if not auth.verify_password(body.current_password, stored):
        raise HTTPException(400, "현재 비밀번호가 올바르지 않습니다.")
    auth.check_password_rule(body.new_password)
    db.execute(text("""UPDATE voc_user SET password_hash = :h, pw_changed_at = now(),
                              updated_by = :u, updated_at = now() WHERE user_id = :id"""),
               {"h": auth.hash_password(body.new_password), "u": user["login_id"], "id": user["user_id"]})
    auth.revoke_user_sessions(db, user["user_id"], keep_token=token)   # 다른 기기 세션 종료
    db.commit()
    return {"ok": True}
