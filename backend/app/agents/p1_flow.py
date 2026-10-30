"""장애 감지 보강: 유형 상담 → 상담사 해결 여부 → P1 관계 지도 → 근거 확인

AI 호출은 detection.py 가 하고, 여기서는 AI가 낸 판단(ans)을 받아 아래 순서로 처리 방향을 정합니다.
  1. 비슷한 유형 상담(팀이 확인한 상담)이 있으면 그 결과를 따른다.
       - 처리 결과가 오탐·고객 입력 오류·상품 조건  → P1 아님 (P4, 알림 없음)
       - P1 유형                                    → 장애 + P1 확인 대상
       - P2~P4 유형                                 → 장애 (등급은 심각도 단계에서)
       - 일반 문의 유형                              → 상담사가 해결해 주지 않았고 고객이 오류 신호를 말한 경우만 장애, 아니면 일반
  2. 없으면 상담사가 그 자리에서 정확히 해결해 줬는지 본다. (확인·전달·접수·감사 인사는 해결이 아님)
       - 해결함   → P1 아님. 오류 신호가 있으면 장애(P1 제외), 없으면 일반
       - 못 함    → 3으로
  3. P1 관계 지도(p1_graph)의 경로와 맞는지 본다.
       - 맞음     → P1 확인 대상
       - 안 맞음  → 장애 후보, 최소 P2(관찰)
  4. AI가 인용한 말이 실제 대화에 없으면 그 AI 판단은 쓰지 않고 규칙 결과로 두며 '확인 필요'로 표시한다.
고객 오류 신호어(규칙)는 AI와 별개로 항상 함께 본다.
등급을 바꾸는 일(상한·하한)은 심각도 단계(severity.py)가 이 결과를 읽어 적용합니다.
"""
import re

from app.services import p1_graph, type_cases

MIN_QUOTE = 4                                    # 인용문 최소 길이(공백·문장부호 뺀 글자 수)
# 앞으로 하겠다는 말(확인·전달·접수·이관)과 인사만 있는 말은 해결이 아님
PROMISE = re.compile(r"(확인|전달|접수|이관|알아보)\s*(해|하)?\s*(보|드리|두)?\s*(겠|도록)|접수했|확인\s*후")
COURTESY_ONLY = re.compile(r"^(감사|죄송|불편|좋은 의견|소중한)")


