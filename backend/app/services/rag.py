"""RAG: 과거 장애 이력(해결/오탐) 임베딩 저장 + 유사 사례 검색

- 임베딩: 로컬 Ollama /api/embed (기본 bge-m3, 한국어 지원)
- 저장소: incident_embedding 테이블
    · pgvector 확장이 있으면 embedding vector 컬럼 + `<=>`(코사인 거리) 연산으로 DB에서 검색
    · 없으면 embedding real[] 컬럼에 저장하고 파이썬에서 코사인 유사도 계산 (자동 대체)
- 임베딩 서버에 연결할 수 없으면 None 을 돌려주고, 호출 측은 문자열 유사도로 대체합니다.
"""
import hashlib
import logging
import math
import time

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import settings

log = logging.getLogger("voc.rag")

_vector_mode: str | None = None          # 'pgvector' | 'array' | 'missing'
_last_status = {"ok": None, "error": None, "at": None}
_RETRY_AFTER_SEC = 30                    # 임베딩 서버 장애 시 재시도 간격 (매 요청 타임아웃 방지)


# ---------------------------------------------------------------------
# 임베딩
# ---------------------------------------------------------------------
def embed(texts: list[str]) -> list[list[float]] | None:
    if not texts or not settings.ollama_embed_model:
        return None
    if _last_status["ok"] is False and time.time() - (_last_status["at"] or 0) < _RETRY_AFTER_SEC:
        return None
    try:
        resp = httpx.post(
            settings.ollama_embed_base_url.rstrip("/") + "/api/embed",
            json={"model": settings.ollama_embed_model, "input": texts},
            timeout=settings.embed_timeout_sec,
        )
        resp.raise_for_status()
        vecs = resp.json().get("embeddings") or []
        if len(vecs) != len(texts):
            raise ValueError(f"임베딩 개수 불일치 {len(vecs)} != {len(texts)}")
        _last_status.update(ok=True, error=None, at=time.time())
        return vecs
    except Exception as e:
        _last_status.update(ok=False, error=str(e)[:200], at=time.time())
        log.warning("임베딩 실패 (%s): %s", settings.ollama_embed_base_url, e)
        return None


def _vec_literal(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.6f}" for x in v) + "]"


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def vector_mode(db: Session) -> str:
    global _vector_mode
    if _vector_mode is None:
        udt = db.execute(text("""
            SELECT udt_name FROM information_schema.columns
             WHERE table_name = 'incident_embedding' AND column_name = 'embedding'
             LIMIT 1
        """)).scalar()
        _vector_mode = "pgvector" if udt == "vector" else ("array" if udt else "missing")
    return _vector_mode


def status(db: Session) -> dict:
    return {"model": settings.ollama_embed_model, "vector_mode": vector_mode(db),
            "embed_ok": _last_status["ok"], "embed_error": _last_status["error"]}


# ---------------------------------------------------------------------
# 지식베이스 임베딩 저장
# ---------------------------------------------------------------------
def incident_content(inc: dict) -> str:
    parts = [inc.get("title") or "", f"유형: {inc.get('error_type') or ''} / 채널: {inc.get('channel') or ''}",
             f"증상: {inc.get('symptoms') or ''}"]
    if inc.get("resolution"):
        parts.append(f"처리결과: {inc['resolution']}")
    return "\n".join(parts)


def ensure_embeddings(db: Session, incident_ids: list[int] | None = None) -> int:
    """해결/오탐 장애 중 임베딩이 없거나 내용이 바뀐 건을 임베딩해 저장. 저장 건수 반환."""
    mode = vector_mode(db)
    if mode == "missing":
        return 0
    cond = "AND i.incident_id = ANY(:ids)" if incident_ids else ""
    rows = [dict(r) for r in db.execute(text(f"""
        SELECT i.incident_id, i.title, i.error_type, i.channel, i.symptoms, i.resolution,
               e.content_hash, e.model
          FROM incident_alert i
          LEFT JOIN incident_embedding e ON e.incident_id = i.incident_id
         WHERE i.status IN ('해결', '오탐') {cond}
    """), {"ids": incident_ids} if incident_ids else {}).mappings().all()]

    todo = []
    for r in rows:
        content = incident_content(r)
        h = hashlib.sha1(content.encode("utf-8")).hexdigest()
        if r["content_hash"] != h or r["model"] != settings.ollama_embed_model:
            todo.append((r["incident_id"], content, h))
    if not todo:
        return 0
    vecs = embed([t[1] for t in todo])
    if vecs is None:
        return 0

    cast = "CAST(:v AS vector)" if mode == "pgvector" else "CAST(:v AS real[])"
    for (iid, content, h), v in zip(todo, vecs):
        lit = _vec_literal(v) if mode == "pgvector" else "{" + ",".join(f"{x:.6f}" for x in v) + "}"
        db.execute(text(f"""
            INSERT INTO incident_embedding (incident_id, model, content, content_hash, embedding, updated_at)
            VALUES (:iid, :model, :content, :h, {cast}, now())
            ON CONFLICT (incident_id) DO UPDATE
               SET model = EXCLUDED.model, content = EXCLUDED.content, content_hash = EXCLUDED.content_hash,
                   embedding = EXCLUDED.embedding, updated_at = now()
        """), {"iid": iid, "model": settings.ollama_embed_model, "content": content, "h": h, "v": lit})
    return len(todo)


# ---------------------------------------------------------------------
# 유사 사례 검색
# ---------------------------------------------------------------------
def search_similar(db: Session, query: str, k: int = 3) -> tuple[list[dict], str] | None:
    """(유사사례 목록, 검색방식) 반환. 임베딩 사용 불가 시 None."""
    mode = vector_mode(db)
    if mode == "missing":
        return None
    ensure_embeddings(db)              # 새로 해결/오탐 처리된 건 자동 반영
    qv = embed([query])
    if qv is None:
        return None
    qv = qv[0]
    cols = """i.incident_id, i.title, i.error_type, i.channel, i.severity, i.status,
              i.symptoms, i.resolution"""

    if mode == "pgvector":
        rows = db.execute(text(f"""
            SELECT {cols}, 1 - (e.embedding <=> CAST(:q AS vector)) AS similarity
              FROM incident_embedding e JOIN incident_alert i ON i.incident_id = e.incident_id
             WHERE i.status IN ('해결', '오탐') AND e.model = :model
             ORDER BY e.embedding <=> CAST(:q AS vector)
             LIMIT :k
        """), {"q": _vec_literal(qv), "model": settings.ollama_embed_model, "k": k}).mappings().all()
        result = [dict(r) for r in rows]
    else:
        rows = db.execute(text(f"""
            SELECT {cols}, e.embedding
              FROM incident_embedding e JOIN incident_alert i ON i.incident_id = e.incident_id
             WHERE i.status IN ('해결', '오탐') AND e.model = :model
        """), {"model": settings.ollama_embed_model}).mappings().all()
        result = []
        for r in rows:
            d = dict(r)
            d["similarity"] = _cosine(qv, list(d.pop("embedding")))
            result.append(d)
        result.sort(key=lambda d: d["similarity"], reverse=True)
        result = result[:k]

    for d in result:
        d["similarity"] = round(float(d["similarity"]), 3)
    method = "pgvector" if mode == "pgvector" else "임베딩(배열)"
    return result, method
