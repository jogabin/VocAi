"""상담요약 초안 작성 (상담이력등록 화면 SCR-03 · 'STT에서 초안 만들기')

STT 원문 전체(고객·상담사 대화)를 읽고 **상담사가 상담이력에 적는 요약**처럼 정리합니다.
고객 발화를 그대로 잘라 붙이지 않고, 아래 3단 구성으로 다시 씁니다.
  [문의] 고객이 무엇을 왜 문의했는지 (업무·증상·발생 시점·영향 범위)
  [확인] 상담사가 상담 중 확인한 사항 (오류 메시지·코드, 기기·OS·앱 버전·브라우저, 금액 등)
  [처리] 상담사의 판단과 조치, 결과 (안내 완료 / 담당 부서 전달 등)

LLM 이 켜져 있으면 LLM 이 작성하고, 꺼져 있거나 실패하면 규칙 기반으로 같은 형식을 만듭니다.
"""
import re

from app.agents import llm, rules

SYSTEM = """당신은 금융 콜센터 상담사입니다. 방금 끝난 통화의 STT 원문 전체를 읽고, 상담이력에 등록할 '상담요약'을 상담사 입장에서 작성하세요.
작성 규칙:
- 고객 발화를 그대로 옮기지 말고, 대화 전체 흐름을 상담사가 정리한 업무 기록 문체로 다시 쓰세요. (~함, ~요청함, ~안내함, ~전달함)
- 아래 3줄 형식을 지키세요. 각 줄은 한 문장, 40~70자 안팎의 중간 길이로 쓰고 전체 200자 이내로 쓰세요.
  핵심(업무·증상·확인 사항·조치)만 남기고, 같은 말을 되풀이하거나 부가 설명을 늘어놓지 마세요.
  [문의] 고객이 어떤 업무에서 어떤 문제/요청으로 문의했는지 (발생 시점·영향 범위가 언급되면 포함)
  [확인] 상담 중 확인한 사항 (오류 메시지·오류코드, 기기·OS·앱 버전·브라우저, 금액·시간 등). 확인한 것이 없으면 '특이사항 없음'
  [처리] 상담사의 판단과 조치 및 결과 (예: 전산 오류로 판단하여 담당 부서에 전달함 / 이용 방법 안내 후 종료)
- 대화에 없는 내용은 추측하지 마세요. 고객 개인정보(계좌번호·주민번호 등)는 적지 마세요.
출력 JSON 스키마: {"summary": "[문의] ...\\n[확인] ...\\n[처리] ..."}"""

# ---------------------------------------------------------------------------
# 규칙 기반 사전
# ---------------------------------------------------------------------------
# 업무(문의 대상) — 앞에 있을수록 우선
TOPICS: list[tuple[str, str]] = [
    (r"타행.{0,6}(이체|송금)|(이체|송금).{0,6}타행", "타행 이체"),
    (r"이체|송금", "이체"),
    (r"공동인증서|인증서", "공동인증서 인증"),
    (r"인증번호|본인인증|otp", "본인인증"),
    (r"거래내역", "거래내역 조회"),
    (r"잔액", "잔액 조회"),
    (r"대출", "대출 신청"),
    (r"카드.{0,6}한도|한도.{0,6}(상향|올리)", "카드 한도 상향"),
    (r"주소.{0,4}(변경|바꾸)", "주소 변경"),
    (r"비밀번호.{0,6}(재설정|변경)", "비밀번호 재설정"),
    (r"로그인", "로그인"),
    (r"조회", "조회"),
]

# 증상 → 정리된 표현
SYMPTOMS: list[tuple[str, str]] = [
    (r"(돈|금액).{0,6}빠져나.{0,20}(못 받|안 들어|입금이 안)", "출금 후 수취인 미입금"),
    (r"처리\s?중", "'처리중' 상태 지속"),
    (r"일시적인 오류", "'일시적인 오류' 메시지 발생"),
    (r"로그인 화면으로 (다시 )?돌아", "로그인 화면 반복 복귀"),
    (r"반응이 없|눌러도 안", "버튼 무반응"),
    (r"화면이 멈|멈춘|멈춰", "화면 멈춤"),
    (r"로딩|느려|느림|지연", "로딩 지연"),
    (r"튕겨|앱이 꺼|꺼져", "앱 강제 종료"),
    (r"하얀 화면|깨져", "화면 표시 오류"),
    (r"인증서 오류|인증 모듈 오류|인증 오류", "인증 오류 발생"),
    (r"잠겼|잠금", "계정 잠김"),
]

