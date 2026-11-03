"""초기 분석(incident_alert.analysis) 문장을 구조로 나눔

LLM은 3~5문장 서술형, 규칙 기반은 '우선 점검: a, b' 같은 줄 단위로 씁니다. (app/agents/severity.py)
저장 형식은 그대로 두고 보여줄 때만 상황·추정 원인 / 점검 항목 / 참고(유사 사례·관찰)로 나눕니다.
장애 상세 화면(frontend/src/utils/analysis.js)과 같은 규칙이므로 한쪽을 바꾸면 같이 고칩니다.
"""
import re

CAUSE_RE = re.compile(r"가능성|의심|보입니다|추정|원인|문제보다")
NOTE_RE = re.compile(r"ERR-\d+|유사 사례|과거 사례|유사한 과거|모니터링|추이|관찰")
ACTION_RE = re.compile(r"(세요|십시오)\.?$|것이 좋습니다\.?$")
CHECK_RE = re.compile(r"점검 ?포인트(?:는|은)?\s*:?\s*(.+)$")
RULE_CHECK_RE = re.compile(r"^우선 점검\s*:\s*(.+)$")
CIRCLED_RE = re.compile(r"[①-⑳]")


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"\n+|(?<=[다요]\.)\s+", text) if s.strip()]


def _split_top_level(text: str) -> list[str]:
    """괄호 안 쉼표는 나누지 않음."""
    out, depth, cur = [], 0, ""
    for ch in text:
        if ch in "(（[":
            depth += 1
        if ch in ")）]":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return out


def _clean_item(s: str) -> str:
    s = re.sub(r"[,，]$", "", s.strip())
    s = re.sub(r"(입니다|등입니다)\.?$", "", s)
    return re.sub(r"\.$", "", s).strip()


def _check_items(sentence: str) -> list[str] | None:
    """'점검 포인트는 ① a ② b 입니다.' / '점검 포인트는 a, b, c입니다.' / '우선 점검: a, b'"""
    m = CHECK_RE.search(sentence) or RULE_CHECK_RE.search(sentence)
    if not m:
        return None
    body = m.group(1)
    parts = CIRCLED_RE.split(body)[1:] if CIRCLED_RE.search(body) else _split_top_level(body)
    return [i for i in (_clean_item(p) for p in parts) if i]


def structure(text: str | None) -> dict:
    result = {"causes": [], "checks": [], "notes": []}
    for s in _split_sentences(text or ""):
        if re.match(r"^재현 환경\s*:", s):
            continue                                   # 재현 정보 항목에 이미 표시
        items = _check_items(s)
        if items is not None:
            result["checks"].extend(items)
        elif NOTE_RE.search(s):
            result["notes"].append(s)
        elif CAUSE_RE.search(s):
            result["causes"].append(s)
        elif ACTION_RE.search(s):
            result["checks"].append(_clean_item(s))
        else:
            result["causes"].append(s)
    return result


def message_text(text: str | None) -> str:
    """메신저 알림 「초기 분석」 본문."""
    parts = structure(text)
    if not any(parts.values()):
        return " -"
    lines = []
    if parts["causes"]:
        lines.append(" [상황 · 추정 원인]")
        lines += [f" · {s}" for s in parts["causes"]]
    if parts["checks"]:
        lines.append(" [점검 항목]")
        lines += [f" {i}) {s}" for i, s in enumerate(parts["checks"], 1)]
    if parts["notes"]:
        lines.append(" [참고]")
        lines += [f" · {s}" for s in parts["notes"]]
    return "\n".join(lines)
