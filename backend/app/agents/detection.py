"""① 장애 감지 에이전트

상담이력 등록 후 실행되어 두 가지를 각각 분석하고 종합해 장애 대상 여부를 판별합니다.
  1) STT 원문 분석   : 고객 발화에서 장애 신호어 · 오류 유형 · 재현정보(OS/기기/앱버전 등) 식별
  2) 상담이력 분석   : 상담유형 · 접촉채널 · 상담요약에서 장애 관련 정보 식별
  → 종합 판정: 둘 중 하나라도 장애로 식별되면 장애 대상 → 중복제보 통합 에이전트로,
               둘 다 아니면 에이전트 종료.
LLM 사용 시 두 분석 결과를 함께 주고 최종 판단과 구조화(제목·증상·환경)를 맡깁니다.
"""
from app.agents import llm, rules
from app.services import criteria

NAME = "장애감지 에이전트"

SYSTEM = """당신은 금융 콜센터 상담 내용을 분석해 웹/앱 전산 장애를 감지하는 에이전트입니다.
STT 원문(고객·상담사 대화)과 상담사가 등록한 상담이력을 각각 분석한 뒤 종합 판단하세요.
고객 단순 문의, 고객 실수(비밀번호 분실 등)는 장애가 아닐 수 있으나, 시스템 오류 가능성이 있으면 is_incident=true 로 두세요.
상담사의 마무리·전달 멘트(예: "긴급 건으로 전달하겠습니다")는 응대 표현일 뿐이므로 장애 여부·심각도 판단 근거로 쓰지 말고, 고객이 말한 사실로 판단하세요.
category 구분:
 - "장애": 지금 업무 진행이 막혀 있거나, 일시 실패 후 정상 진행됐더라도 상담 중 오류가 발생한 건
 - "개선의견": 이미 해결·완료된 건에 대해 화면 문구·안내·절차를 바꿔 달라는 의견 (과거 오류 경험을 말해도 지금 막힌 업무가 없으면 개선의견). is_incident=false
 - "일반": 장애도 개선의견도 아닌 일반 문의. is_incident=false
출력 JSON 스키마:
{"category": "장애|개선의견|일반", "stt_is_incident": bool, "stt_reason": "STT 원문 분석 근거",
 "consult_is_incident": bool, "consult_reason": "상담이력 분석 근거",
 "is_incident": bool, "error_type": "로그인|인증|조회|이체|UI오류|기타", "channel": "앱|웹|ARS|기타",
 "severity_candidate": "P1|P2|P3|P4", "title": "30자 이내 장애 제목", "symptoms": "증상 요약 1~2문장",
 "env": {"os": "", "device": "", "app_version": "", "browser": "", "error_code": "", "error_message": "",
         "occurred_at_text": ""}, "confidence": 0.0~1.0, "reason": "종합 판단 근거"}"""


def analyze_stt(customer_text: str) -> dict:
    """STT 원문(고객 발화) 분석."""
    signals = rules.contains_any(customer_text, rules.ISSUE_SIGNALS)
    error_type, scores = rules.classify_error_type(customer_text)
    env = rules.extract_env(customer_text)
    is_incident = bool(signals) and (error_type != "기타" or len(signals) >= 2)
    improvement = rules.is_improvement(customer_text)
    return {
        "is_incident": is_incident and not improvement,
        "improvement": improvement,
        "error_type": error_type,
        "signals": signals[:8],
        "channel": rules.detect_channel(customer_text),
        "env": env,
        "reason": ("해결·완료된 건에 대한 개선 요청 표현 (개선의견)" if improvement
                   else f"고객 발화 장애 신호어 {signals[:5]}, 유형 '{error_type}'" if signals
                   else "고객 발화에 장애 신호어 없음"),
    }


def analyze_consult(consult: dict) -> dict:
    """상담이력(상담유형·접촉채널·상담요약) 분석."""
    summary = f"{consult.get('summary') or ''} {consult.get('memo') or ''}"
    signals = rules.contains_any(summary, rules.ISSUE_SIGNALS)
    error_type, _ = rules.classify_error_type(summary)
    is_error_consult = consult.get("consult_type") == "전산오류문의"
    is_incident = (is_error_consult and (bool(signals) or error_type != "기타")) or len(signals) >= 2
    parts = [f"상담유형 '{consult.get('consult_type')}'"]
    if consult.get("channel"):
        parts.append(f"접촉채널 '{consult['channel']}'")
    parts.append(f"요약 신호어 {signals[:5]}" if signals else "요약에 장애 신호어 없음")
    return {
        "is_incident": is_incident,
        "error_type": error_type,
        "signals": signals[:8],
        "channel": consult.get("channel"),
        "reason": ", ".join(parts),
    }


