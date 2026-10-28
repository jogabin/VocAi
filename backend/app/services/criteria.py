"""장애등급 판별기준 로더

심각도 판별·중복통합·담당자식별 에이전트가 쓰는 기준을 DB(severity_* 테이블)에서 읽습니다.
- 테이블이 없거나 비어 있으면 app/agents/rules.py 의 코드 기본값으로 동작합니다.
- 사용 중(use_yn)이고 적용 기간(valid_from~valid_to) 안에 있는 행만 씁니다.
- 기준 버전 = 사용 중인 기준 행의 최종 수정 시각. 장애에 함께 기록해 판정 근거를 남깁니다.
- 5초 동안 메모리에 보관합니다. 기준 수정 API 는 invalidate() 로 즉시 반영합니다.
"""
import time
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents import rules
from app.database import settings

_CACHE: dict = {"at": 0.0, "value": None}
_TTL_SEC = 5.0
_KST = ZoneInfo("Asia/Seoul")

_ACTIVE = "use_yn AND valid_from <= CURRENT_DATE AND (valid_to IS NULL OR valid_to >= CURRENT_DATE)"


@dataclass
class Criteria:
    grades: list[dict]                       # grade_order 오름차순 (P1 먼저)
    base_rules: list[dict]
    adjust_rules: list[dict]                 # apply_order 오름차순
    version: str
    source: str                              # 'DB' | 'CODE' | 'DB+CODE'
    _by_code: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self._by_code = {g["grade_code"]: g for g in self.grades}

    # ---------- 등급 ----------
    def codes(self) -> list[str]:
        return [g["grade_code"] for g in self.grades]

    def label(self, code: str) -> str:
        return self._by_code.get(code, {}).get("grade_name", code)

    def lowest(self) -> str:
        return self.grades[-1]["grade_code"]

    def _idx(self, code: str | None) -> int:
        codes = self.codes()
        return codes.index(code) if code in codes else len(codes) - 1

    def max(self, a: str | None, b: str | None) -> str | None:
        """둘 중 더 심각한 등급."""
        if not a:
            return b
        if not b:
            return a
        return a if self._idx(a) <= self._idx(b) else b

    def raise_by(self, code: str, steps: int = 1) -> str:
        return self.codes()[max(0, self._idx(code) - max(0, steps or 0))]

    def should_notify(self, code: str, report_count: int) -> bool:
        n = self._by_code.get(code, {}).get("notify_min_reports")
        return n is not None and report_count >= n

    def observe(self, code: str) -> bool:
        """알림 미대상일 때 관찰로 등록할지 (False 면 미대상 자동 종결)."""
        return bool(self._by_code.get(code, {}).get("observe_yn"))

    def unnotified_status(self, code: str) -> str:
        return "관찰" if self.observe(code) else "미대상"

    def roles(self, code: str) -> list[str]:
        raw = self._by_code.get(code, {}).get("recipient_roles") or ""
        return [r.strip() for r in raw.split(",") if r.strip()]

    def prefix(self, code: str) -> str:
        return self._by_code.get(code, {}).get("message_prefix") or "[장애알림]"

    # ---------- 기본 등급 ----------
    def base_grade(self, error_type: str, channel: str | None) -> tuple[str, dict | None]:
        """채널까지 일치하는 규칙을 우선, 없으면 채널 무관(NULL) 규칙."""
        exact = [r for r in self.base_rules if r["error_type"] == error_type and r.get("channel") and r["channel"] == channel]
        generic = [r for r in self.base_rules if r["error_type"] == error_type and not r.get("channel")]
        rule = (exact or generic or [None])[0]
        if rule:
            return rule["base_grade"], rule
        return self.lowest(), None

    # ---------- 조정 규칙 ----------
    def mass_threshold(self) -> int:
        r = next((r for r in self.adjust_rules if r["rule_type"] == "MASS_SIGNAL" and r.get("threshold")), None)
        return int(r["threshold"]) if r else settings.mass_signal_threshold

    def false_positive_rule(self) -> dict | None:
        return next((r for r in self.adjust_rules if r["rule_type"] == "FALSE_POSITIVE"), None)

    def llm_definitions(self) -> str:
        lines = []
        for g in self.grades:
            ex = f" (예: {g['judge_examples']})" if g.get("judge_examples") else ""
            lines.append(f"{g['grade_code']}({g['grade_name']}): {g['definition']}{ex}")
        return "\n".join(lines)


# ---------------------------------------------------------------------
# 코드 기본값 (DB 기준이 없을 때)
# ---------------------------------------------------------------------
_CODE_DEFS = {
    "P1": ("다수 고객의 핵심 거래가 계속 막히거나 금전 피해가 발생하는 장애, 또는 지급 기한이 임박했는데 대체수단 없이"
           " 거래가 계속 막혀 중대한 피해가 예상되는 장애", 1, False),
    "P2": ("로그인·인증·이체 등 핵심 기능을 사용할 수 없는 장애", None, True),   # 알림은 P1만, P2 는 관찰
    "P3": ("일부 기능 지연이나 화면 오류로 불편하지만 우회가 가능한 장애", None, False),
    "P4": ("영향이 미미하거나 고객 실수·정상 동작으로 보이는 건", None, False),
}


