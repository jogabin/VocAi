"""VOC 테이블 생성 + 시드 입력. scripts/init_db.py 와 서버 시작 시(빈 DB일 때) 공용으로 사용."""
import logging
from pathlib import Path

from sqlalchemy import inspect, text

from app.database import engine

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent

VOC_TABLES = [
    "improvement_opinion",
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
    "10_impact_improvement.sql",   # 영향 기반 판별 보강 · 독립 고객 수 · 개선의견
    "11_demo_scripts.sql",         # 등급별 시연 STT 원문 16건 + 누적 제보용 사전 통화
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


def reset_users() -> None:
    """로그인 계정만 초기화: 모든 계정·세션을 지우고 초기 계정(05_users_hr.sql)으로 다시 만든다. 다른 데이터는 유지."""
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("DELETE FROM voc_user")          # 세션(voc_session)은 FK CASCADE 로 함께 삭제
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    init_schema()                                     # 계정 시드 재입력 (나머지 SQL 은 이미 있으면 그대로)


def init_if_empty() -> None:
    """빈 DB(배포 환경 첫 실행)일 때만 테이블 + 시드를 만든다. 이미 있으면 아무것도 하지 않음."""
    if inspect(engine).has_table("voc_user"):
        return
    log.info("VOC 테이블이 없어 초기화합니다 (초기 로그인 계정: admin / admin, user01 / user01, user02 / user02)")
    init_schema()


def reset_once(token: str) -> None:
    """DB_RESET_TOKEN 값이 마지막으로 적용한 값과 다를 때만 VOC 테이블을 지우고 시드로 다시 만든다.

    배포 환경에서 기존 데이터를 초기화할 때 사용: 새 토큰 값(예: 날짜)을 설정값으로 넣고 재배포하면
    첫 시작 때 한 번만 초기화되고, 이후 재시작·재배포에서는 같은 토큰이라 다시 지우지 않는다.
    """
    if not token:
        return
    with engine.begin() as cn:
        # 여러 인스턴스가 동시에 시작해도 한 곳에서만 초기화하도록 잠금 (트랜잭션 종료 시 자동 해제)
        cn.execute(text("SELECT pg_advisory_xact_lock(hashtext('vocai_db_reset'))"))
        cn.execute(text("CREATE TABLE IF NOT EXISTS app_meta (key VARCHAR(50) PRIMARY KEY, value TEXT NOT NULL,"
                        " updated_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
        applied = cn.execute(text("SELECT value FROM app_meta WHERE key = 'db_reset_token'")).scalar()
        if applied == token:
            return
        log.warning("DB_RESET_TOKEN=%s 이 새 값이라 VOC 테이블을 초기화합니다 (기존 데이터 삭제)", token)
        init_schema(reset=True)
        cn.execute(text("INSERT INTO app_meta (key, value) VALUES ('db_reset_token', :v) "
                        "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()"), {"v": token})
