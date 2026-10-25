from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from app.database import DB

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_items(
    db: DB,
    email: str | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    conditions = []                      # 고정 SQL 조각만 들어감
    params = {"limit": limit, "offset": offset}

    if email:
        conditions.append("email = :email")
        params["email"] = email

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    query_str = ""
    if email != "":
        query_str = "WHERE (email = :email)"
    rows = db.execute(
        text(f"""
            SELECT * FROM public.users
            {where}
            ORDER BY user_id LIMIT :limit OFFSET :offset
        """),
        params,
    ).mappings().all()
    return rows

@router.get("/{user_id}")
def get_item(user_id: str, db: DB):
    row = db.execute(
        text("SELECT * FROM users WHERE user_id = :user_id"), {"user_id": user_id}
    ).mappings().first()
    if not row:
        raise HTTPException(404, "User  not found")
    return row