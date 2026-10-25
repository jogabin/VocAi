from fastapi import APIRouter

router = APIRouter(tags=["wellcom"])


@router.get("/wellcom")
def hello():
    return {"message": "hello world"}