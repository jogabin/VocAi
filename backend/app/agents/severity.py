"""③ 장애 심각도 판별 에이전트

판별 기준은 DB의 장애등급 판별기준(severity_grade / severity_base_rule / severity_adjust_rule)을 사용합니다.
(테이블이 없거나 비어 있으면 rules.py 코드 기본값)

1차: 판별기준(판별기준 조회 API /api/severity-criteria 와 같은 서비스)으로 메신저 알림 대상 여부 식별
     - 기본 등급(오류유형·접촉채널) + 조정 규칙(적용순서: 키워드 상향, 복수 제보, 대규모 신호)
     - 등급별 알림 조건(알림 최소 제보 건수)으로 알림 대상 판정
     - LLM 사용 시 같은 등급 정의를 프롬프트로 주고 등급·알림 여부를 함께 판단
2차: 1차에서 알림 대상일 때만, 과거 장애 사례(RAG) 중 '오탐'으로 판별된 건과 대조
     → 오탐 규칙(FALSE_POSITIVE)에 해당하면 알림 제외
결과: 알림 대상 → 메신저 전송 에이전트 / 미대상 → 장애알림 정보만 등록
적용한 기준 버전과 규칙코드를 결과에 남겨 장애에 기록합니다.
"""
from app.agents import llm, rules
from app.database import settings
from app.services import criteria, rag, repo

NAME = "심각도 판별 에이전트"
BIGRAM_FP_THRESHOLD = 0.25   # 문자열 유사도(대체 방식)일 때 오탐 일치 기준

SYSTEM_TMPL = """당신은 금융 IT 장애 심각도 판별 에이전트입니다.
아래 장애등급 판별기준과 규칙 기반 1차 판별 결과를 보고 심각도 등급과 메신저 알림 대상 여부를 결정하세요.
[장애등급 판별기준]
{definitions}
출력 JSON: {{"severity": "{codes}", "notify": bool,
            "analysis": "IT담당자를 위한 추정 원인과 초기 점검 포인트 (3~5문장, 한국어)", "reason": "판단 근거"}}"""


def _bigram_cases(db, det: dict, query: str) -> list[dict]:
    """임베딩을 쓸 수 없을 때의 대체 검색 (문자 bigram 유사도)."""
    cases = []
    for k in repo.search_knowledge(db):
        sim = rules.similarity(query, f"{k['title']} {k['symptoms']}")
        if k["error_type"] == det["error_type"]:
            sim = round(min(1.0, sim + 0.1), 3)
        cases.append({**k, "similarity": sim})
    cases.sort(key=lambda c: c["similarity"], reverse=True)
    return [c for c in cases[:3] if c["similarity"] >= 0.1]


def _similar_cases(db, det: dict, customer_text: str) -> tuple[list[dict], str, float]:
    """(유사사례, 검색방식, 오탐판정 기준값). pgvector 임베딩 검색 우선, 실패 시 문자열 유사도."""
    query = f"{det['title']}\n증상: {det['symptoms']}\n{customer_text[:600]}"
    found = rag.search_similar(db, query, k=3)
    if found is not None:
        cases, method = found
        cases = [c for c in cases if c["similarity"] >= settings.rag_min_similarity]
        threshold = settings.rag_fp_similarity
    else:
        # 문자열 유사도는 라벨 단어("증상:")가 섞이면 점수가 떨어지므로 원문만 비교
        plain = f"{det['title']} {det['symptoms']} {customer_text}"
        cases, method, threshold = _bigram_cases(db, det, plain), "문자열 유사도", BIGRAM_FP_THRESHOLD
    keep = ("incident_id", "title", "status", "severity", "error_type", "resolution", "similarity")
    return [{k: c.get(k) for k in keep} for c in cases], method, threshold


def _rule_analysis(det: dict, similar: list[dict]) -> str:
    lines = []
    solved = [c for c in similar if c["status"] == "해결"]
    if solved:
        c = solved[0]
        lines.append(f"유사 사례 #{c['incident_id']} '{c['title']}'(유사도 {c['similarity']}) - {c['resolution']}")
    guide = rules.CHECK_GUIDE.get(det["error_type"], rules.CHECK_GUIDE["기타"])
    lines.append("우선 점검: " + ", ".join(guide))
    env = det.get("env") or {}
    if env:
        lines.append("재현 환경: " + ", ".join(f"{k}={v}" for k, v in env.items()))
    return "\n".join(lines)


def _apply_adjust_rules(cr, det: dict, dd: dict, text: str, sev: str, count: int,
                        reasons: list, applied: list) -> str:
    for r in cr.adjust_rules:
        if r["rule_type"] == "FALSE_POSITIVE":
            continue                                   # 오탐 규칙은 RAG 대조 후 적용
        if r.get("target_error_type") and r["target_error_type"] != det["error_type"]:
            continue
        if r.get("condition_grade") and r["condition_grade"] != sev:
            continue
        hit = None
        if r["rule_type"] == "KEYWORD":
            words = rules.contains_any(text, list(r.get("keywords") or []))
            hit = f"키워드 {words}" if words else None
        elif r["rule_type"] == "REPORT_COUNT":
            hit = f"누적 제보 {count}건 ≥ {r['threshold']}" if r.get("threshold") and count >= r["threshold"] else None
        elif r["rule_type"] == "MASS_SIGNAL":
            hit = f"대규모 장애 신호(누적 {count}건)" if dd.get("mass_signal") else None
        if not hit:
            continue
        before = sev
        if r["action_type"] == "RAISE":
            sev = cr.raise_by(sev, r.get("raise_steps") or 1)
        elif r["action_type"] == "SET_GRADE" and r.get("target_grade"):
            sev = r["target_grade"]
        applied.append(r["rule_code"])
        reasons.append(f"[{r['rule_code']}] {r['rule_name']}: {hit} → {before}→{sev}")
    return sev


