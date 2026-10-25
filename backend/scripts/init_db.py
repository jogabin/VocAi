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

import logging  # noqa: E402

from app.database import SessionLocal, settings  # noqa: E402
from app.db_init import init_schema  # noqa: E402


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="  - %(message)s")
    mode = init_schema(reset="--reset" in sys.argv)
    print(f"  - incident_embedding 테이블 ({mode})")

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
