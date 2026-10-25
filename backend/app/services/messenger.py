"""사내 메신저 전송.

MESSENGER_PROVIDER 로 전송 방식을 고른다 (비우면 MESSENGER_WEBHOOK_URL 유무로 webhook / mock 자동 선택).
- mock     : 실제 전송 없이 messenger_log 테이블에만 기록 → 모니터 화면에서 확인
- webhook  : MESSENGER_WEBHOOK_URL 로 JSON POST (Slack/Teams/사내메신저 Incoming Webhook 형식: {"text": ...})
             사내 메신저 규격이 다르면 _post_webhook() 의 payload 만 바꾸면 됩니다.
- telegram : 텔레그램 봇(TELEGRAM_BOT_TOKEN)으로 수신자별 전송. 인사정보의 메신저 ID = 텔레그램 chat_id
             chat_id 확인: 수신자가 봇에게 아무 메시지나 보낸 뒤 GET /api/messenger/telegram/chats
"""
import httpx
from sqlalchemy.orm import Session

from app.database import settings
from app.services import repo

TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_MAX_TEXT = 4096


def provider() -> str:
    """현재 전송 방식: MOCK / WEBHOOK / TELEGRAM"""
    p = settings.messenger_provider.strip().lower()
    if p == "telegram":
        return "TELEGRAM"
    if p == "webhook" or (not p and settings.messenger_webhook_url):
        return "WEBHOOK"
    return "MOCK"


def _post_webhook(receivers: list[dict], title: str, body: str) -> None:
    mentions = " ".join(f"@{r['receiver']}" for r in receivers)
    payload = {"text": f"{title}\n{mentions}\n\n{body}"}
    resp = httpx.post(settings.messenger_webhook_url, json=payload, timeout=10)
    resp.raise_for_status()


def _telegram_call(method: str, payload: dict | None = None) -> dict:
    """텔레그램 Bot API 호출. 오류 메시지에 봇 토큰(URL에 포함)이 섞이지 않도록 직접 만든 문구만 올린다."""
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN 이 설정되지 않았습니다.")
    url = f"{TELEGRAM_API}/bot{settings.telegram_bot_token}/{method}"
    try:
        resp = httpx.post(url, json=payload or {}, timeout=10)
    except httpx.HTTPError as e:
        raise RuntimeError(f"텔레그램 연결 실패 ({type(e).__name__})") from None
    try:
        data = resp.json()
    except ValueError:
        raise RuntimeError(f"텔레그램 응답 오류 (HTTP {resp.status_code})") from None
    if not data.get("ok"):
        raise RuntimeError(f"텔레그램 오류 {data.get('error_code', resp.status_code)}: {data.get('description', '')}")
    return data["result"]


def _send_telegram(chat_id: str, title: str, body: str) -> None:
    text = f"{title}\n\n{body}"
    if len(text) > TELEGRAM_MAX_TEXT:
        text = text[:TELEGRAM_MAX_TEXT - 1] + "…"
    _telegram_call("sendMessage", {"chat_id": chat_id.strip(), "text": text,
                                   "link_preview_options": {"is_disabled": True}})


def telegram_chats() -> list[dict]:
    """봇에게 최근 메시지를 보낸 대화 목록 (chat_id 확인용). 텔레그램은 약 24시간 동안의 메시지만 돌려준다."""
    chats = {}
    for u in _telegram_call("getUpdates", {"allowed_updates": ["message"]}):
        chat = (u.get("message") or {}).get("chat")
        if chat:
            name = chat.get("title") or " ".join(filter(None, [chat.get("last_name"), chat.get("first_name")]))
            chats[chat["id"]] = {"chat_id": str(chat["id"]), "type": chat.get("type"), "name": name,
                                 "username": chat.get("username")}
    return list(chats.values())


def send_message(db: Session, receivers: list[dict], title: str, body: str,
                 incident_id: int | None = None) -> list[dict]:
    """receivers: [{"receiver": 메신저ID, "receiver_name": 이름, "emp_id": int|None,
                    "recipient_type": "1차"|"2차"|None, "link_url": str|None, "owner_id": int|None}]"""
    transport = provider()
    # 수신자별 (status, error). 텔레그램은 수신자마다 따로 보내므로 결과도 따로 남긴다
    results = [("SENT", None)] * len(receivers)
    if transport == "WEBHOOK":
        try:
            _post_webhook(receivers, title, body)
        except Exception as e:  # 전송 실패도 이력으로 남긴다
            results = [("FAILED", str(e)[:500])] * len(receivers)
    elif transport == "TELEGRAM":
        results = []
        for r in receivers:
            try:
                _send_telegram(r["receiver"], title, body)
                results.append(("SENT", None))
            except Exception as e:
                results.append(("FAILED", str(e)[:500]))

    logs = []
    for r, (status, error) in zip(receivers, results):
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
