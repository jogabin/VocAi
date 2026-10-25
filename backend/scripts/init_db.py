"""VOC 장애 알림용 테이블 생성 + 시연 데이터 입력 + 장애등급 판별기준 + 사용자·인사정보 + RAG 임베딩 생성.

사용법 (backend 폴더에서):
    python scripts/init_db.py           # 테이블 생성(없으면) + 시드 입력 + 임베딩
    python scripts/init_db.py --reset   # VOC 테이블 삭제 후 재생성 + 시드 (시연 초기화)

.env 의 DATABASE_URL 을 그대로 사용합니다. 기존 users 테이블은 건드리지 않습니다.
pgvector 확장이 설치돼 있으면 vector 컬럼을, 없으면 real[] 컬럼을 만듭니다(자동 대체).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal, engine, settings  # noqa: E402

VOC_TABLES = [
    "customer",
    "incident_action",
    "voc_session", "voc_user", "employee",
    "severity_adjust_rule", "severity_base_rule", "severity_grade",
    "incident_embedding", "agent_step", "agent_run", "messenger_log", "incident_report",
    "incident_alert", "biz_owner", "consult_history", "stt_utterance", "stt_call",
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


def run_sql(cur, path: Path) -> None:
    print(f"  - {path.name}")
    cur.execute(path.read_text(encoding="utf-8"))


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
        print(f"  ! pgvector 확장을 사용할 수 없어 real[] 컬럼으로 대체합니다. ({str(e).splitlines()[0]})")
        cur = raw.cursor()
        cur.execute(EMBED_TABLE.format(col_type="real[]"))
        raw.commit()
        return "array"


def main() -> None:
    reset = "--reset" in sys.argv
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        if reset:
            print("기존 VOC 테이블 삭제")
            cur.execute("DROP TABLE IF EXISTS " + ", ".join(VOC_TABLES) + " CASCADE")
            cur.execute("DROP SEQUENCE IF EXISTS customer_no_seq, stt_call_no_seq")
        print("SQL 실행")
        run_sql(cur, ROOT / "sql" / "01_schema.sql")
        run_sql(cur, ROOT / "sql" / "02_seed.sql")
        run_sql(cur, ROOT / "sql" / "04_severity_criteria.sql")   # 장애등급 판별기준 + 초기 데이터
        run_sql(cur, ROOT / "sql" / "05_users_hr.sql")            # 로그인 사용자 + 인사정보 + 초기 계정
        run_sql(cur, ROOT / "sql" / "06_consult_agent.sql")       # 상담상태 · 담당자/처리자 · 메신저 수신 구분
        run_sql(cur, ROOT / "sql" / "07_incident_process.sql")    # 장애 처리 이력
        run_sql(cur, ROOT / "sql" / "08_customer_consult_data.sql")  # 고객정보 · 상담데이터 등록
        run_sql(cur, ROOT / "sql" / "09_auth_roles.sql")          # 로그인 권한 4종 (상담사/센터관리자/IT담당자/시스템관리자)
        raw.commit()
        mode = create_embedding_table(raw)
        print(f"  - incident_embedding 테이블 ({mode})")
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()

    # 과거 장애 이력 임베딩 (로컬 Ollama 필요. 실패해도 서버 실행 중 검색 시 자동 재시도)
    from app.services import rag
    with SessionLocal() as db:
        n = rag.ensure_embeddings(db)
        db.commit()
        st = rag.status(db)
    if st["embed_ok"] is False:
        print(f"  ! 임베딩 생성 실패: {st['embed_error']}")
        print(f"    로컬 Ollama 실행 및 `ollama pull {settings.ollama_embed_model}` 후 다시 실행하거나,"
              " 서버 실행 중 첫 검색 때 자동 생성됩니다.")
    else:
        print(f"  - 과거 장애 이력 임베딩 {n}건 생성 ({settings.ollama_embed_model}, {st['vector_mode']})")
    print("완료  (초기 로그인 계정: admin / admin1234)")


if __name__ == "__main__":
    main()
