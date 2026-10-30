"""사전 정의 규칙 (키워드 사전, 재현정보 추출, 유사도).

심각도 관련 상수(BASE_SEVERITY, ESCALATION_SIGNALS, FALSE_POSITIVE_SIGNALS, RECIPIENT_ROLES, SEVERITY_LABEL)는
DB 장애등급 판별기준(severity_* 테이블)이 없거나 비어 있을 때만 쓰는 코드 기본값입니다.
운영 기준은 DB에서 관리합니다 → app/services/criteria.py, sql/04_severity_criteria.sql
"""
import re

ERROR_TYPES = ["로그인", "인증", "조회", "이체", "UI오류", "기타"]

# 오류유형 키워드 (가중치)
TYPE_KEYWORDS: dict[str, dict[str, int]] = {
    "이체":   {"이체": 3, "송금": 3, "타행": 2, "처리중": 2, "출금": 2, "입금이 안": 2, "못 받": 2},
    "인증":   {"인증서": 3, "공동인증": 3, "인증 모듈": 3, "인증번호": 3, "본인인증": 3, "otp": 3,
               "인증 오류": 3, "생체인증": 2, "지문": 1, "인증 화면": 3, "인증 완료": 3, "인증을": 2,
               "인증 전화": 3, "신분증": 3, "본인확인": 2, "인증하": 2},
    "로그인": {"로그인": 3, "접속이 안": 2, "로그아웃": 1, "아이디": 1},
    "조회":   {"조회": 3, "거래내역": 2, "잔액": 2, "로딩": 2, "느려": 2, "느림": 2},
    "UI오류": {"화면이 멈": 3, "멈춘": 2, "반응이 없": 3, "버튼": 2, "하얀 화면": 3, "깨져": 2,
               "튕겨": 3, "앱이 꺼": 3, "먹통": 2, "안 눌려": 3, "눌리지 않": 3, "안 열려": 3, "불러오는": 2},
}
TYPE_PRIORITY = ["이체", "인증", "로그인", "조회", "UI오류"]

# 장애 신호어 (하나도 없으면 장애 아님)
ISSUE_SIGNALS = ["오류", "에러", "안 돼", "안돼", "안 되", "안되", "실패", "멈", "느려", "지연",
                 "처리중", "반응이 없", "튕", "꺼져", "먹통", "돌아가", "잠겼",
                 "끊어졌", "끊겼", "사용 불가", "이용할 수 없", "안 눌려", "눌리지 않", "안 열려",
                 "똑같아요", "똑같고", "계속 그래", "계속 나와", "안 나와", "안 와요", "할 수 없", "할 수가 없",
                 "확인할 수 없", "하얀 화면", "오래 걸려", "늦게 와", "늦었", "틀렸다고 나와", "로그아웃이 돼", "안 보여"]
# 신호어처럼 보이지만 장애가 아닌 표현 (신호어 검사 전에 지움)
NOT_SIGNAL_PHRASES = ["오류 없", "오류는 없", "지연이체", "면 안되나요", "면 안 되나요"]

# 개선의견: 해결·완료된 건에 대해 문구·안내·절차를 바꿔 달라는 요청 (알림 대상 아님)
IMPROVE_SIGNALS = ["좋겠어요", "좋겠습니다", "좋겠네요", "개선해", "바꿔주", "보완해", "의견을 남기", "의견 남기",
                   "넣어 주", "있으면 좋겠"]
DONE_SIGNALS = ["됐어요", "됐고", "완료했", "완료됐", "받았어요", "끝났어요", "개선됐", "해결됐", "해결됐어요",
                "잘 돼요", "이제 돼요"]
NOW_BLOCK_SIGNALS = ["지금도 안", "아직도 안", "아직 안 돼", "계속 안 돼", "여전히 안"]

# 고객 귀책/정상 동작 가능성 (오탐 신호)
FALSE_POSITIVE_SIGNALS = ["비밀번호를 몇 번 틀", "비밀번호 틀", "잊어버", "잠겼", "재설정", "5회 오류"]

