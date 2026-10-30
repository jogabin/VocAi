from contextlib import asynccontextmanager
from pathlib import Path

import logging

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, settings
from app.db_init import apply_updates, init_if_empty, reset_once
from app.routers import admin_api, auth_api, customer_api, getRt, users_dao, voc_api   # 본인 라우터 파일명에 맞게 수정
from app.services.auth import require_user


logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    reset_once(settings.db_reset_token)   # DB_RESET_TOKEN 이 새 값이면 한 번만 초기화 (기존 데이터 삭제)
    init_if_empty()   # 빈 DB(axhub 등 새 배포 환경)면 테이블 + 시드 생성
    apply_updates()   # 기존 DB에도 적용할 SQL(UPDATE_SQL_FILES)을 한 번씩 적용 (예: IT담당자 계정 user02 → user)
    yield
    engine.dispose()


docs_kwargs = {} if settings.enable_docs else {
    "docs_url": None, "redoc_url": None, "openapi_url": None,
}
app = FastAPI(title="DB 조회 API", lifespan=lifespan, **docs_kwargs)

# 로컬 개발(Vue 5173 → FastAPI 8000)용. Cloud Run에서는 같은 출처라 사용되지 않음
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["*"],
)

# API는 /api 아래로
app.include_router(getRt.router, prefix="/api")
app.include_router(users_dao.router, prefix="/api")
app.include_router(auth_api.router, prefix="/api")    # 로그인 (토큰 없이 호출 가능)
# VOC 장애 알림 API / 사용자·인사정보 API: 로그인 필요 (.env AUTH_REQUIRED=false 이면 생략)
app.include_router(voc_api.router, prefix="/api", dependencies=[Depends(require_user)])
app.include_router(admin_api.router, prefix="/api", dependencies=[Depends(require_user)])
app.include_router(customer_api.router, prefix="/api", dependencies=[Depends(require_user)])   # 고객정보 · 상담데이터 등록

# Vue 빌드 결과 서빙 (반드시 맨 마지막, static 폴더가 있을 때만)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")