"""사내 메신저 전송.

- MESSENGER_WEBHOOK_URL 이 없으면 MOCK 전송 (messenger_log 테이블에만 기록 → 모니터 화면에서 확인)
- 있으면 해당 URL로 JSON POST (Slack/Teams/사내메신저 Incoming Webhook 형식: {"text": ...})
  사내 메신저 규격이 다르면 _post_webhook() 의 payload 만 바꾸면 됩니다.
"""
import httpx
from sqlalchemy.orm import Session

from app.database import settings
from app.services import repo


def _post_webhook(receivers: list[dict], title: str, body: str) -> None:
    mentions = " ".join(f"@{r['receiver']}" for r in receivers)
    payload = {"text": f"{title}\n{mentions}\n\n{body}"}
    resp = httpx.post(settings.messenger_webhook_url, json=payload, timeout=10)
    resp.raise_for_status()


def send_message(db: Session, receivers: list[dict], title: str, body: str,
                 incident_id: int | None = None) -> list[dict]:
    """receivers: [{"receiver": 메신저ID, "receiver_name": 이름, "emp_id": int|None,
                    "recipient_type": "1차"|"2차"|None, "link_url": str|None, "owner_id": int|None}]"""
    transport, status, error = "MOCK", "SENT", None
    if settings.messenger_webhook_url:
        transport = "WEBHOOK"
        try:
            _post_webhook(receivers, title, body)
        except Exception as e:  # 전송 실패도 이력으로 남긴다
            status, error = "FAILED", str(e)[:500]

    logs = []
    for r in receivers:
        logs.append(repo.insert_messenger_log(db, {
            "incident_id": incident_id,
            "owner_id": r.get("owner_id"),
            "emp_id": r.get("emp_id"),
            "recipient_type": r.get("recipient_type"),
            "link_url": r.get("link_url"),
            "receiver": r["receiver"],
            "receiver_name": r.get("receiver_name"),
            "title": title,
            "body": body,
            "transport": transport,
            "status": status,
            "error_message": error,
        }))
    return logs