def _combine(cr, stt: dict, cons: dict, customer_text: str) -> dict:
    # 고객 발화가 개선 의견이면 상담이력(상담유형 등)과 관계없이 장애로 보지 않음
    is_incident = not stt["improvement"] and (stt["is_incident"] or cons["is_incident"])
    category = "개선의견" if stt["improvement"] else ("장애" if is_incident else "일반")
    error_type = stt["error_type"] if stt["error_type"] != "기타" else cons["error_type"]
    form_channel = cons.get("channel")
    channel = form_channel if form_channel and form_channel != "기타" else stt["channel"]
    env = stt["env"]
    first_issue = next((s for s in customer_text.split("\n") if rules.contains_any(s, rules.ISSUE_SIGNALS)), "")
    both = stt["is_incident"] and cons["is_incident"]
    n_sig = len(set(stt["signals"]) | set(cons["signals"]))
    if category == "개선의견":
        basis = "해결·완료된 건에 대한 개선 의견 → 알림 없이 개선의견으로 기록"
    elif both:
        basis = "STT 원문 · 상담이력 모두 장애로 식별"
    elif is_incident:
        basis = ("STT 원문" if stt["is_incident"] else "상담이력") + "에서만 장애로 식별 → 장애 대상으로 판단"
    else:
        basis = "STT 원문 · 상담이력 모두 장애 아님"
    return {
        "is_incident": is_incident,
        "category": category,
        "error_type": error_type,
        "channel": channel,
        "severity_candidate": cr.base_grade(error_type, channel)[0],
        "title": f"[{channel}] {error_type}{'' if error_type.endswith('오류') else ' 오류'}"
                 + (f" ({env['os']})" if env.get("os") else ""),
        "symptoms": (first_issue.strip() or cons.get("reason", ""))[:200],
        "env": env,
        "confidence": round(min(1.0, (0.5 if both else 0.35) + 0.07 * n_sig), 2),
        "reason": basis,
    }


def run(db, ctx: dict) -> tuple[str, str, dict]:
    consult, call = ctx["consult"], ctx.get("call") or {}
    customer_lines = [u["text"] for u in call.get("utterances", []) if u["speaker"] == "CUSTOMER"]
    customer_text = "\n".join(customer_lines) or consult["summary"]

    cr = criteria.load(db)
    stt = analyze_stt(customer_text)
    cons = analyze_consult(consult)
    result, source = _combine(cr, stt, cons, customer_text), "규칙"

    if llm.enabled():
        transcript = "\n".join(f"{'상담사' if u['speaker'] == 'AGENT' else '고객'}: {u['text']}"
                               for u in call.get("utterances", []))
        ans = llm.ask_json(SYSTEM, f"""[STT 원문]
{transcript}

[상담이력]
고객번호: {consult.get('customer_id')} / 상담유형: {consult['consult_type']} / 접촉채널: {consult.get('channel')}
접촉결과: {consult.get('result_status')}
상담요약: {consult['summary']}

[규칙 기반 1차 분석]
STT 원문 분석: {stt}
상담이력 분석: {cons}
종합: {result}""")
        if ans and ans.get("error_type") in rules.ERROR_TYPES:
            ctx["llm_used"] = True
            source = "LLM"
            if isinstance(ans.get("stt_is_incident"), bool):
                stt = {**stt, "is_incident": ans["stt_is_incident"], "reason": ans.get("stt_reason") or stt["reason"]}
            if isinstance(ans.get("consult_is_incident"), bool):
                cons = {**cons, "is_incident": ans["consult_is_incident"],
                        "reason": ans.get("consult_reason") or cons["reason"]}
            ans["env"] = {**result["env"], **{k: v for k, v in (ans.get("env") or {}).items() if v}}
            if ans.get("severity_candidate") not in cr.codes():
                ans["severity_candidate"] = result["severity_candidate"]
            if ans.get("category") in ("장애", "개선의견", "일반"):
                ans["is_incident"] = ans["category"] == "장애"
            keep = ("is_incident", "category", "error_type", "channel", "severity_candidate", "title", "symptoms",
                    "env", "confidence", "reason")
            result = {**result, **{k: ans[k] for k in keep if k in ans and ans[k] not in (None, "")}}

    result["source"] = source
    result["stt_analysis"] = {k: stt[k] for k in ("is_incident", "error_type", "signals", "reason")}
    result["consult_analysis"] = {k: cons[k] for k in ("is_incident", "error_type", "signals", "reason")}
    ctx["detection"] = result
    ctx["customer_text"] = customer_text

    mark = lambda a: "장애" if a["is_incident"] else "정상"   # noqa: E731
    sub = f"STT 원문: {mark(stt)} · 상담이력: {mark(cons)}"
    if result.get("category") == "개선의견":
        return "DONE", (f"개선의견 감지 ({source}) - {result['reason']} → 알림 없이 개선의견으로 기록, "
                        f"유형={result['error_type']}, 채널={result['channel']}"), result
    if not result["is_incident"]:
        return "SKIPPED", f"장애 미감지 ({source}) - {sub} → 일반 상담으로 판단, 에이전트 종료", result
    env_txt = ", ".join(f"{k}={v}" for k, v in result["env"].items() if k in ("os", "device", "app_version", "browser"))
    return "DONE", (f"장애 감지 ({source}) - {sub} → 유형={result['error_type']}, 채널={result['channel']}, "
                    f"심각도 후보={result['severity_candidate']}" + (f", 환경[{env_txt}]" if env_txt else "")), result
