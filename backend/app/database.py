from typing import Annotated, Iterator

from fastapi import Depends
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


class Settings(BaseSettings):
    database_url: str
    enable_docs: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # ---- LLM 설정 ----
    # llm_provider: anthropic / ollama / none(규칙 기반)
    llm_provider: str = "anthropic"
    # Ollama Cloud(채팅). 로컬 Ollama로 채팅하려면 OLLAMA_BASE_URL=http://localhost:11434, 키 비움
    ollama_base_url: str = "https://ollama.com"
    ollama_api_key: str = ""
    ollama_model: str = "gemma4:31b"
    # RAG 유사사례 검색 방식: text(문자열 유사도, 기본) / embedding(Ollama 임베딩 + pgvector)
    # 배포 서버에서는 PC의 로컬 Ollama에 접근할 수 없으므로 text 사용
    rag_search: str = "text"
    # RAG 검색 결과(과거 해결·오탐 사례)를 심각도 판별 LLM 프롬프트에 넣을지 여부
    rag_in_llm: bool = True
    # 임베딩(RAG_SEARCH=embedding): Ollama Cloud는 임베딩 미지원 → PC의 로컬 Ollama 사용 (ollama pull bge-m3)
    ollama_embed_base_url: str = "http://localhost:11434"
    ollama_embed_model: str = "bge-m3"
    embed_timeout_sec: float = 30.0
    # RAG 유사도 기준 (코사인). 표시 최소값 / 오탐 사례 일치 판단값
    rag_min_similarity: float = 0.45
    rag_fp_similarity: float = 0.60
    # Claude (LLM_PROVIDER=anthropic)
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"
    # 생각(thinking) 깊이: low / medium / high. 짧은 JSON 분류라 low (높이면 느려지고 토큰 소모 증가)
    llm_effort: str = "low"
    llm_timeout_sec: float = 60.0
    # 배포 환경 DB 초기화: 마지막으로 적용한 값과 다른 값을 넣고 재배포하면 시작 시 한 번만 VOC 테이블을 다시 만듦
    db_reset_token: str = ""
    # 메신저 전송 방식: mock / webhook / telegram (비우면 웹훅 URL 유무로 webhook·mock 자동 선택)
    messenger_provider: str = ""
    # 사내 메신저 웹훅 URL (없으면 MOCK 전송: messenger_log 테이블에만 기록)
    messenger_webhook_url: str = ""
    # 텔레그램 봇 토큰 (MESSENGER_PROVIDER=telegram). 인사정보의 메신저 ID 에 텔레그램 chat_id 입력
    telegram_bot_token: str = ""
    # 중복 제보 통합 판단 시간창(분) / 대규모 장애 신호 기준 제보 건수
    dedup_window_min: int = 60
    mass_signal_threshold: int = 3
    # 시연용: 에이전트 단계 사이 지연(초). 모니터 화면에서 진행 과정을 보이게 함. 운영 시 0
    agent_step_delay_sec: float = 1.0

    # ---- 로그인 / 세션 ----
    # auth_required=false 이면 로그인 없이 API 사용 (개발·테스트용)
    auth_required: bool = True
    session_hours: int = 12              # 마지막 사용 후 세션 유지 시간
    login_max_fail: int = 5              # 연속 실패 시 계정 잠금 (관리자가 사용자관리에서 해제)
    # 메신저 알림의 '장애 상세 보기' 링크 주소 (Cloud Run 배포 시 서비스 URL 로 변경)
    app_base_url: str = "http://localhost:5173"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()


def _sqlalchemy_url(url: str) -> str:
    """postgres:// · postgresql:// 형식(axhub 등에서 주입)을 psycopg(v3) 드라이버 형식으로 맞춘다."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


# 앱 전체에서 공유하는 엔진(커넥션 풀)
engine = create_engine(_sqlalchemy_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db() -> Iterator[Session]:
    """요청마다 세션을 열고, 응답이 끝나면 자동으로 닫는다."""
    with SessionLocal() as db:
        yield db


# 라우터에서 `db: DB`로 간단히 사용
DB = Annotated[Session, Depends(get_db)]