def _norm(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", s or "").lower()


def quote_exists(quote: str, text: str) -> bool:
    """AI가 인용한 말이 실제 대화 문장에 들어 있는지 (공백·문장부호 차이는 무시)."""
    q = _norm(quote)
    return len(q) >= MIN_QUOTE and q in _norm(text)


def is_resolution_quote(quote: str) -> bool:
    q = (quote or "").strip()
    return bool(q) and not PROMISE.search(q) and not COURTESY_ONLY.match(q)


def _obj(v) -> dict:
    return v if isinstance(v, dict) else {}


def decide(ans: dict, customer_text: str, agent_text: str, rule_cue: list[str]) -> dict:
    """AI 판단 + 규칙 신호 → 처리 방향.

    반환 route: 오탐 유형 / P1 유형 / 장애 유형 / 일반 문의 유형 / 개선 유형 / 상담사 해결 / P1 지도 일치 / 장애 후보
    incident: True·False 면 장애 여부를 이 결과로 정하고, None 이면 기존 판정을 그대로 둔다.
    cap: 이 등급보다 심각하면 낮춘다(대규모 신호·기존 장애 통합 건은 제외). floor: 최소 이 등급.
    """
    notes: list[str] = []
    need_check = False

    # ----- 근거 확인: AI가 인용한 말이 실제 대화에 있어야 AI 판단을 쓴다 -----
    cue = _obj(ans.get("failure_cue"))
    ai_cue = bool(cue.get("has"))
    if ai_cue and not quote_exists(str(cue.get("quote") or ""), customer_text):
        ai_cue, need_check = False, True
        notes.append("AI가 인용한 고객 말이 대화에 없음 → 오류 신호는 규칙 결과로 판단")
    has_cue = ai_cue or bool(rule_cue)

    res = _obj(ans.get("counselor_resolved"))
    resolved = bool(res.get("resolved"))
    if resolved:
        q = str(res.get("quote") or "")
        if not (quote_exists(q, agent_text) and is_resolution_quote(q)):
            resolved, need_check = False, True
            notes.append("AI가 인용한 상담사 말이 대화에 없거나 해결로 볼 수 없음 → 해결 아님으로 처리")

    tid = ans.get("similar_type")
    case = type_cases.by_id().get(tid) if tid else None
    if tid and not case:
        need_check = True
        notes.append(f"AI가 유형 상담 목록에 없는 '{tid}'를 인용 → 유형 상담 없음으로 처리")

    pth = _obj(ans.get("p1_path"))
    pid = pth.get("id")
    path_ok = bool(pid) and pid in p1_graph.path_ids() and quote_exists(str(pth.get("quote") or ""), customer_text)
    if pid and not path_ok:
        need_check = True
        notes.append(f"P1 경로 '{pid}' 인용이 대화나 지도와 맞지 않음 → 지도 일치 아님으로 처리")

    out = {"route": None, "similar_type": case["id"] if case else None, "incident": None, "p1_candidate": False,
           "p1_path": None, "exclude_p1": False, "cap": None, "floor": None, "resolved": resolved,
           "exclude_from_count": False, "has_cue": has_cue, "need_check": need_check, "notes": notes}

    if case:
        g = case.get("구분")
        why = case.get("P1 판단 이유", "")
        if type_cases.is_not_p1_result(case):
            out.update(route="오탐 유형", incident=has_cue, exclude_p1=True, cap="P4")
            msg = f"비슷한 유형 [{case['id']}] 처리 결과 '{case['처리결과']}' → P1 아님(P4, 알림 없음)"
        elif g == "P1":
            out.update(route="P1 유형", incident=True, p1_candidate=True, floor="P2")
            msg = f"비슷한 유형 [{case['id']}]이 P1 유형 → 장애 + P1 확인 대상 ({why})"
        elif g in ("P2", "P3", "P4"):
            out.update(route="장애 유형", incident=True)
            msg = f"비슷한 유형 [{case['id']}]이 {g} 유형 → 장애, 등급은 심각도 단계에서 판단"
        elif g == "일반":
            out.update(route="일반 문의 유형", incident=(not resolved) and has_cue)
            msg = (f"비슷한 유형 [{case['id']}]이 일반 문의 → "
                   + ("해결 안내 없이 오류 신호가 있어 장애" if out["incident"] else "일반 문의로 판단"))
        else:
            out.update(route="개선 유형")
            msg = f"비슷한 유형 [{case['id']}]이 개선 의견 → 기존 판정 유지"
    elif resolved:
        out.update(route="상담사 해결", incident=has_cue, exclude_p1=True, cap="P2")
        msg = ("상담사가 그 자리에서 해결 → P1 아님, " + ("오류 신호가 있어 장애(P1 제외)" if has_cue else "오류 신호 없어 일반"))
    elif path_ok:
        out.update(route="P1 지도 일치", p1_candidate=True, p1_path=pid, floor="P2")
        msg = f"유형 상담 없음, 상담사 미해결, P1 지도 경로 {pid} '{p1_graph.path_name(pid)}'와 일치 → P1 확인 대상"
    else:
        out.update(route="장애 후보", floor="P2")
        msg = "유형 상담 없음, 상담사 미해결, P1 지도와 불일치 → 장애 후보, 최소 P2(관찰)"

    # 상담사가 해결한 건과 오탐은 '미해결 독립 고객 3명' 집계에서 뺀다. P1 유형은 해결로 보지 않고 계속 센다.
    out["exclude_from_count"] = resolved and out["route"] != "P1 유형"
    if need_check:
        msg += " [확인 필요: " + "; ".join(notes) + "]"
    out["reason"] = msg
    return out