# 영향 범위 확대 신호 (심각도 +1)
ESCALATION_SIGNALS = ["돈이 빠져나", "돈은 빠져나", "출금은 되", "이중 출금", "이중출금", "전체",
                      "모든 고객", "주변 사람들도", "다 안 된", "전부 안", "아무것도 안"]

# 지속 차단: 재시도·재설치 후에도 같은 오류 (최소 P2)
PERSIST_SIGNALS = ["지웠다 다시 깔", "다시 깔았", "껐다 켰는데", "캐시도 지우고", "다시 켜도 똑같", "다시 켜도 같",
                   "다시 해도 똑같", "다시 해도 안", "계속 그래요", "지금도 같은", "두 번 했는데 똑같",
                   "다시 발급하려고 해도 오류"]
# 기한 임박 + 대체수단 없음 + 지속 차단이 함께 확인되면 P1 ('그룹:단어', 그룹마다 하나 이상)
URGENT_DEADLINE_SIGNALS = (
    [f"기한:{w}" for w in ["분 남았", "까지 보내야", "까지 이체해야", "까지 입금해야", "시까지 보내", "마감이 얼마 안"]]
    + [f"대체수단:{w}" for w in ["다른 계좌도 없", "다른 방법도 없", "인터넷뱅킹도 같은", "인터넷뱅킹도 안",
                                 "대신 보낼 수 없", "다른 은행 계좌도 없"]]
    + [f"지속:{w}" for w in ["계속 오류", "다시 켜도 똑같", "다시 해도 똑같", "다시 해도 안", "계속 실패", "똑같아요"]]
)
# 일시 실패 후 정상 진행 (최대 P3, 대규모 신호면 적용 안 함)
RECOVERED_SIGNALS = ["이번에는 됐", "이제 열려", "지금은 됐", "넘어갔어요", "완료라고 나와", "완료됐다고 나와",
                     "접수 완료라고", "등록 완료라고"]

SEVERITY_ORDER = ["P1", "P2", "P3", "P4"]
SEVERITY_LABEL = {"P1": "긴급", "P2": "높음", "P3": "보통", "P4": "낮음"}
BASE_SEVERITY = {"이체": "P2", "로그인": "P2", "인증": "P2", "조회": "P3", "UI오류": "P3", "기타": "P4"}

# 심각도별 알림 대상 역할
RECIPIENT_ROLES = {"P1": ["담당", "부담당", "팀장"], "P2": ["담당", "부담당"], "P3": ["담당"], "P4": []}

# 유형별 초기 점검 가이드
CHECK_GUIDE = {
    "로그인": ["최근 앱/서버 배포 이력", "인증 토큰 발급·갱신 서버 로그", "특정 OS/앱 버전 집중 여부"],
    "인증":   ["인증 모듈/서버 인증서 유효기간", "인증 대외기관 응답 상태", "오류 코드별 발생 건수"],
    "조회":   ["조회 API 응답시간·DB 부하", "배치 작업과의 시간 중복", "특정 계좌 유형 집중 여부"],
    "이체":   ["대외기관(금융결제원) 연계 회선 상태", "전문 타임아웃·미처리 거래 건", "출금 후 미입금 건 즉시 확인"],
    "UI오류": ["최근 프론트엔드 배포 이력", "브라우저/OS 버전별 스크립트 오류", "CDN/정적 리소스 로딩 상태"],
    "기타":   ["관련 시스템 모니터링 지표", "최근 변경 작업 이력"],
}


def contains_any(text: str, words: list[str]) -> list[str]:
    low = text.lower()
    return [w for w in words if w.lower() in low]


def issue_signals(text: str) -> list[str]:
    """장애 신호어 (장애가 아닌 표현은 지우고 검사)."""
    for p in NOT_SIGNAL_PHRASES:
        text = text.replace(p, " ")
    return contains_any(text, ISSUE_SIGNALS)


def is_improvement(text: str) -> bool:
    """해결·완료 표현 + 개선 요청 표현이 있고 지금 막힌 업무가 없으면 개선의견."""
    return (bool(contains_any(text, IMPROVE_SIGNALS)) and bool(contains_any(text, DONE_SIGNALS))
            and not contains_any(text, NOW_BLOCK_SIGNALS))