def run(db, ctx: dict) -> tuple[str, str, dict]:
    det, dd = ctx["detection"], ctx["dedup"]
    text = ctx["customer_text"]
    count = dd["report_count"]
    cr = criteria.load(db)                       # 장애등급 판별기준 (판별기준 관리 화면에서 관리)
    reasons = [f"판별기준 {cr.version} ({cr.source})"]
    applied: list[str] = []

    # ================= 1차: 판별기준으로 알림 대상 여부 =================
    base, base_rule = cr.base_grade(det["error_type"], det.get("channel"))
    applied.append(f"BASE:{det['error_type']}" + (f"/{base_rule['channel']}" if base_rule and base_rule.get("channel") else ""))
    reasons.append(f"[BASE] 유형 '{det['error_type']}' 기본 등급 {base}")
    sev = base
    cand = det.get("severity_candidate")
    if cand in cr.codes() and cr.max(sev, cand) != sev:
        reasons.append(f"감지 단계 후보 등급 {cand} 반영")
        sev = cand
    sev = _apply_adjust_rules(cr, det, dd, text, sev, count, reasons, applied)
    if dd.get("merged"):
        merged = cr.max(sev, dd.get("previous_severity"))
        if merged != sev:
            reasons.append(f"통합된 기존 장애 등급 {dd.get('previous_severity')} 유지")
        sev = merged
    notify = cr.should_notify(sev, count)
    analysis = None
    source = "판별기준"

    if llm.enabled():
        system = SYSTEM_TMPL.format(definitions=cr.llm_definitions(), codes="|".join(cr.codes()))
        ans = llm.ask_json(system, f"""[감지 결과]
{det}

[중복 통합 결과]
누적 제보 {count}건, 대규모 신호={dd.get('mass_signal')}

[규칙 기반 1차 판별]
심각도={sev}, 알림 대상={notify}
근거: {reasons}""")
        if ans and ans.get("severity") in cr.codes():
            ctx["llm_used"] = True
            source = "판별기준+LLM"
            mass_rule = next((r for r in cr.adjust_rules if r["rule_type"] == "MASS_SIGNAL"), None)
            if dd.get("mass_signal") and mass_rule and mass_rule.get("target_grade"):
                sev = mass_rule["target_grade"]          # 대규모 장애 신호는 LLM 판단보다 우선
            else:
                sev = ans["severity"]
            notify = cr.should_notify(sev, count)    # 알림 여부는 등급별 알림 조건(판별기준)으로만 결정
            analysis = ans.get("analysis")
            applied.append("LLM")
            reasons.append(f"LLM: {ans.get('reason', '')}")
    stage1 = {"severity": sev, "notify": notify}
    reasons.append(f"1차 판별: {sev}({cr.label(sev)}) → " + ("알림 대상" if notify else "알림 미대상"))

    # ================= 2차: 과거 오탐 사례 대조 (알림 대상일 때만) =================
    false_positive = False
    similar, rag_method = [], "-"
    stage2 = {"checked": False}
    if notify:
        similar, rag_method, fp_threshold = _similar_cases(db, det, text)
        fp_rule = cr.false_positive_rule()
        fp_cases = [c for c in similar if c["status"] == "오탐"]
        fp_case = next((c for c in fp_cases if c["similarity"] >= fp_threshold), None)
        fp_words = rules.contains_any(text, list((fp_rule or {}).get("keywords") or []))
        false_positive = bool(fp_rule and fp_case and fp_words and not dd.get("mass_signal"))
        stage2 = {"checked": True, "method": rag_method, "fp_cases": len(fp_cases),
                  "matched": fp_case["incident_id"] if false_positive else None}
        if false_positive:
            sev = fp_rule.get("target_grade") or cr.lowest()
            notify = False
            applied.append(fp_rule["rule_code"])
            reasons.append(f"2차 대조: [{fp_rule['rule_code']}] 과거 오탐 사례 #{fp_case['incident_id']}"
                           f"(유사도 {fp_case['similarity']}) + 고객 귀책 신호 {fp_words} → 오탐, 알림 제외")
        else:
            reasons.append(f"2차 대조: 과거 오탐 사례와 일치 없음 ({rag_method}, 비교 {len(similar)}건) → 최종 알림 대상")
        source += f"+RAG({rag_method})"
    else:
        reasons.append("2차 대조 생략 (1차에서 알림 미대상)")

    analysis = analysis or _rule_analysis(det, similar)
    out = {"severity": sev, "severity_label": cr.label(sev), "notify": notify,
           "false_positive": false_positive, "stage1": stage1, "stage2": stage2,
           "reasons": reasons, "similar_cases": similar,
           "analysis": analysis, "source": source, "rag_method": rag_method,
           "criteria_version": cr.version, "criteria_source": cr.source, "applied_rules": applied}
    ctx["severity"] = out

    s1 = f"1차 {stage1['severity']} {'알림 대상' if stage1['notify'] else '미대상'}"
    if not stage2["checked"]:
        decision = f"{s1} → 알림 미대상, 장애알림 정보만 등록 (추가 제보 시 재판정)"
    elif false_positive:
        decision = f"{s1} → 2차 과거 오탐 사례 #{stage2['matched']} 일치 → 알림 제외"
    else:
        decision = f"{s1} → 2차 오탐 대조 통과 → 메신저 알림 대상"
    rules_txt = ", ".join(a for a in applied if not a.startswith("BASE"))
    return "DONE", (f"최종 {sev}({cr.label(sev)}) / {decision} [{source}]"
                    + (f" · 적용 규칙 {rules_txt}" if rules_txt else "")), out
