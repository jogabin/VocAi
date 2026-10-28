"""④ 메신저 전송 에이전트 (+ 장애이력 등록)

메신저 전송 대상으로 선정된 장애 정보로
  1) 1차 수신자: 인사정보(employee, 인사정보 조회 API와 같은 테이블)에서
                 해당 오류유형을 담당하는 근무 중 IT담당자 중 등급별 수신 역할(판별기준)에 맞는 사람
  2) 2차 수신자: 비슷한 과거 장애를 처리(해결)한 담당자
  3) 장애 개요 · 증상 · 재현정보 · 초기 분석 · 과거 해결 사례 · 장애 상세 화면 링크를 담은 템플릿 작성
  4) 1차 · 2차 수신자에게 메신저 전송, 장애알림 정보와 메신저 전송 이력 등록
알림 미대상이면 '장애이력 등록' 노드에서 장애알림 정보만 등록합니다.
  - 등급 정의의 관찰 여부(observe_yn) 체크 → '관찰' (센터관리자가 확인 후 수동 알림 전송 또는 종결)
  - 관찰 여부 미체크 → '미대상' 자동 종결 (같은 증상 추가 제보가 60분 안에 쌓이면 재판정)
  - 2차 과거 오탐 사례 일치 → '오탐'
IT담당자(담당자)는 메신저 알림이 나갈 때 지정합니다. (관찰·미대상 건은 담당자 없음)
"""
from zoneinfo import ZoneInfo

from app.database import settings
from app.services import criteria, messenger, repo

NAME = "메신저 전송 에이전트"
RECORD_NAME = "장애이력 등록"
KST = ZoneInfo("Asia/Seoul")


def detail_url(incident_id: int) -> str:
    return f"{settings.app_base_url.rstrip('/')}/#/incident?id={incident_id}"


# ---------------------------------------------------------------------
# 수신자 식별
# ---------------------------------------------------------------------
def primary_recipients(db, error_type: str, severity: str) -> list[dict]:
    """1차: 인사정보의 담당 IT담당자 중 판별기준 수신 역할에 해당하는 사람."""
    roles = criteria.load(db).roles(severity)
    staff = repo.find_it_staff(db, error_type) or repo.find_it_staff(db, "기타")
    picked = [e for e in staff if e["duty_role"] in roles] or staff[:1]
    return picked


def secondary_recipients(db, similar: list[dict], exclude_ids: set) -> tuple[list[dict], dict]:
    """2차: 비슷한 과거 장애를 처리한 담당자. (수신자 목록, {incident_id: 처리자명})"""
    solved_ids = [c["incident_id"] for c in similar if c.get("status") == "해결"]
    resolvers = repo.past_resolvers(db, solved_ids)
    emps = {e["emp_id"]: e for e in repo.employees_by_ids(db, [r["emp_id"] for r in resolvers])}
    names = {r["incident_id"]: emps[r["emp_id"]]["emp_name"] for r in resolvers if r["emp_id"] in emps}
    picked, seen = [], set(exclude_ids)
    for r in resolvers:
        e = emps.get(r["emp_id"])
        if e and e["on_duty"] and e["messenger_id"] and e["emp_id"] not in seen:
            picked.append({**e, "for_incident": r["incident_id"]})
            seen.add(e["emp_id"])
    return picked, names


