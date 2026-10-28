"""③ 장애 심각도 판별 에이전트

판별 기준은 DB의 장애등급 판별기준(severity_grade / severity_base_rule / severity_adjust_rule)을 사용합니다.
(테이블이 없거나 비어 있으면 rules.py 코드 기본값)

1차: 판별기준(판별기준 조회 API /api/severity-criteria 와 같은 서비스)으로 메신저 알림 대상 여부 식별
     - 기본 등급(오류유형·접촉채널) + 조정 규칙(adjust_rule 의 apply_order 순)
     - 등급별 알림 조건(알림 최소 제보 건수)으로 알림 대상 판정
     - RAG: 과거 해결·오탐 사례를 검색(RAG_SEARCH, 기본 문자열 유사도)해 LLM 프롬프트에 함께 제공
     - LLM 사용 시 등급 정의 + 과거 유사 사례를 프롬프트로 주고 등급·초기 분석을 판단
2차: 1차에서 알림 대상일 때만, 1차에서 검색한 사례 중 '오탐'으로 판별된 건과 대조
     → 오탐 규칙(FALSE_POSITIVE)에 해당하면 알림 제외
결과: 알림 대상 → 메신저 전송 에이전트 / 미대상 → 장애알림 정보만 등록
적용한 기준 버전과 규칙코드를 결과에 남겨 장애에 기록합니다.
"""
import logging

from app.agents import llm, rules
from app.database import settings
from app.services import criteria, rag, repo

log = logging.getLogger("voc.severity")
NAME = "심각도 판별 에이전트"
BIGRAM_FP_THRESHOLD = 0.25   # 문자열 유사도(대체 방식)일 때 오탐 일치 기준

SYSTEM_TMPL = """당신은 금융 IT 장애 심각도 판별 에이전트입니다.
아래 장애등급 판별기준과 규칙 기반 1차 판별 결과를 보고 심각도 등급과 메신저 알림 대상 여부를 결정하세요.
등급은 고객이 말한 사실(재시도 후에도 계속 막히는지, 지급·신청 기한, 구체적 피해, 대체수단 유무, 같은 증상의 독립 고객 수)로 판단하고 오류 원인은 단정하지 마세요.
상담사의 마무리·전달 멘트(예: "긴급 건으로 전달하겠습니다")는 응대 표현일 뿐이므로 등급 판단 근거로 쓰지 마세요.
[과거 유사 사례]가 주어지면 추정 원인과 초기 점검 포인트(analysis)를 쓸 때 참고하고, 관련 있는 해결 사례는 장애번호와 처리결과를 인용하세요.
과거 사례는 참고 자료입니다. 등급은 판별기준과 이번 고객 발화로 판단하고 과거 사례의 등급을 그대로 따르지 마세요.
오탐 사례와 비슷해도 이번 고객 발화에서 고객 귀책(비밀번호 오입력 등)이 확인되지 않으면 오탐으로 보지 마세요. 관련 없는 사례는 무시하세요.
[장애등급 판별기준]
{definitions}
출력 JSON: {{"severity": "{codes}", "notify": bool,
            "analysis": "IT담당자를 위한 추정 원인과 초기 점검 포인트 (3~5문장, 한국어)", "reason": "판단 근거",
            "ref_cases": [참고한 과거 사례 장애번호(예: "ERR-0003"), 없으면 빈 배열]}}"""


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
    keep = ("incident_id", "title", "status", "severity", "error_type", "symptoms", "resolution", "similarity")
    return [{k: c.get(k) for k in keep} for c in cases], method, threshold


def _cases_prompt(similar: list[dict]) -> str:
    """LLM 프롬프트에 넣을 과거 유사 사례 (RAG 검색 결과)."""
    lines = []
    for c in similar:
        lines.append(f"- {repo.incident_no(c['incident_id'])} [{c['status']}] {c['title']} (유형 {c.get('error_type')}, 등급 {c.get('severity')},"
                     f" 유사도 {c['similarity']})")
        if c.get("symptoms"):
            lines.append(f"  증상: {str(c['symptoms'])[:150]}")
        if c.get("resolution"):
            lines.append(f"  처리결과: {str(c['resolution'])[:200]}")
    return "\n".join(lines)


