"""VOC 테이블 생성 + 시드 입력. scripts/init_db.py 와 서버 시작 시(빈 DB일 때) 공용으로 사용."""
import logging
from pathlib import Path

from sqlalchemy import inspect

from app.database import engine

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

VOC_TABLES = [
    "customer",
    "incident_action",
    "voc_session", "voc_user", "employee",
    "severity_adjust_rule", "severity_base_rule", "severity_grade",
    "incident_embedding", "agent_step", "agent_run", "messenger_log", "incident_report",
    "incident_alert", "biz_owner", "consult_history", "stt_utterance", "stt_call",
]

SQL_FILES = [
    "01_schema.sql",
    "02_seed.sql",
    "04_severity_criteria.sql",    # 장애등급 판별기준 + 초기 데이터
    "05_users_hr.sql",             # 로그인 사용자 + 인사정보 + 초기 계정
    "06_consult_agent.sql",        # 상담상태 · 담당자/처리자 · 메신저 수신 구분
    "07_incident_process.sql",     # 장애 처리 이력
    "08_customer_consult_data.sql",  # 고객정보 · 상담데이터 등록
    "09_auth_roles.sql",           # 로그인 권한 4종 (상담사/센터관리자/IT담당자/시스템관리자)
]

EMBED_TABLE = """
CREATE TABLE IF NOT EXISTS incident_embedding (
    incident_id   BIGINT PRIMARY KEY REFERENCES incident_alert(incident_id) ON DELETE CASCADE,
    model         VARCHAR(100) NOT NULL,
    content       TEXT         NOT NULL,
    content_hash  VARCHAR(40)  NOT NULL,
    embedding     {col_type}   NOT NULL,
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
)"""


def create_embedding_table(raw) -> str:
    """pgvector 사용 가능 여부를 확인하고 incident_embedding 테이블 생성. 사용 모드 반환."""
    cur = raw.cursor()
    cur.execute("""SELECT udt_name FROM information_schema.columns
                    WHERE table_name = 'incident_embedding' AND column_name = 'embedding'""")
    row = cur.fetchone()
    if row:
        return "pgvector" if row[0] == "vector" else "array"
    try:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute(EMBED_TABLE.format(col_type="vector"))
        raw.commit()
        return "pgvector"
    except Exception as e:
        raw.rollback()
        log.warning("pgvector 확장을 사용할 수 없어 real[] 컬럼으로 대체합니다. (%s)", str(e).splitlines()[0])
        cur = raw.cursor()
        cur.execute(EMBED_TABLE.format(col_type="real[]"))
        raw.commit()
        return "array"


def init_schema(reset: bool = False) -> str:
    """테이블 생성 + 시드 입력. incident_embedding 사용 모드(pgvector/array) 반환."""
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        if reset:
            log.info("기존 VOC 테이블 삭제")
            cur.execute("DROP TABLE IF EXISTS " + ", ".join(VOC_TABLES) + " CASCADE")
            cur.execute("DROP SEQUENCE IF EXISTS customer_no_seq, stt_call_no_seq")
        for name in SQL_FILES:
            log.info("SQL 실행: %s", name)
            cur.execute((ROOT / "sql" / name).read_text(encoding="utf-8"))
        raw.commit()
        return create_embedding_table(raw)
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def init_if_empty() -> None:
    """빈 DB(배포 환경 첫 실행)일 때만 테이블 + 시드를 만든다. 이미 있으면 아무것도 하지 않음."""
    if inspect(engine).has_table("voc_user"):
        return
    log.info("VOC 테이블이 없어 초기화합니다 (초기 로그인 계정: admin / admin1234)")
    init_schema()