# ---------------------------------------------------------------------
# 메시지 템플릿
# ---------------------------------------------------------------------
def compose(db, inc: dict, sev: dict, consult: dict, primary: list[dict], secondary: list[dict],
            resolver_names: dict) -> tuple[str, str]:
    cr = criteria.load(db)
    label = cr.label(inc["severity"])
    prefix = "[대규모 장애]" if inc.get("mass_signal") else cr.prefix(inc["severity"])
    title = f"{prefix}[{inc['severity']} {label}] {inc['title']}"
    env = inc.get("env_info") or {}
    env_txt = " / ".join(f"{k}: {v}" for k, v in env.items() if v) or "-"
    solved = [c for c in (sev.get("similar_cases") or []) if c.get("status") == "해결"]
    if solved:
        cases = []
        for c in solved:
            who = resolver_names.get(c["incident_id"])
            cases.append(f" · {repo.incident_no(c['incident_id'])} {c['title']} (유사도 {c['similarity']}"
                         + (f", 처리자 {who}" if who else "") + ")")
            if c.get("resolution"):
                cases.append(f"   → {c['resolution']}")
        case_txt = "\n".join(cases)
    else:
        case_txt = " · 비슷한 과거 해결 사례 없음"
    fmt = lambda e: f"{e['emp_name']}({e.get('duty_role') or '-'})"   # noqa: E731
    first = f"{inc['first_reported_at'].astimezone(KST):%H:%M}"
    last = f"{inc['last_reported_at'].astimezone(KST):%H:%M}"
    body = f"""▣ 장애 개요
 · 장애번호 : {repo.incident_no(inc['incident_id'])}
 · 등급 : {inc['severity']} ({label}){'  ※ 동일유형 다발 - 대규모 장애 신호' if inc.get('mass_signal') else ''}
 · 오류유형 : {inc['error_type']} / 접촉채널 : {inc.get('channel') or '-'}
 · 누적 제보 : {inc['report_count']}건 · 독립 고객 {inc.get('customer_count') or 1}명 (최초 {first} · 최근 {last})

▣ 증상
 {inc.get('symptoms') or '-'}

▣ 재현 정보
 {env_txt}

▣ 최근 제보
 상담#{consult['consult_id']} {consult.get('customer_name') or ''} 고객 · {consult.get('agent_name') or ''}

▣ 초기 분석
{sev.get('analysis') or '-'}

▣ 과거 해결 사례
{case_txt}

▣ 수신자
 · 1차(담당) : {', '.join(fmt(e) for e in primary) or '-'}
 · 2차(유사 장애 처리자) : {', '.join(fmt(e) for e in secondary) or '-'}

▶ 장애 상세 보기 · 처리 입력
 {detail_url(inc['incident_id'])}

※ VOC 자율형 장애 알림 AI Agent 자동 발송"""
    return title, body


def manual_draft(db, inc: dict, severity: str, sender: str) -> dict:
    """관찰 장애 수동 알림: 추천 수신자(1차 등급별 수신 역할 · 2차 유사 장애 처리자) + 자동 작성 메시지.
    inc 는 repo.get_incident(detail=True) 결과. sender 예: '센터관리자 강민정'."""
    primary = primary_recipients(db, inc["error_type"], severity)
    secondary, names = secondary_recipients(db, inc.get("similar_cases") or [], {e["emp_id"] for e in primary})
    reports = inc.get("reports") or []
    consult = reports[-1] if reports else {"consult_id": "-", "customer_name": "", "agent_name": ""}
    view = {**inc, "severity": severity}
    title, body = compose(db, view, {"analysis": inc.get("analysis"), "similar_cases": inc.get("similar_cases")},
                          consult, primary, secondary, names)
    if severity != inc["severity"]:
        title = f"[등급 변경 {inc['severity']}→{severity}]" + title
        body = body.replace("▣ 증상", f"▣ 등급 변경\n 이전 {inc['severity']} → 현재 {severity} ({sender} 판단)\n\n▣ 증상", 1)
    title = f"[수동 전송 · {sender}]" + title
    body = body.replace("※ VOC 자율형 장애 알림 AI Agent 자동 발송", f"※ {sender} 확인 후 수동 전송 (VOC 장애 알림 AI Agent 작성)")
    return {"primary": primary, "secondary": secondary, "title": title[:200], "body": body}


# ---------------------------------------------------------------------
# 장애알림 정보 등록
# ---------------------------------------------------------------------
def register(db, ctx: dict) -> tuple[dict, str]:
    """장애 알림 정보 등록/갱신 (장애알림정보등록). (incident, action 설명) 반환."""
    det, dd, sev, consult = ctx["detection"], ctx["dedup"], ctx["severity"], ctx["consult"]
    severity = sev["severity"]
    cr = criteria.load(db)
    basis = {"criteria_version": sev.get("criteria_version"), "applied_rules": sev.get("applied_rules") or []}
    prev = repo.get_incident(db, dd["incident_id"], detail=False) if dd["merged"] else None
    if prev:
        severity = cr.max(severity, prev["severity"])
    if sev["false_positive"]:
        status = "오탐"
    elif sev["notify"]:
        status = "접수"
    else:
        status = cr.unnotified_status(severity)

    if prev:
        fields = {"severity": severity, "analysis": sev["analysis"], **basis}
        if sev.get("similar_cases"):
            fields["similar_cases"] = sev["similar_cases"]
        # 알림 대상이 되면 접수, 미대상 건이 관찰 등급으로 올라가면 관찰로 다시 엶 (진행 중·처리된 건은 그대로)
        if (status == "접수" and prev["status"] in ("관찰", "미대상")) or (status == "관찰" and prev["status"] == "미대상"):
            fields["status"] = status
        inc = repo.update_incident(db, prev["incident_id"], fields)
        action = f"장애 {repo.incident_no(inc['incident_id'])} 갱신(누적 {inc['report_count']}건, 상태 {inc['status']})"
    else:
        inc = repo.create_incident(db, {
            "title": det["title"], "error_type": det["error_type"], "channel": det["channel"],
            "severity": severity, "status": status, "report_count": 1, "mass_signal": False,
            "symptoms": det["symptoms"], "env_info": det.get("env") or {},
            "analysis": sev["analysis"], "similar_cases": sev["similar_cases"], **basis,
        })
        repo.add_incident_report(db, inc["incident_id"], consult["consult_id"], 1.0)
        action = f"장애 {repo.incident_no(inc['incident_id'])} 신규 등록(상태 {status})"
    ctx["incident_id"] = inc["incident_id"]
    return inc, action


