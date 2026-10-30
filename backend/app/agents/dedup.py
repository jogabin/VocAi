"""② 중복 제보 통합 에이전트

장애 대상으로 판별된 건을 최근 60분(DEDUP_WINDOW_MIN) 안의 동일 오류유형 미해결 장애와
증상 유사도 + 채널/환경 일치도로 비교해 같은 장애이면 하나로 통합합니다.
(증상 유사도가 MIN_SYMPTOM_SIMILARITY 미만이면 채널·환경이 같아도 다른 장애로 봅니다.
 재시도 후 정상 진행이 확인된 상담은 미해결 장애에 통합하지 않고 별도 관찰 건으로 둡니다.)
통합된 장애의 독립 고객 수(같은 고객의 재문의·중복 등록은 1명)가 기준(판별기준 MASS_SIGNAL 규칙, 기본 3명) 이상이면
대규모 장애 신호(mass_signal)로 등록하고,
이 건수는 장애 알림 모니터의 '동일유형 장애' 건수에 집계됩니다.
등록 여부와 관계없이 다음 단계(심각도 판별)로 진행합니다.
"""
from datetime import datetime, timezone

from app.agents import rules
from app.database import settings
from app.services import criteria, repo

NAME = "중복제보 통합 에이전트"
MERGE_THRESHOLD = 0.30
MIN_SYMPTOM_SIMILARITY = 0.20   # 채널·환경 가산점만으로 다른 증상이 묶이지 않도록 증상 유사도 자체의 최소값


def _symptom_similarity(det: dict, customer_text: str, inc: dict) -> float:
    return max(rules.similarity(det["symptoms"], inc.get("symptoms") or ""),
               rules.similarity(customer_text, inc.get("symptoms") or ""))


def _score(det: dict, customer_text: str, inc: dict) -> float:
    base = _symptom_similarity(det, customer_text, inc)
    if base < MIN_SYMPTOM_SIMILARITY:
        return round(base, 3)                  # 증상이 다르면 가산점 없이 비교 (통합 기준 미달)
    env_new, env_old = det.get("env") or {}, inc.get("env_info") or {}
    bonus = 0.0
    if det.get("channel") and det["channel"] == inc.get("channel"):
        bonus += 0.15
    for key in ("os", "app_version", "error_code"):
        if env_new.get(key) and env_new.get(key) == env_old.get(key):
            bonus += 0.1
    return round(min(1.0, base + bonus), 3)


def _recovered_words(db, customer_text: str) -> list[str]:
    """일시 실패 후 정상 진행된 상담인지 (판별기준 RECOVERED_P3 규칙의 단어, 없으면 코드 기본값)."""
    rule = next((r for r in criteria.load(db).adjust_rules if r["rule_code"] == "RECOVERED_P3"), None)
    return rules.contains_any(customer_text, list((rule or {}).get("keywords") or rules.RECOVERED_SIGNALS))


def run(db, ctx: dict) -> tuple[str, str, dict]:
    det, consult = ctx["detection"], ctx["consult"]
    flow = det.get("p1_decision") or {}
    if flow.get("exclude_from_count"):
        # 상담사가 그 자리에서 해결한 건은 '미해결 독립 고객' 집계(대규모 신호)에 넣지 않음
        out = {"merged": False, "incident_id": None, "report_count": 1, "customer_count": 1, "mass_signal": False,
               "candidates": [], "window_min": settings.dedup_window_min, "resolved_by_counselor": True}
        ctx["dedup"] = out
        return "DONE", "상담사가 그 자리에서 해결한 건 → 미해결 장애 누적(대규모 신호 집계)에서 제외, 별도 건으로 등록", out
    recovered = _recovered_words(db, ctx["customer_text"])
    if recovered:
        # 해결된 건은 미해결 오류 누적에 넣지 않음 (별도 관찰 건으로 등록)
        out = {"merged": False, "incident_id": None, "report_count": 1, "customer_count": 1, "mass_signal": False,
               "candidates": [], "window_min": settings.dedup_window_min, "recovered": recovered}
        ctx["dedup"] = out
        return "DONE", f"정상 진행 확인 {recovered[:3]} → 미해결 장애 누적에서 제외, 별도 관찰 건으로 등록", out
    candidates = repo.find_open_incidents(db, det["error_type"], settings.dedup_window_min)
    scored = sorted(((_score(det, ctx["customer_text"], c), c) for c in candidates),
                    key=lambda x: x[0], reverse=True)
    compared = [{"incident_id": c["incident_id"], "title": c["title"], "score": s} for s, c in scored[:5]]

    if not scored or scored[0][0] < MERGE_THRESHOLD:
        out = {"merged": False, "incident_id": None, "report_count": 1, "customer_count": 1, "mass_signal": False,
               "candidates": compared, "window_min": settings.dedup_window_min}
        ctx["dedup"] = out
        msg = (f"최근 {settings.dedup_window_min}분 내 동일 유형 미해결 장애 {len(candidates)}건 비교 → "
               "유사 장애 없음, 신규 장애로 판단")
        return "DONE", msg, out

    score, inc = scored[0]
    count = int(inc["report_count"]) + 1
    repo.add_incident_report(db, inc["incident_id"], consult["consult_id"], score)
    customers = repo.count_incident_customers(db, inc["incident_id"])
    threshold = criteria.load(db).mass_threshold()
    mass = customers >= threshold              # 제보 건수가 아니라 독립 고객 수로 판단
    env = {**(inc.get("env_info") or {}), **{k: v for k, v in (det.get("env") or {}).items() if v}}
    repo.update_incident(db, inc["incident_id"], {
        "report_count": count,
        "customer_count": customers,
        "mass_signal": bool(inc.get("mass_signal")) or mass,
        "last_reported_at": datetime.now(timezone.utc),
        "env_info": env,
    })

    out = {"merged": True, "incident_id": inc["incident_id"], "similarity": score, "report_count": count,
           "customer_count": customers, "mass_signal": mass, "previous_severity": inc["severity"],
           "notified_severity": inc.get("notified_severity"), "previous_status": inc["status"],
           "candidates": compared, "window_min": settings.dedup_window_min}
    ctx["dedup"] = out
    msg = f"장애 {repo.incident_no(inc['incident_id'])}에 동일 제보로 통합 (유사도 {score}, 누적 {count}건 · 독립 고객 {customers}명)"
    if mass:
        msg += f" → 대규모 장애 신호 (기준 독립 고객 {threshold}명 이상) · 모니터 '동일유형 장애' 건수에 등록"
    out["same_type_registered"] = mass
    return "DONE", msg, out