# 상담사가 확인한 항목 (상담사 질문 → 항목명)
ASKED: list[tuple[str, str]] = [
    (r"오류 (메시지|문구)", "오류 메시지"),
    (r"오류 코드", "오류코드"),
    (r"기종|휴대폰|핸드폰", "기기"),
    (r"앱 버전|버전", "앱 버전"),
    (r"브라우저", "브라우저"),
    (r"언제부터|시간|시각", "발생 시점"),
    (r"금액", "금액"),
]

TIME = re.compile(r"(오늘\s?(?:아침|오전|오후|저녁)|어제|(?:오전|오후)\s?[가-힣\d]+\s?시(?:쯤)?|[가-힣\d]+\s?분\s?(?:전|째))")
MONEY = re.compile(r"([일이삼사오육칠팔구십백천\d,]+\s?(?:만|억)\s?원|\d[\d,]{3,}\s?원)")


def _find(patterns: list[tuple[str, str]], text: str, many: bool = False):
    hits = []
    for pat, label in patterns:
        if re.search(pat, text, re.I) and label not in hits:
            hits.append(label)
            if not many:
                break
    return hits if many else (hits[0] if hits else None)


def _env_text(env: dict) -> str:
    parts = []
    if env.get("device"):
        parts.append(env["device"])
    if env.get("os") and env["os"] not in (env.get("device") or ""):
        parts.append(env["os"])
    if env.get("app_version"):
        parts.append(f"앱 {env['app_version']}")
    if env.get("browser"):
        parts.append(env["browser"])
    return " · ".join(parts)


def _times(text: str) -> tuple[str | None, str | None]:
    """(경과/시작 시점, 시각) — 예: ('이십 분째', '오후 두 시쯤')"""
    since = clock = None
    for m in TIME.finditer(text):
        t = re.sub(r"\s+", " ", m.group(1)).strip()
        if t.endswith("시") or t.endswith("쯤"):
            clock = clock or t
        else:
            since = since or t
    return since, clock


def _josa(word: str, a: str, b: str) -> str:
    """받침 유무로 조사 선택 (a: 받침 있음, b: 없음)."""
    ch = word[-1] if word else ""
    if "가" <= ch <= "힣":
        return a if (ord(ch) - 0xAC00) % 28 else b
    return b


