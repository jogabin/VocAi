from typing import Annotated
from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

class Settings(BaseSettings):
    database_url: str
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

def get_db():
    with SessionLocal() as db:
        yield db

DB = Annotated[Session, Depends(get_db)]
app = FastAPI(title="DB 조회 API")

@app.get("/health")
def health(db: DB):
    info = db.execute(text("SELECT current_database() AS db, current_user AS usr, current_schema() AS sch")).mappings().first()
    tables = db.execute(text("""
        SELECT table_schema, table_name FROM information_schema.tables
        WHERE table_schema NOT IN ('pg_catalog','information_schema')
        ORDER BY 1, 2
    """)).mappings().all()
    return {"status": "ok", **info, "tables": tables}

@app.get("/users")
def list_items(
    db: DB,
    email: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    rows = db.execute(
        text("""
            SELECT * FROM public.users
            WHERE (email = :email)
            ORDER BY user_id LIMIT :limit OFFSET :offset
        """),
        {"email": email, "limit": limit, "offset": offset},
    ).mappings().all()
    return rows

@app.get("/users/{user_id}")
def get_item(user_id: str, db: DB):
    row = db.execute(
        text("SELECT * FROM users WHERE user_id = :user_id"), {"user_id": user_id}
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Item not found")
    return row