def match_keyword_groups(text: str, keywords: list[str]) -> list[str] | None:
    """'그룹:단어' 형식 키워드는 그룹마다 하나 이상 포함돼야 일치 (예: 기한·대체수단·지속 차단 동시 충족).
    그룹 없는 키워드는 하나라도 포함되면 일치. 일치한 단어 목록, 불일치면 None."""
    groups: dict[str, list[str]] = {}
    for k in keywords:
        g, sep, w = k.partition(":")
        groups.setdefault(g if sep else "", []).append(w if sep else k)
    hits = []
    for words in groups.values():
        found = contains_any(text, words)
        if not found:
            return None
        hits += found
    return hits


def classify_error_type(text: str) -> tuple[str, dict[str, int]]:
    low = text.lower()
    scores = {t: sum(w * low.count(k.lower()) for k, w in kws.items()) for t, kws in TYPE_KEYWORDS.items()}
    best = max(TYPE_PRIORITY, key=lambda t: (scores[t], -TYPE_PRIORITY.index(t)))
    return (best if scores[best] > 0 else "기타"), scores


def detect_channel(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ["홈페이지", "인터넷뱅킹", "pc", "크롬", "엣지", "브라우저", "웹"]):
        return "웹"
    if any(k in low for k in ["앱", "모바일", "아이폰", "갤럭시", "안드로이드", "ios", "android"]):
        return "앱"
    if "ars" in low:
        return "ARS"
    return "기타"


def extract_env(text: str) -> dict:
    env: dict[str, str] = {}
    low = text.lower()
    if re.search(r"아이폰|ios|iphone", low):
        env["os"] = "iOS"
    elif re.search(r"안드로이드|갤럭시|android", low):
        env["os"] = "Android"
    elif re.search(r"윈도우|windows", low):
        env["os"] = "Windows"
    elif re.search(r"맥북|mac", low):
        env["os"] = "macOS"

    m = re.search(r"(아이폰\s?\d+(?:\s?프로)?|갤럭시\s?[A-Za-z]?\d+)", text)
    if m:
        env["device"] = m.group(1)
    elif re.search(r"\bpc\b|PC", text):
        env["device"] = "PC"

    m = re.search(r"(?<![\d.])(\d+\.\d+\.\d+)(?![\d.])", text)
    if m:
        env["app_version"] = m.group(1)

    for k, v in {"크롬": "Chrome", "엣지": "Edge", "사파리": "Safari", "chrome": "Chrome"}.items():
        if k in low:
            env["browser"] = v
            break

    m = re.search(r"(?<![A-Za-z0-9])([A-Z]-?\d{3,5})(?!\d)", text)
    if m:
        env["error_code"] = m.group(1)

    m = re.search(r"(일시적인 오류[^.,]*|[가-힣]*\s?오류 코드[^.,]*)", text)
    if m:
        env["error_message"] = m.group(1).strip()[:80]

    m = re.search(r"((?:오늘|어제|아까|오전|오후|아침)[가-힣 ]{0,8}|[가-힣\d]+\s?분\s?(?:전|째)[가-힣 ]{0,8})", text)
    if m:
        env["occurred_at_text"] = m.group(1).strip()
    return env


# ---------- 유사도 (문자 bigram Jaccard: 한국어에 추가 라이브러리 없이 동작) ----------
def _bigrams(text: str) -> set[str]:
    s = re.sub(r"[^0-9a-zA-Z가-힣]", "", text.lower())
    return {s[i:i + 2] for i in range(len(s) - 1)}


def similarity(a: str, b: str) -> float:
    A, B = _bigrams(a or ""), _bigrams(b or "")
    if not A or not B:
        return 0.0
    return round(len(A & B) / len(A | B), 3)


def raise_severity(sev: str, steps: int = 1) -> str:
    i = max(0, SEVERITY_ORDER.index(sev) - steps)
    return SEVERITY_ORDER[i]


def max_severity(a: str | None, b: str | None) -> str | None:
    if not a:
        return b
    if not b:
        return a
    return a if SEVERITY_ORDER.index(a) <= SEVERITY_ORDER.index(b) else b


def should_notify(severity: str, report_count: int) -> bool:
    return severity == "P1"      # 장애 알림은 P1만