def rule_summary(utterances: list[dict]) -> str:
    cust = " ".join(u["text"] for u in utterances if u["speaker"] == "CUSTOMER")
    agent_lines = [u["text"] for u in utterances if u["speaker"] == "AGENT"]
    agent = " ".join(agent_lines)
    if not cust.strip():
        return ""

    channel = rules.detect_channel(cust)
    ch_txt = {"앱": "모바일 앱", "웹": "PC 홈페이지(인터넷뱅킹)", "ARS": "ARS"}.get(channel, "")
    topic = _find(TOPICS, cust) or "서비스 이용"
    symptoms = _find(SYMPTOMS, cust, many=True)
    signals = rules.contains_any(cust, rules.ISSUE_SIGNALS)
    customer_fault = bool(rules.contains_any(cust + " " + agent, rules.FALSE_POSITIVE_SIGNALS))
    env = rules.extract_env(cust)

    # ---------------- [문의] ----------------
    where = f"{ch_txt} {topic}".strip()
    if symptoms or signals:
        sym = ", ".join(symptoms[:3]) if symptoms else "이용 불가"
        ask = f"고객이 {where} 시 {sym} 증상으로 문의함."
    elif topic != "서비스 이용":
        ask = f"고객이 {topic} 관련하여 문의함."
    else:
        ask = "고객이 일반 업무 관련하여 문의함."

    extra = []
    since, clock = _times(cust)
    if re.search(r"업데이트", cust):
        if since and since.endswith("전"):
            extra.append(f"{since}부터, 앱 업데이트 이후 발생")
        else:
            extra.append(f"{since + ' ' if since and since.startswith(('오늘', '어제')) else ''}앱 업데이트 이후 발생")
    elif since and since.endswith("째"):
        extra.append(f"{since} 지속")
    elif since:
        extra.append(f"{since}부터 발생")
    if rules.contains_any(cust, ["주변 사람들도", "다 안 된", "다른 사람", "가족들도"]):
        extra.append("주변 이용자도 동일 증상이라고 함")
    if extra:
        ask += f" ({', '.join(extra)})"

    # ---------------- [확인] ----------------
    checks = []
    if env.get("error_code"):
        checks.append(f"오류코드 {env['error_code']}")
    elif env.get("error_message") and not any("일시적인 오류" in x for x in symptoms):
        checks.append(f"오류 메시지 '{env['error_message']}'")
    env_txt = _env_text(env)
    if env_txt:
        checks.append(f"이용 환경 {env_txt}")
    money = MONEY.search(cust)
    if money:
        checks.append(f"{clock + ' ' if clock else ''}{money.group(1).replace(' ', '')} {topic} 건")
    if customer_fault:
        checks.append("비밀번호 입력 오류 누적으로 인한 잠금으로 확인")
    if not checks:
        asked = _find(ASKED, " ".join(l for l in agent_lines if re.search(r"\?|까요|나요|세요", l)), many=True)
        checks.append(f"{', '.join(asked)} 확인" if asked else "특이사항 없음")
    confirm = ", ".join(checks)
    if confirm != "특이사항 없음" and not confirm.endswith("확인"):
        confirm += " 확인"
    confirm += "."

    # ---------------- [처리] ----------------
    if customer_fault:
        act = "고객 귀책(비밀번호 오류)으로 판단하여 본인인증 후 비밀번호 재설정 방법을 안내함."
    elif re.search(r"전달|접수|확인 요청|이관", agent):
        kind = "전산 오류" if (symptoms or signals) else "확인 필요 건"
        if re.search(r"동일 증상|같은 증상|다른 고객", agent):
            act = f"동일 증상 문의가 접수되고 있어 {kind}로 판단하여 전산 담당 부서에 전달함."
        else:
            act = f"{kind}로 판단하여 전산 담당 부서에 {'확인을 요청함' if '확인 요청' in agent else '전달함'}."
        if "이체" in topic and money:
            act = act.rstrip(".") + " (미입금 거래 확인 필요)."
    elif re.search(r"바로 변경|변경해 드|처리해 드|바꿔 드", agent) or re.search(r"바꿔 주세요|해 주세요", cust):
        act = f"고객 요청에 따라 {topic}을 직접 처리함."
    elif re.search(r"메뉴|신청이 가능|가능하|안내", agent):
        act = f"{topic} 이용 방법을 안내하고 상담 종료함."
    else:
        act = "문의 내용 안내 후 상담 종료함."
    act = act.replace(f"{topic}을", f"{topic}{_josa(topic, '을', '를')}")

    return f"[문의] {ask}\n[확인] {confirm}\n[처리] {act}"


def draft(call: dict) -> dict:
    """STT 통화(발화 포함) → {'summary': str, 'source': 'LLM'|'규칙'}"""
    utterances = call.get("utterances") or []
    base = rule_summary(utterances)
    if llm.enabled() and utterances:
        transcript = "\n".join(f"{'상담사' if u['speaker'] == 'AGENT' else '고객'}: {u['text']}" for u in utterances)
        ans = llm.ask_json(SYSTEM, f"[STT 원문 전체]\n{transcript}", max_tokens=600)
        text = (ans or {}).get("summary")
        if isinstance(text, str) and len(text.strip()) >= 10:
            return {"summary": text.strip()[:1000], "source": "LLM"}
    return {"summary": base, "source": "규칙"}