def _code_grades() -> list[dict]:
    return [{"grade_code": c, "grade_name": rules.SEVERITY_LABEL[c], "grade_order": i + 1,
             "definition": _CODE_DEFS[c][0], "judge_examples": None, "notify_min_reports": _CODE_DEFS[c][1],
             "observe_yn": _CODE_DEFS[c][2],
             "recipient_roles": ",".join(rules.RECIPIENT_ROLES[c]), "message_prefix": "[장애알림]"}
            for i, c in enumerate(rules.SEVERITY_ORDER)]


def _code_base_rules() -> list[dict]:
    return [{"rule_id": None, "error_type": t, "channel": None, "base_grade": g, "rationale": "코드 기본값"}
            for t, g in rules.BASE_SEVERITY.items()]


def _code_adjust_rules() -> list[dict]:
    return [
        {"rule_code": "PERSIST_P2", "rule_name": "지속 차단", "rule_type": "KEYWORD",
         "keywords": rules.PERSIST_SIGNALS, "threshold": None, "action_type": "RAISE_TO", "raise_steps": None,
         "target_grade": "P2", "condition_grade": None, "target_error_type": None, "apply_order": 5},
        {"rule_code": "ESC_IMPACT", "rule_name": "영향범위 확대 신호", "rule_type": "KEYWORD",
         "keywords": rules.ESCALATION_SIGNALS, "threshold": None, "action_type": "RAISE", "raise_steps": 1,
         "target_grade": None, "condition_grade": None, "target_error_type": None, "apply_order": 10},
        {"rule_code": "URGENT_P1", "rule_name": "기한 임박·대체수단 없음·지속 차단", "rule_type": "KEYWORD",
         "keywords": rules.URGENT_DEADLINE_SIGNALS, "threshold": None, "action_type": "RAISE_TO",
         "raise_steps": None, "target_grade": "P1", "condition_grade": None, "target_error_type": None,
         "apply_order": 15},
        {"rule_code": "RECOVERED_P3", "rule_name": "일시 실패 후 정상 진행", "rule_type": "KEYWORD",
         "keywords": rules.RECOVERED_SIGNALS, "threshold": None, "action_type": "LOWER_TO", "raise_steps": None,
         "target_grade": "P3", "condition_grade": None, "target_error_type": None, "apply_order": 25},
        {"rule_code": "RPT_MULTI", "rule_name": "복수 제보 시 P4 상향", "rule_type": "REPORT_COUNT",
         "keywords": None, "threshold": 2, "action_type": "SET_GRADE", "raise_steps": None,
         "target_grade": "P3", "condition_grade": "P4", "target_error_type": None, "apply_order": 20},
        {"rule_code": "MASS_P1", "rule_name": "대규모 장애 신호", "rule_type": "MASS_SIGNAL",
         "keywords": None, "threshold": settings.mass_signal_threshold, "action_type": "SET_GRADE",
         "raise_steps": None, "target_grade": "P1", "condition_grade": None, "target_error_type": None,
         "apply_order": 30},
        {"rule_code": "FP_CUSTOMER", "rule_name": "고객 귀책 오탐", "rule_type": "FALSE_POSITIVE",
         "keywords": rules.FALSE_POSITIVE_SIGNALS, "threshold": None, "action_type": "FALSE_POSITIVE",
         "raise_steps": None, "target_grade": "P4", "condition_grade": None, "target_error_type": None,
         "apply_order": 90},
    ]


# ---------------------------------------------------------------------
# 로드
# ---------------------------------------------------------------------
def tables_exist(db: Session) -> bool:
    return db.execute(text("SELECT to_regclass('public.severity_grade') IS NOT NULL")).scalar() is True