def run_record(db, ctx: dict) -> tuple[str, str, dict]:
    """[분기: 알림 미대상] 메신저 없이 장애알림 정보만 등록."""
    sev = ctx["severity"]
    inc, action = register(db, ctx)
    out = {"incident_id": inc["incident_id"], "incident_status": inc["status"], "severity": inc["severity"],
           "sent": False, "recipients": []}
    ctx["notify"] = out
    if sev["false_positive"]:
        reason = "과거 오탐 사례와 일치"
    elif inc["status"] == "관찰":
        reason = "관찰 등급 - 센터관리자 확인 후 IT담당자 수동 알림"
    elif inc["status"] == "미대상":
        reason = "관찰 대상이 아닌 등급 - 미대상 종결, 추가 제보 시 재판정"
    else:
        reason = "알림 미대상 등급/건수"
    return "DONE", f"{action} - 메신저 미발송 ({reason})", out


def run(db, ctx: dict) -> tuple[str, str, dict]:
    """[분기: 알림 대상] 수신자 식별(1차 인사정보 · 2차 유사장애 처리자) + 템플릿 작성 + 메신저 전송."""
    sev, consult = ctx["severity"], ctx["consult"]
    inc, action = register(db, ctx)
    out = {"incident_id": inc["incident_id"], "incident_status": inc["status"], "severity": inc["severity"],
           "sent": False, "recipients": [], "link_url": detail_url(inc["incident_id"])}
    ctx["notify"] = out

    # 이미 같은(또는 더 높은) 등급으로 알림이 나간 장애면 중복 발송하지 않음
    notified = inc.get("notified_severity")
    if notified and criteria.load(db).max(notified, inc["severity"]) == notified:
        out["skipped_reason"] = f"이미 {notified}로 알림 발송됨"
        return "DONE", f"{action} - 이미 {notified} 알림 발송된 장애로 중복 발송 생략", out

    primary = primary_recipients(db, inc["error_type"], inc["severity"])
    secondary, resolver_names = secondary_recipients(db, sev.get("similar_cases") or [],
                                                     {e["emp_id"] for e in primary})
    title, body = compose(db, inc, sev, consult, primary, secondary, resolver_names)
    dd = ctx.get("dedup") or {}
    before = notified or (dd.get("previous_severity") if dd.get("merged") else None)
    if before and before != inc["severity"]:
        title = f"[등급 상향 {before}→{inc['severity']}]" + title
        changed = "; ".join(r for r in sev.get("reasons") or [] if r.startswith("[")) or "-"
        body = body.replace("▣ 증상", f"▣ 등급 변경\n 이전 {before} → 현재 {inc['severity']} (근거: {changed})\n\n▣ 증상", 1)
    link = detail_url(inc["incident_id"])
    targets = [{"receiver": e["messenger_id"], "receiver_name": e["emp_name"], "emp_id": e["emp_id"],
                "recipient_type": "1차", "link_url": link} for e in primary]
    targets += [{"receiver": e["messenger_id"], "receiver_name": e["emp_name"], "emp_id": e["emp_id"],
                 "recipient_type": "2차", "link_url": link} for e in secondary]
    logs = messenger.send_message(db, targets, title, body, incident_id=inc["incident_id"])
    fields = {"notified_severity": inc["severity"]}
    if not inc.get("owner_emp_id") and primary:
        fields["owner_emp_id"] = primary[0]["emp_id"]
    repo.update_incident(db, inc["incident_id"], fields)

    out.update(sent=True, title=title, transport=logs[0]["transport"] if logs else None,
               primary=[f"{e['emp_name']}({e['duty_role']}, {e['dept']})" for e in primary],
               secondary=[f"{e['emp_name']}({repo.incident_no(e['for_incident'])} 처리)" for e in secondary])
    out["recipients"] = out["primary"] + out["secondary"]
    msg = f"{action} → 1차 {', '.join(out['primary']) or '없음'}"
    if secondary:
        msg += f" / 2차 {', '.join(out['secondary'])}"
    return "DONE", msg + " 에게 메신저 발송 (상세 링크 포함)", out