def _rule_analysis(det: dict, similar: list[dict]) -> str:
    lines = []
    solved = [c for c in similar if c["status"] == "해결"]
    if solved:
        c = solved[0]
        lines.append(f"유사 사례 {repo.incident_no(c['incident_id'])} '{c['title']}'(유사도 {c['similarity']}) - {c['resolution']}")
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
            words = rules.match_keyword_groups(text, list(r.get("keywords") or []))
            hit = f"키워드 {words}" if words else None
        elif r["rule_type"] == "REPORT_COUNT":
            hit = f"누적 제보 {count}건 ≥ {r['threshold']}" if r.get("threshold") and count >= r["threshold"] else None
        elif r["rule_type"] == "MASS_SIGNAL":
            hit = (f"대규모 장애 신호(독립 고객 {dd.get('customer_count', count)}명, 누적 {count}건)"
                   if dd.get("mass_signal") else None)
        if not hit:
            continue
        before = sev
        if r["action_type"] == "RAISE":
            sev = cr.raise_by(sev, r.get("raise_steps") or 1)
        elif r["action_type"] == "SET_GRADE" and r.get("target_grade"):
            sev = r["target_grade"]
        elif r["action_type"] == "RAISE_TO" and r.get("target_grade"):
            sev = cr.max(sev, r["target_grade"])          # 최소 이 등급 (더 심각하면 유지)
        elif r["action_type"] == "LOWER_TO" and r.get("target_grade"):
            if dd.get("mass_signal"):
                continue                                   # 대규모 신호는 내리지 않음
            if cr.max(sev, r["target_grade"]) == sev:
                sev = r["target_grade"]                    # 최대 이 등급 (덜 심각하면 유지)
        if sev == before and r["action_type"] in ("RAISE_TO", "LOWER_TO"):
            continue                                       # 등급 변화 없음 → 적용 규칙으로 남기지 않음
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

    # RAG 검색: 과거 해결·오탐 사례. LLM 프롬프트 · 2차 오탐 대조 · 초기 분석 · 메신저 과거 해결 사례에 함께 사용
    try:
        similar, rag_method, fp_threshold = _similar_cases(db, det, text)
    except Exception:
        log.exception("유사 사례 검색 실패")
        similar, rag_method, fp_threshold = [], "-", 1.0
    use_cases = settings.rag_in_llm and bool(similar)
    refs: list[int] = []
    reasons.append(f"RAG 유사 사례 검색 ({rag_method}): {len(similar)}건"
                   + (" → LLM 프롬프트에 제공" if use_cases and llm.enabled() else ""))

    if llm.enabled():
        cases_txt = f"\n\n[과거 유사 사례]\n{_cases_prompt(similar)}" if use_cases else ""
        system = SYSTEM_TMPL.format(definitions=cr.llm_definitions(), codes="|".join(cr.codes()))
        ans = llm.ask_json(system, f"""[고객 발화]
{text}

[감지 결과]
{det}

[중복 통합 결과]
누적 제보 {count}건 (독립 고객 {dd.get('customer_count', 1)}명), 대규모 신호={dd.get('mass_signal')}

[규칙 기반 1차 판별]
심각도={sev}, 알림 대상={notify}
근거: {reasons}{cases_txt}""")
        if ans and ans.get("severity") in cr.codes():
            ctx["llm_used"] = True
            source = "판별기준+LLM"
            by_no = {repo.incident_no(c["incident_id"]): c["incident_id"] for c in similar}
            refs = [by_no[str(r).strip()] for r in (ans.get("ref_cases") or []) if str(r).strip() in by_no]
            if refs:
                reasons.append("LLM 참고 사례: " + ", ".join(repo.incident_no(r) for r in refs))
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
    stage2 = {"checked": False}
    if notify:
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
            reasons.append(f"2차 대조: [{fp_rule['rule_code']}] 과거 오탐 사례 {repo.incident_no(fp_case['incident_id'])}"
                           f"(유사도 {fp_case['similarity']}) + 고객 귀책 신호 {fp_words} → 오탐, 알림 제외")
        else:
            reasons.append(f"2차 대조: 과거 오탐 사례와 일치 없음 ({rag_method}, 비교 {len(similar)}건) → 최종 알림 대상")
    else:
        reasons.append("2차 대조 생략 (1차에서 알림 미대상)")
    if rag_method != "-":
        source += f"+RAG({rag_method})"

    analysis = analysis or _rule_analysis(det, similar)
    out = {"severity": sev, "severity_label": cr.label(sev), "notify": notify,
           "false_positive": false_positive, "stage1": stage1, "stage2": stage2,
           "reasons": reasons, "similar_cases": similar,
           "analysis": analysis, "source": source, "rag_method": rag_method,
           "criteria_version": cr.version, "criteria_source": cr.source, "applied_rules": applied,
           "rag": {"method": rag_method, "count": len(similar), "in_llm": use_cases and source != "판별기준",
                   "ref_cases": refs}}
    ctx["severity"] = out

    s1 = f"1차 {stage1['severity']} {'알림 대상' if stage1['notify'] else '미대상'}"
    if not stage2["checked"]:
        decision = (f"{s1} → 알림 미대상, " + ("관찰 등록 (센터관리자 확인)" if cr.observe(sev)
                                              else "미대상 종결 (추가 제보 시 재판정)"))
    elif false_positive:
        decision = f"{s1} → 2차 과거 오탐 사례 {repo.incident_no(stage2['matched'])} 일치 → 알림 제외"
    else:
        decision = f"{s1} → 2차 오탐 대조 통과 → 메신저 알림 대상"
    rules_txt = ", ".join(a for a in applied if not a.startswith("BASE"))
    rag_txt = f" · RAG 유사 사례 {len(similar)}건" + (f"(LLM 참고 {', '.join(repo.incident_no(r) for r in refs)})" if refs else "")
    return "DONE", (f"최종 {sev}({cr.label(sev)}) / {decision} [{source}]"
                    + (f" · 적용 규칙 {rules_txt}" if rules_txt else "") + rag_txt), out