def load(db: Session, use_cache: bool = True) -> Criteria:
    now = time.time()
    if use_cache and _CACHE["value"] is not None and now - _CACHE["at"] < _TTL_SEC:
        return _CACHE["value"]

    grades = base = adjust = []
    latest = None
    if tables_exist(db):   # 테이블이 없을 때 쿼리 오류로 트랜잭션이 깨지지 않도록 먼저 확인
        grades = [dict(r) for r in db.execute(text(
            f"SELECT * FROM severity_grade WHERE {_ACTIVE} ORDER BY grade_order")).mappings().all()]
        base = [dict(r) for r in db.execute(text(
            f"SELECT * FROM severity_base_rule WHERE {_ACTIVE} ORDER BY error_type, channel NULLS LAST, rule_id"
        )).mappings().all()]
        adjust = [dict(r) for r in db.execute(text(
            f"SELECT * FROM severity_adjust_rule WHERE {_ACTIVE} ORDER BY apply_order, rule_code")).mappings().all()]
        latest = db.execute(text(f"""
            SELECT max(t) FROM (
              SELECT max(updated_at) t FROM severity_grade WHERE {_ACTIVE}
              UNION ALL SELECT max(updated_at) FROM severity_base_rule WHERE {_ACTIVE}
              UNION ALL SELECT max(updated_at) FROM severity_adjust_rule WHERE {_ACTIVE}) x
        """)).scalar()

    parts = [bool(grades), bool(base), bool(adjust)]
    source = "DB" if all(parts) else ("DB+CODE" if any(parts) else "CODE")
    grades = grades or _code_grades()
    base = base or _code_base_rules()
    adjust = adjust or _code_adjust_rules()
    if latest is not None and hasattr(latest, "astimezone"):
        version = f"{source}-{latest.astimezone(_KST).strftime('%Y%m%d%H%M%S')}"
    elif latest is not None:
        from datetime import datetime
        try:
            version = f"{source}-{datetime.fromisoformat(str(latest)).astimezone(_KST).strftime('%Y%m%d%H%M%S')}"
        except ValueError:
            version = f"{source}-{str(latest)[:19]}"
    else:
        version = "CODE-default"

    cr = Criteria(grades, base, adjust, version, source)
    _CACHE.update(at=now, value=cr)
    return cr


def invalidate() -> None:
    _CACHE.update(at=0.0, value=None)


# ---------------------------------------------------------------------
# 기준 관리 (조회·등록·수정) - API 에서 사용. 커밋은 호출하는 쪽에서 합니다.
# ---------------------------------------------------------------------
_TABLES = {
    "grade": ("severity_grade", "grade_code",
              {"grade_name", "grade_order", "definition", "judge_examples", "notify_min_reports", "observe_yn",
               "recipient_roles",
               "target_ack_min", "target_resolve_min", "message_prefix", "use_yn", "valid_from", "valid_to"}),
    "base": ("severity_base_rule", "rule_id",
             {"error_type", "channel", "system_name", "base_grade", "rationale", "use_yn", "valid_from", "valid_to"}),
    "adjust": ("severity_adjust_rule", "rule_code",
               {"rule_name", "rule_type", "keywords", "threshold", "action_type", "raise_steps", "target_grade",
                "condition_grade", "target_error_type", "apply_order", "description", "use_yn", "valid_from",
                "valid_to"}),
}


def list_all(db: Session) -> dict:
    """사용 여부·적용 기간과 관계없이 전체 기준 + 현재 적용 중인 버전."""
    cr = load(db, use_cache=False)
    if not tables_exist(db):
        return {"tables_exist": False, "version": cr.version, "source": cr.source,
                "grades": cr.grades, "base_rules": cr.base_rules, "adjust_rules": cr.adjust_rules}
    q = lambda sql: [dict(r) for r in db.execute(text(sql)).mappings().all()]  # noqa: E731
    return {
        "tables_exist": True, "version": cr.version, "source": cr.source,
        "grades": q("SELECT * FROM severity_grade ORDER BY grade_order"),
        "base_rules": q("SELECT * FROM severity_base_rule ORDER BY error_type, channel NULLS LAST, rule_id"),
        "adjust_rules": q("SELECT * FROM severity_adjust_rule ORDER BY apply_order, rule_code"),
    }


def _write(db: Session, kind: str, data: dict, key=None, *, user: str, reason: str | None) -> dict | None:
    table, pk, allowed = _TABLES[kind]
    vals = {k: v for k, v in data.items() if k in allowed}
    if key is None:            # 등록
        if kind == "adjust":
            vals["rule_code"] = data["rule_code"]
        if kind == "grade":
            vals["grade_code"] = data["grade_code"]
        vals.update(created_by=user, updated_by=user, change_reason=reason)
        cols = list(vals)
        row = db.execute(text(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(':' + c for c in cols)}) "
                              f"RETURNING *"), vals).mappings().first()
    else:                      # 수정
        if not vals:
            row = db.execute(text(f"SELECT * FROM {table} WHERE {pk} = :k"), {"k": key}).mappings().first()
        else:
            sets = ", ".join(f"{c} = :{c}" for c in vals)
            vals.update(k=key, u=user, r=reason)
            row = db.execute(text(f"UPDATE {table} SET {sets}, updated_by = :u, updated_at = now(), "
                                  f"change_reason = :r WHERE {pk} = :k RETURNING *"), vals).mappings().first()
    invalidate()
    return dict(row) if row else None


def save_grade(db, data, code=None, *, user, reason):
    return _write(db, "grade", data, code, user=user, reason=reason)


def save_base_rule(db, data, rule_id=None, *, user, reason):
    return _write(db, "base", data, rule_id, user=user, reason=reason)


def save_adjust_rule(db, data, rule_code=None, *, user, reason):
    return _write(db, "adjust", data, rule_code, user=user, reason=reason)
