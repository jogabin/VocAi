"""시연용 과거 상담 데이터: 2026-10-15 ~ 2026-10-28, 하루 20건

  - 10/15 ~ 10/27 : 상담완료(상담이력 등록) → 에이전트 실행 이력 → 등급 정의에 따라 장애알림 정보 등록
      P1  : 같은 장애를 고객 3명이 연달아 제보 → 대규모 장애 신호로 자동 알림 → IT담당자 진행중 → 처리완료
      P2  : 관찰 등록 → 센터관리자 확인 후 IT담당자 지정 수동 알림(→ 대기중) → IT담당자 처리완료, 또는 알림 없이 미대상 종결
      P3·P4 : 미대상 자동 종결 (관찰 대상이 아닌 등급)
      고객 실수 : 관찰 등록 → 센터관리자가 오탐으로 종결 (2차 오탐 대조 사례)
      메신저는 내용만 기록 (실제 발송 없음, MOCK)
  - 10/28(오늘)   : 상담 진행 중인 통화만 (상담이력 등록 시연용)
대본은 app/history_scenarios.py. 날짜별 난수 시드를 고정해 다시 만들어도 같은 데이터가 나옵니다.
에이전트를 실제로 돌리지 않고 같은 형식의 결과를 기록합니다 (과거 시각으로 남기기 위해).

DB 초기화(init_schema) 때 SQL 파일 다음에 실행되며, 이미 들어 있으면 건너뜁니다.
"""
import json
import logging
import random
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import text

from app import history_scenarios as S
from app.agents import dedup, detection, improve, notify, rules, severity
from app.services import criteria, repo

log = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
START, TODAY = date(2026, 10, 15), date(2026, 10, 28)
PER_DAY = 20
P1_DAYS = {date(2026, 10, 16): 0, date(2026, 10, 19): 1, date(2026, 10, 22): 2, date(2026, 10, 25): 3,
           date(2026, 10, 28): 4}
AGENTS = ["이수진", "박지훈", "정하나"]
REGISTERED_BY = {"이수진": "user01"}          # 로그인 계정이 있는 상담사. 그 밖에는 admin 이 등록
BASE = {"이체": "P2", "인증": "P2", "로그인": "P2", "조회": "P3", "UI오류": "P3", "기타": "P4"}
MANAGERS = ["강민정", "조현우"]                # 관찰 장애를 확인하는 센터관리자
MANAGER_LOGIN = {"강민정": "admin"}
CLOSE_REASONS = [
    "단일 고객 건으로 같은 시간대 동일 증상 추가 제보 없음. 고객에게 다른 채널(영업점·인터넷뱅킹) 이용 안내 후 종결, 추가 제보 시 재검토.",
    "고객 콜백 결과 재시도 후 정상 이용 확인. 알림 불필요로 종결.",
    "일시 현상으로 판단(이후 동일 문의 없음). 고객 안내 완료, 추가 제보 시 재판정.",
]
RAG = "문자열 유사도"

SURNAMES = "김이박최정강조윤장임한오서신권황안송전홍"
GIVEN = [("민준", "남"), ("서연", "여"), ("지훈", "남"), ("하은", "여"), ("도현", "남"), ("수아", "여"), ("예준", "남"),
         ("지민", "여"), ("시우", "남"), ("채원", "여"), ("주원", "남"), ("유나", "여"), ("건우", "남"), ("다은", "여"),
         ("현우", "남"), ("소율", "여"), ("지호", "남"), ("서윤", "여"), ("준서", "남"), ("하린", "여"), ("우진", "남"),
         ("지아", "여"), ("선호", "남"), ("예린", "여"), ("태윤", "남"), ("나연", "여"), ("동현", "남"), ("세아", "여")]


def _kst(d: date, hh: int, mm: int, ss: int = 0) -> datetime:
    return datetime.combine(d, time(hh, mm, ss), tzinfo=KST)


def _offsets(lines: list[tuple[str, str]]) -> list[int]:
    """상담데이터 등록 화면과 같은 규칙 (약 6자/초, 최소 4초)."""
    out, cur = [], 0
    for i, (_, t) in enumerate(lines):
        if i:
            cur += max(4, round(len(lines[i - 1][1]) / 6))
        out.append(cur)
    return out


def _fill(s: str, slots: dict) -> str:
    return s.format(**slots)


class _Loader:
    def __init__(self, db):
        self.db = db
        self.cr = criteria.load(db, use_cache=False)
        emps = repo._rows(db.execute(text("SELECT * FROM employee WHERE use_yn ORDER BY emp_id")))
        self.emp_by_name = {e["emp_name"]: e for e in emps}
        self.it_staff = {t: repo.find_it_staff(db, t) for t in BASE}
        # RAG 지식베이스: 해결·오탐 장애 (seed 5건 + 이 데이터에서 처리완료되는 장애)
        self.knowledge = [{**k, "resolved_at": k.get("first_reported_at") + timedelta(hours=3),
                           "resolver": None}
                          for k in repo.search_knowledge(db)]
        for k in self.knowledge:
            row = db.execute(text("SELECT coalesce(resolved_by_emp_id, owner_emp_id) FROM incident_alert"
                                  " WHERE incident_id = :i"), {"i": k["incident_id"]}).scalar()
            k["resolver"] = row
        self.customers = self._customers()
        self.counts = {"calls": 0, "consults": 0, "incidents": 0, "messages": 0, "improvements": 0}

    # ------------------------------------------------------------------ 고객
    def _customers(self) -> list[dict]:
        rng = random.Random(20261015)
        out = []
        for i in range(220):
            given, gender = rng.choice(GIVEN)
            c = {"customer_id": f"CUST-{26001 + i}", "customer_name": rng.choice(SURNAMES) + given,
                 "phone": f"010-{4600 + i}-{rng.randint(1000, 9999)}", "gender": gender,
                 "age": rng.randint(21, 72)}
            out.append(c)
        self.db.execute(text("""
            INSERT INTO customer (customer_id, customer_name, phone, gender, age, created_at, updated_at)
            VALUES (:customer_id, :customer_name, :phone, :gender, :age, '2026-10-01 09:00+09', '2026-10-01 09:00+09')
            ON CONFLICT (customer_id) DO NOTHING"""), out)
        return out

    # ------------------------------------------------------------------ 하루치 상담 계획
    def _plan(self, d: date) -> list[dict]:
        rng = random.Random(d.toordinal())
        calls = []
        if d in P1_DAYS:
            sc = S.P1[P1_DAYS[d]]
            base = _kst(d, rng.randint(9, 14), rng.choice([5, 15, 25, 35]))
            for i, gap in enumerate([0, rng.randint(11, 18), rng.randint(26, 38)]):
                calls.append({"kind": "P1", "sc": sc, "at": base + timedelta(minutes=gap), "nth": i})
        picks = (("P2", rng.sample(S.P2, 3)), ("P3", rng.sample(S.P3, 3)), ("P4", rng.sample(S.P4, 1)),
                 ("FP", rng.sample(S.FP, 1)), ("IMP", rng.sample(S.IMP, 1) if d.toordinal() % 2 == 0 else []))
        for kind, scs in picks:
            calls += [{"kind": kind, "sc": sc} for sc in scs]
        gens = rng.sample(S.GEN, len(S.GEN))
        while len(calls) < PER_DAY:
            calls.append({"kind": "GEN", "sc": gens[len(calls) % len(gens)]})
        # P1 이외 통화 시각: 09:00 ~ 17:40 사이, P1 시각과 겹치지 않게 5분 단위
        taken = {c["at"].replace(second=0) for c in calls if "at" in c}
        free = [_kst(d, 9, 0) + timedelta(minutes=5 * k) for k in range(105)]
        free = [t for t in free if all(abs((t - x).total_seconds()) >= 300 for x in taken)]
        for c, t in zip([c for c in calls if "at" not in c], sorted(rng.sample(free, sum("at" not in c for c in calls)))):
            c["at"] = t + timedelta(seconds=rng.randint(0, 240))
        calls.sort(key=lambda c: c["at"])
        people = rng.sample(self.customers, len(calls))
        for i, c in enumerate(calls):
            c["cust"] = people[i]
            c["agent"] = AGENTS[(d.toordinal() + i) % len(AGENTS)]
            dev, os_ = rng.choice(S.DEVICES)
            pc_os, browser = rng.choice(S.PCS)
            c["slots"] = {"agent": c["agent"], "device": dev, "ver": rng.choice(S.APP_VERSIONS),
                          "pc": f"{pc_os} {browser}", "amt": rng.choice(S.AMOUNTS), "code": f"E-{rng.choice([1203, 1207, 1311])}",
                          "n": rng.randint(12, 140)}
            c["env"] = ({"os": os_, "device": dev, "app_version": c["slots"]["ver"]} if c["sc"].get("channel") == "앱"
                        else {"os": pc_os, "device": "PC", "browser": browser} if c["sc"].get("channel") == "웹" else {})
            c["call_id"] = f"CALL-{d:%m%d}-{i + 1:02d}"
        if d in P1_DAYS:                            # P1 대본은 하루 1건이라 같은 증상 슬롯을 3명이 공유
            first = next(c for c in calls if c["kind"] == "P1")
            for c in calls:
                if c["kind"] == "P1":
                    c["slots"].update({k: first["slots"][k] for k in ("ver", "code", "n")})
        return calls

    # ------------------------------------------------------------------ 통화 + 원문
    def _insert_call(self, c: dict, done: bool) -> None:
        sc = c["sc"]
        lines = [(sp, _fill(t, c["slots"])) for sp, t in sc["lines"] if sp != "C+" or c.get("nth", 0) > 0]
        lines = [("CUSTOMER" if sp.startswith("C") else "AGENT", t) for sp, t in lines]
        offs = _offsets(lines)
        c["lines"], c["duration"] = lines, offs[-1] + max(5, round(len(lines[-1][1]) / 6))
        c["customer_text"] = "\n".join(t for sp, t in lines if sp == "CUSTOMER")
        agent = self.emp_by_name.get(c["agent"])
        end = c["at"] + timedelta(seconds=c["duration"])
        c["consult_at"] = end + timedelta(seconds=90 + sum(map(ord, c["call_id"])) % 120)
        self.db.execute(text("""
            INSERT INTO stt_call (call_id, customer_id, customer_name, agent_name, agent_emp_id, inbound_channel,
                                  started_at, duration_sec, consult_status, completed_at)
            VALUES (:id, :cid, :cname, :aname, :aid, '콜센터', :st, :dur, :cs, :done_at)"""),
            {"id": c["call_id"], "cid": c["cust"]["customer_id"], "cname": c["cust"]["customer_name"],
             "aname": f"상담사 {c['agent']}", "aid": agent["emp_id"] if agent else None, "st": c["at"],
             "dur": c["duration"], "cs": "상담완료" if done else "진행", "done_at": c["consult_at"] if done else None})
        self.db.execute(text("""
            INSERT INTO stt_utterance (call_id, seq, speaker, offset_sec, text, created_at)
            VALUES (:id, :seq, :sp, :off, :tx, :at)"""),
            [{"id": c["call_id"], "seq": i + 1, "sp": sp, "off": o, "tx": t, "at": c["at"] + timedelta(seconds=o)}
             for i, ((sp, t), o) in enumerate(zip(lines, offs))])
        self.counts["calls"] += 1

    # ------------------------------------------------------------------ 상담이력
    def _insert_consult(self, c: dict) -> None:
        sc, kind = c["sc"], c["kind"]
        ctype = "일반문의" if kind in ("GEN", "IMP") else "전산오류문의"
        channel = sc.get("channel") or ("앱" if kind == "GEN" else None)
        row = repo._row(self.db.execute(text("""
            INSERT INTO consult_history (call_id, customer_id, customer_name, agent_name, consult_type, channel,
                                         summary, result_status, registered_by, created_at)
            VALUES (:call, :cid, :cname, :aname, :ct, :ch, :sm, :rs, :by, :at) RETURNING *"""),
            {"call": c["call_id"], "cid": c["cust"]["customer_id"], "cname": c["cust"]["customer_name"],
             "aname": f"상담사 {c['agent']}", "ct": ctype, "ch": channel, "sm": _fill(sc["summary"], c["slots"]),
             "rs": "이관" if kind in ("P1", "P2") else "완료", "by": REGISTERED_BY.get(c["agent"], "admin"),
             "at": c["consult_at"]}))
        c["consult"] = row
        self.counts["consults"] += 1

    # ------------------------------------------------------------------ 에이전트 실행 이력
    def _run(self, c: dict, steps: list[tuple[str, str, str, dict]], status: str, incident_id=None) -> None:
        t0 = c["consult_at"] + timedelta(seconds=1)
        run_id = self.db.execute(text("""
            INSERT INTO agent_run (consult_id, status, outcome, incident_id, llm_used, started_at, finished_at)
            VALUES (:cid, :st, :oc, :iid, TRUE, :t0, :t1) RETURNING run_id"""),
            {"cid": c["consult"]["consult_id"], "st": status, "oc": steps[-1][2][:200], "iid": incident_id,
             "t0": t0, "t1": t0 + timedelta(seconds=2 * len(steps) + 6)}).scalar_one()
        for i, (name, st, msg, out) in enumerate(steps):
            s = t0 + timedelta(seconds=2 * i + (3 if i else 0))
            self.db.execute(text("""
                INSERT INTO agent_step (run_id, seq, agent_name, status, message, output, started_at, finished_at)
                VALUES (:r, :s, :a, :st, :m, CAST(:o AS jsonb), :t0, :t1)"""),
                {"r": run_id, "s": i + 1, "a": name, "st": st, "m": msg, "t0": s, "t1": s + timedelta(seconds=1.4),
                 "o": json.dumps(out, ensure_ascii=False, default=str)})

    def _detect_step(self, c: dict, cand: str | None) -> tuple:
        sc, kind = c["sc"], c["kind"]
        if kind == "GEN":
            out = {"is_incident": False, "category": "일반", "error_type": "기타", "channel": "앱", "source": "LLM",
                   "stt_analysis": {"is_incident": False, "reason": "고객 발화에 장애 신호어 없음 (일반 문의)"},
                   "consult_analysis": {"is_incident": False, "reason": "상담유형 '일반문의', 요약에 장애 신호어 없음"}}
            return (detection.NAME, "SKIPPED",
                    "장애 미감지 (LLM) - STT 원문: 정상 · 상담이력: 정상 → 일반 상담으로 판단, 에이전트 종료", out)
        if kind == "IMP":
            out = {"is_incident": False, "category": "개선의견", "error_type": sc["error_type"], "channel": sc["channel"],
                   "title": sc["title"], "source": "LLM",
                   "stt_analysis": {"is_incident": False, "reason": "해결·완료된 건에 대한 화면 문구·절차 개선 요청"},
                   "consult_analysis": {"is_incident": False, "reason": "상담유형 '일반문의', 개선 의견 접수"}}
            return (detection.NAME, "DONE",
                    f"개선의견 감지 (LLM) - 현재 막힌 업무 없이 문구·절차 개선을 요청 → 알림 없이 개선의견으로 기록, "
                    f"유형={sc['error_type']}, 채널={sc['channel']}", out)
        env_txt = ", ".join(f"{k}={v}" for k, v in c["env"].items() if k in ("os", "device", "app_version", "browser"))
        out = {"is_incident": True, "category": "장애", "error_type": sc["error_type"], "channel": sc["channel"],
               "severity_candidate": cand, "title": sc["title"], "symptoms": _fill(sc["symptoms"], c["slots"]),
               "env": c["env"], "source": "LLM",
               "stt_analysis": {"is_incident": True, "reason": f"고객 발화: {c['customer_text'].splitlines()[0][:80]}"},
               "consult_analysis": {"is_incident": True,
                                    "reason": f"상담유형 '전산오류문의', 접촉채널 '{sc['channel']}', 요약에 오류 내용 기재"}}
        return (detection.NAME, "DONE",
                f"장애 감지 (LLM) - STT 원문: 장애 · 상담이력: 장애 → 유형={sc['error_type']}, 채널={sc['channel']}, "
                f"심각도 후보={cand}" + (f", 환경[{env_txt}]" if env_txt else ""), out)

    # ------------------------------------------------------------------ RAG 유사 사례 (그 시점에 처리완료된 장애만)
    def _similar(self, sc: dict, slots: dict, at: datetime) -> list[dict]:
        q = f"{sc['title']} {_fill(sc['symptoms'], slots)}"
        cases = []
        for k in self.knowledge:
            if k["resolved_at"] > at:
                continue
            sim = rules.similarity(q, f"{k['title']} {k['symptoms']}")
            if k["error_type"] == sc["error_type"]:
                sim = round(min(1.0, sim + 0.1), 3)
            if sim >= 0.1:
                cases.append({"incident_id": k["incident_id"], "title": k["title"], "status": k["status"],
                              "severity": k["severity"], "error_type": k["error_type"], "symptoms": k["symptoms"],
                              "resolution": k["resolution"], "similarity": sim})
        cases.sort(key=lambda x: x["similarity"], reverse=True)
        return cases[:3]

    def _severity_step(self, sev: str, notify_: bool, similar: list[dict], reasons: list[str], applied: list[str],
                       analysis: str) -> tuple:
        cr = self.cr
        refs = [s["incident_id"] for s in similar if s["status"] == "해결"][:2]
        rs = [f"판별기준 {cr.version} ({cr.source})"] + reasons + [
            f"RAG 유사 사례 검색 ({RAG}): {len(similar)}건" + (" → LLM 프롬프트에 제공" if similar else "")]
        if refs:
            rs.append("LLM 참고 사례: " + ", ".join(repo.incident_no(r) for r in refs))
        rs.append(f"1차 판별: {sev}({cr.label(sev)}) → " + ("알림 대상" if notify_ else "알림 미대상"))
        fp_cases = [s for s in similar if s["status"] == "오탐"]
        if notify_:
            rs.append(f"2차 대조: 과거 오탐 사례와 일치 없음 ({RAG}, 비교 {len(similar)}건) → 최종 알림 대상")
            decision = f"1차 {sev} 알림 대상 → 2차 오탐 대조 통과 → 메신저 알림 대상"
        else:
            rs.append("2차 대조 생략 (1차에서 알림 미대상)")
            decision = (f"1차 {sev} 미대상 → 알림 미대상, "
                        + ("관찰 등록 (센터관리자 확인)" if cr.observe(sev) else "미대상 종결 (추가 제보 시 재판정)"))
        out = {"severity": sev, "severity_label": cr.label(sev), "notify": notify_, "false_positive": False,
               "stage1": {"severity": sev, "notify": notify_},
               "stage2": {"checked": notify_, "method": RAG, "fp_cases": len(fp_cases), "matched": None}
               if notify_ else {"checked": False},
               "reasons": rs, "similar_cases": similar, "analysis": analysis,
               "source": f"판별기준+LLM+RAG({RAG})", "rag_method": RAG, "criteria_version": cr.version,
               "criteria_source": cr.source, "applied_rules": applied,
               "rag": {"method": RAG, "count": len(similar), "in_llm": bool(similar), "ref_cases": refs}}
        rules_txt = ", ".join(a for a in applied if not a.startswith("BASE"))
        msg = (f"최종 {sev}({cr.label(sev)}) / {decision} [판별기준+LLM+RAG({RAG})]"
               + (f" · 적용 규칙 {rules_txt}" if rules_txt else "")
               + f" · RAG 유사 사례 {len(similar)}건"
               + (f"(LLM 참고 {', '.join(repo.incident_no(r) for r in refs)})" if refs else ""))
        return (severity.NAME, "DONE", msg, out)

    # ------------------------------------------------------------------ 장애 처리 (IT담당자)
    def _staff(self, etype: str, rng: random.Random) -> dict:
        staff = self.it_staff.get(etype) or self.it_staff["기타"]
        workers = [e for e in staff if e["duty_role"] in ("담당", "부담당")] or staff
        return rng.choice(workers)

    def _action(self, iid: int, ps: str, before: str, after: str, content: str, emp: dict, at: datetime) -> None:
        login = "user" if emp["emp_name"] == "김도윤" else emp["emp_no"].lower()
        self.db.execute(text("""
            INSERT INTO incident_action (incident_id, process_status, status_before, status_after, content, emp_id,
                                         actor_login, actor_name, created_at)
            VALUES (:iid, :ps, :b, :a, :c, :e, :lg, :nm, :at)"""),
            {"iid": iid, "ps": ps, "b": before, "a": after, "c": content, "e": emp["emp_id"], "lg": login,
             "nm": emp["emp_name"], "at": at})

    def _resolve(self, inc: dict, sc: dict, slots: dict, start: datetime, work_min: tuple[int, int],
                 resolve_min: tuple[int, int], rng: random.Random) -> None:
        """알림을 받은 IT담당자: 진행중 → 처리완료(해결). 오늘 오전 이후로 넘어가지 않게 맞춤."""
        limit = _kst(TODAY, 11, 30)
        emp = self._staff(sc["error_type"], rng)
        t1 = min(start + timedelta(minutes=rng.randint(*work_min)), limit - timedelta(minutes=30))
        t2 = min(t1 + timedelta(minutes=rng.randint(*resolve_min)), limit)
        resolution = _fill(sc["resolution"], slots)
        self._action(inc["incident_id"], "진행중", "접수", "확인중",
                     f"확인 착수: {sc['title']} 관련 로그·영향 범위 점검", emp, t1)
        self._action(inc["incident_id"], "처리완료", "확인중", "해결", resolution, emp, t2)
        self._set_closed(inc, "해결", resolution, t2, emp)

    def _set_closed(self, inc: dict, status: str, resolution: str, at: datetime, emp: dict) -> None:
        self.db.execute(text("""
            UPDATE incident_alert SET status = :st, resolution = :res, resolved_at = :t, resolved_by_emp_id = :e,
                                      updated_at = :t WHERE incident_id = :id"""),
            {"st": status, "res": resolution, "t": at, "e": emp["emp_id"], "id": inc["incident_id"]})
        if status in ("해결", "오탐"):                 # RAG 지식베이스 (미대상은 넣지 않음)
            self.knowledge.append({**inc, "status": status, "resolution": resolution, "resolved_at": at,
                                   "resolver": emp["emp_id"]})

    # ------------------------------------------------------------------ 관찰 장애 (센터관리자)
    def _manager(self, rng: random.Random) -> dict:
        return self.emp_by_name[rng.choice(MANAGERS)]

    def _manager_action(self, inc: dict, ps: str, after: str, content: str, mgr: dict, at: datetime) -> None:
        self.db.execute(text("""
            INSERT INTO incident_action (incident_id, process_status, status_before, status_after, content, emp_id,
                                         actor_login, actor_name, created_at)
            VALUES (:iid, :ps, '관찰', :a, :c, :e, :lg, :nm, :at)"""),
            {"iid": inc["incident_id"], "ps": ps, "a": after, "c": content, "e": mgr["emp_id"],
             "lg": MANAGER_LOGIN.get(mgr["emp_name"], mgr["emp_no"].lower()), "nm": mgr["emp_name"], "at": at})

    def _manual_send(self, inc: dict, mgr: dict, at: datetime) -> dict:
        """센터관리자가 IT담당자를 지정해 수동 알림 (자동 작성 메시지 그대로) → 접수(대기중)."""
        sender = f"센터관리자 {mgr['emp_name']}"
        detail = repo.get_incident(self.db, inc["incident_id"])
        draft = notify.manual_draft(self.db, detail, inc["severity"], sender)
        link = notify.detail_url(inc["incident_id"])
        rows = [(e, "1차") for e in draft["primary"]] + [(e, "2차") for e in draft["secondary"]]
        self.db.execute(text("""
            INSERT INTO messenger_log (incident_id, receiver, receiver_name, title, body, transport, status, emp_id,
                                       recipient_type, link_url, sent_at)
            VALUES (:iid, :rcv, :name, :title, :body, 'MOCK', 'SENT', :emp, :rt, :link, :at)"""),
            [{"iid": inc["incident_id"], "rcv": e["messenger_id"], "name": e["emp_name"], "title": draft["title"],
              "body": draft["body"], "emp": e["emp_id"], "rt": rt, "link": link, "at": at} for e, rt in rows])
        self.counts["messages"] += len(rows)
        who = lambda t: ", ".join(e["emp_name"] for e, rt in rows if rt == t) or "-"  # noqa: E731
        self._manager_action(inc, "대기중", "접수",
                             f"수동 알림 전송 ({sender}) · 등급 {inc['severity']} · 1차 {who('1차')} / 2차 {who('2차')}\n"
                             "단일 고객이지만 재시도 후에도 업무가 막혀 있어 담당자 확인 요청", mgr, at)
        owner = draft["primary"][0]["emp_id"] if draft["primary"] else None
        return repo._row(self.db.execute(text("""
            UPDATE incident_alert SET status = '접수', notified_severity = severity, owner_emp_id = :o, updated_at = :t
             WHERE incident_id = :id RETURNING *"""), {"o": owner, "t": at, "id": inc["incident_id"]}))

    def _manager_close(self, inc: dict, mgr: dict, at: datetime, status: str, reason: str) -> None:
        """센터관리자가 알림 없이 종결: 미대상 또는 오탐(고객 실수·정상 동작)."""
        self._manager_action(inc, status, status, f"알림 없이 종결 (센터관리자 {mgr['emp_name']})\n{reason}", mgr, at)
        self._set_closed(inc, status, reason, at, mgr)

    # ------------------------------------------------------------------ 장애 등록
    def _create_incident(self, c: dict, sev: str, similar: list[dict], applied: list[str], status: str) -> dict:
        sc = c["sc"]
        at = c["consult_at"] + timedelta(seconds=7)
        inc = repo._row(self.db.execute(text("""
            INSERT INTO incident_alert (title, error_type, channel, severity, status, report_count, customer_count,
                                        mass_signal, symptoms, env_info, analysis, similar_cases,
                                        criteria_version, applied_rules, first_reported_at, last_reported_at,
                                        resolved_at, created_at, updated_at)
            VALUES (:title, :et, :ch, :sev, :st, 1, 1, FALSE, :sym, CAST(:env AS jsonb), :an, CAST(:sim AS jsonb),
                    :ver, CAST(:rules AS jsonb), :at, :at, :closed, :at, :at) RETURNING *"""),
            {"title": sc["title"], "et": sc["error_type"], "ch": sc["channel"], "sev": sev, "st": status,
             "sym": _fill(sc["symptoms"], c["slots"]), "env": json.dumps(c["env"], ensure_ascii=False),
             "an": sc["analysis"], "sim": json.dumps(similar, ensure_ascii=False, default=str),
             "ver": self.cr.version, "rules": json.dumps(applied), "at": at,
             "closed": at if status == "미대상" else None}))
        self.db.execute(text("INSERT INTO incident_report (incident_id, consult_id, similarity, created_at)"
                             " VALUES (:i, :c, 1.0, :at)"),
                        {"i": inc["incident_id"], "c": c["consult"]["consult_id"], "at": inc["created_at"]})
        self.counts["incidents"] += 1
        return inc

    def _single(self, c: dict, rng: random.Random) -> None:
        """P2 · P3 · P4 · 고객 실수: 단일 제보 → 등급 정의의 관찰 여부에 따라 관찰 / 미대상 등록.
        관찰 건은 센터관리자가 수동 알림(→ IT담당자 처리완료) 또는 종결(미대상 / 오탐)."""
        sc, kind = c["sc"], c["kind"]
        base = BASE[sc["error_type"]]
        sev = {"P2": "P2", "P3": "P3", "P4": "P4", "FP": base}[kind]
        status = self.cr.unnotified_status(sev)
        similar = self._similar(sc, c["slots"], c["consult_at"])
        applied = [f"BASE:{sc['error_type']}", "LLM"]
        reasons = [f"[BASE] 유형 '{sc['error_type']}' 기본 등급 {base}"]
        if kind == "P2" and base != "P2":
            applied.insert(1, "PERSIST_P2")
            reasons.append(f"[PERSIST_P2] 지속 차단: 재시도 후에도 같은 오류 → {base}→P2")
        if kind == "P3" and base == "P2":
            applied.insert(1, "RECOVERED_P3")
            reasons.append(f"[RECOVERED_P3] 일시 실패 후 정상 진행: 재시도 후 완료 확인 → P2→P3")
        reasons.append(f"LLM: {'재시도 후에도 진행이 막혀 P2, 고객 귀책 여부는 확인 필요' if kind == 'FP' else '고객 발화 기준 영향 범위 판단'} → {sev}")
        inc = self._create_incident(c, sev, similar, applied, status)
        steps = [self._detect_step(c, base),
                 (dedup.NAME, "DONE", "최근 60분 내 동일 유형 미해결 장애 0건 비교 → 유사 장애 없음, 신규 장애로 판단",
                  {"merged": False, "report_count": 1, "customer_count": 1, "mass_signal": False, "window_min": 60}),
                 self._severity_step(sev, False, similar, reasons, applied, sc["analysis"]),
                 self._record_step(inc, "신규 등록")]
        self._run(c, steps, "DONE", inc["incident_id"])
        if status != "관찰":
            return                                  # P3 · P4: 미대상 자동 종결
        mgr = self._manager(rng)
        seen = inc["created_at"] + timedelta(minutes=rng.randint(8, 40))
        if kind == "FP":
            self._manager_close(inc, mgr, seen, "오탐", _fill(sc["resolution"], c["slots"]))
        elif rng.random() < 0.65:
            inc = self._manual_send(inc, mgr, seen)
            self._resolve(inc, sc, c["slots"], seen, (10, 40), (90, 300), rng)
        else:
            self._manager_close(inc, mgr, seen, "미대상", rng.choice(CLOSE_REASONS))

    def _record_step(self, inc: dict, action: str) -> tuple:
        no = repo.incident_no(inc["incident_id"])
        reason = ("관찰 등급 - 센터관리자 확인 후 IT담당자 수동 알림" if inc["status"] == "관찰"
                  else "관찰 대상이 아닌 등급 - 미대상 종결, 추가 제보 시 재판정")
        cnt = f"(누적 {inc['report_count']}건, 상태 {inc['status']})" if action == "갱신" else f"(상태 {inc['status']})"
        return (notify.RECORD_NAME, "DONE", f"장애 {no} {action}{cnt} - 메신저 미발송 ({reason})",
                {"incident_id": inc["incident_id"], "incident_status": inc["status"], "severity": inc["severity"],
                 "sent": False, "recipients": []})

    def _p1(self, calls: list[dict], rng: random.Random) -> None:
        """같은 장애 3명 제보: 1·2번째는 P2 관찰, 3번째에 독립 고객 3명 → 대규모 장애 신호 → P1 메신저 알림."""
        sc, cr = calls[0]["sc"], self.cr
        similar = self._similar(sc, calls[0]["slots"], calls[0]["consult_at"])
        inc = None
        for i, c in enumerate(calls):
            if i == 0:
                applied = [f"BASE:{sc['error_type']}", "PERSIST_P2", "LLM"]
                inc = self._create_incident(c, "P2", similar, applied, cr.unnotified_status("P2"))
                no = repo.incident_no(inc["incident_id"])
                reasons = [f"[BASE] 유형 '{sc['error_type']}' 기본 등급 {BASE[sc['error_type']]}",
                           "[PERSIST_P2] 지속 차단: 재시도 후에도 같은 오류", "LLM: 업무 진행이 막혀 P2, 독립 고객 1명으로 P1 조건 미충족 → P2"]
                steps = [self._detect_step(c, "P2"),
                         (dedup.NAME, "DONE", "최근 60분 내 동일 유형 미해결 장애 0건 비교 → 유사 장애 없음, 신규 장애로 판단",
                          {"merged": False, "report_count": 1, "customer_count": 1, "mass_signal": False, "window_min": 60}),
                         self._severity_step("P2", False, similar, reasons, applied, sc["analysis"]),
                         self._record_step(inc, "신규 등록")]
                self._run(c, steps, "DONE", inc["incident_id"])
                continue
            n = i + 1
            score = round(0.55 + rng.random() * 0.25, 3)
            mass = n >= cr.mass_threshold()
            sev = "P1" if mass else "P2"
            at = c["consult_at"] + timedelta(seconds=7)
            self.db.execute(text("INSERT INTO incident_report (incident_id, consult_id, similarity, created_at)"
                                 " VALUES (:i, :c, :s, :at)"),
                            {"i": inc["incident_id"], "c": c["consult"]["consult_id"], "s": score, "at": at})
            env = {**inc["env_info"], **c["env"]}
            inc = repo._row(self.db.execute(text("""
                UPDATE incident_alert SET report_count = :n, customer_count = :n, mass_signal = :m, severity = :sev,
                       status = :st, last_reported_at = :at, updated_at = :at, env_info = CAST(:env AS jsonb),
                       applied_rules = CAST(:rules AS jsonb)
                 WHERE incident_id = :id RETURNING *"""),
                {"n": n, "m": mass, "sev": sev, "st": "접수" if mass else inc["status"], "at": at,
                 "env": json.dumps(env, ensure_ascii=False), "id": inc["incident_id"],
                 "rules": json.dumps([f"BASE:{sc['error_type']}", "PERSIST_P2", "MASS_P1", "LLM"] if mass
                                     else [f"BASE:{sc['error_type']}", "PERSIST_P2", "LLM"])}))
            dd_msg = f"장애 {no}에 동일 제보로 통합 (유사도 {score}, 누적 {n}건 · 독립 고객 {n}명)"
            if mass:
                dd_msg += f" → 대규모 장애 신호 (기준 독립 고객 {cr.mass_threshold()}명 이상) · 모니터 '동일유형 장애' 건수에 등록"
            dd_out = {"merged": True, "incident_id": inc["incident_id"], "similarity": score, "report_count": n,
                      "customer_count": n, "mass_signal": mass, "previous_severity": "P2", "window_min": 60}
            applied = [f"BASE:{sc['error_type']}", "PERSIST_P2"] + (["MASS_P1"] if mass else []) + ["LLM"]
            reasons = [f"[BASE] 유형 '{sc['error_type']}' 기본 등급 {BASE[sc['error_type']]}",
                       "[PERSIST_P2] 지속 차단: 재시도 후에도 같은 오류"]
            if mass:
                reasons.append(f"[MASS_P1] 대규모 장애 신호: 대규모 장애 신호(독립 고객 {n}명, 누적 {n}건) → P2→P1")
            reasons.append("통합된 기존 장애 등급 P2 유지" if not mass else "LLM: 같은 증상 독립 고객 3명, 핵심 거래 차단 → P1")
            sev_step = self._severity_step(sev, mass, similar, reasons, applied, sc["analysis"])
            if not mass:
                steps = [self._detect_step(c, "P2"), (dedup.NAME, "DONE", dd_msg, dd_out), sev_step,
                         self._record_step(inc, "갱신")]
                self._run(c, steps, "DONE", inc["incident_id"])
                continue
            # ---- 3번째 제보: P1 메신저 알림 (MOCK 기록) ----
            notify_out, msg = self._messages(inc, c, sev_step[3], at + timedelta(seconds=3))
            steps = [self._detect_step(c, "P2"), (dedup.NAME, "DONE", dd_msg, dd_out), sev_step,
                     (notify.NAME, "DONE", msg, notify_out)]
            self._run(c, steps, "DONE", inc["incident_id"])
            owner = (self.it_staff.get(sc["error_type"]) or self.it_staff["기타"])[0]
            self.db.execute(text("UPDATE incident_alert SET notified_severity = 'P1', owner_emp_id = :o"
                                 " WHERE incident_id = :id"), {"id": inc["incident_id"], "o": owner["emp_id"]})
            self._resolve(inc, sc, calls[0]["slots"], at, (6, 14), (60, 150), rng)

    def _messages(self, inc: dict, c: dict, sev_out: dict, at: datetime) -> tuple[dict, str]:
        cr = self.cr
        roles = cr.roles(inc["severity"])
        staff = self.it_staff.get(inc["error_type"]) or self.it_staff["기타"]
        primary = [e for e in staff if e["duty_role"] in roles] or staff[:1]
        solved = [s for s in sev_out["similar_cases"] if s["status"] == "해결"]
        seen, secondary, names = {e["emp_id"] for e in primary}, [], {}
        for s in solved:
            k = next((k for k in self.knowledge if k["incident_id"] == s["incident_id"]), None)
            emp = next((e for e in self.emp_by_name.values() if k and e["emp_id"] == k["resolver"]), None)
            if emp:
                names[s["incident_id"]] = emp["emp_name"]
                if emp["emp_id"] not in seen and emp.get("messenger_id"):
                    secondary.append({**emp, "for_incident": s["incident_id"]})
                    seen.add(emp["emp_id"])
        consult = {**c["consult"], "customer_name": c["cust"]["customer_name"], "agent_name": f"상담사 {c['agent']}"}
        title, body = notify.compose(self.db, inc, sev_out, consult, primary, secondary, names)
        title = "[등급 상향 P2→P1]" + title
        changed = "; ".join(r for r in sev_out["reasons"] if r.startswith("[")) or "-"
        body = body.replace("▣ 증상", f"▣ 등급 변경\n 이전 P2 → 현재 P1 (근거: {changed})\n\n▣ 증상", 1)
        link = notify.detail_url(inc["incident_id"])
        rows = [(e, "1차") for e in primary] + [(e, "2차") for e in secondary]
        self.db.execute(text("""
            INSERT INTO messenger_log (incident_id, receiver, receiver_name, title, body, transport, status, emp_id,
                                       recipient_type, link_url, sent_at)
            VALUES (:iid, :rcv, :name, :title, :body, 'MOCK', 'SENT', :emp, :rt, :link, :at)"""),
            [{"iid": inc["incident_id"], "rcv": e["messenger_id"], "name": e["emp_name"], "title": title[:200],
              "body": body, "emp": e["emp_id"], "rt": rt, "link": link, "at": at} for e, rt in rows])
        self.counts["messages"] += len(rows)
        p = [f"{e['emp_name']}({e['duty_role']}, {e['dept']})" for e in primary]
        s = [f"{e['emp_name']}({repo.incident_no(e['for_incident'])} 처리)" for e in secondary]
        msg = f"장애 {repo.incident_no(inc['incident_id'])} 갱신(누적 {inc['report_count']}건) → 1차 {', '.join(p)}"
        if s:
            msg += f" / 2차 {', '.join(s)}"
        out = {"incident_id": inc["incident_id"], "incident_status": "접수", "severity": "P1", "sent": True,
               "title": title, "transport": "MOCK", "primary": p, "secondary": s, "recipients": p + s,
               "link_url": link}
        return out, msg + " 에게 메신저 발송 (상세 링크 포함)"

    def _improvement(self, c: dict) -> None:
        sc = c["sc"]
        related = self.db.execute(text("""
            SELECT incident_id, title FROM incident_alert
             WHERE error_type = :et AND status <> '오탐' AND first_reported_at < :at
             ORDER BY first_reported_at DESC LIMIT 1"""), {"et": sc["error_type"], "at": c["consult_at"]}).mappings().first()
        row = repo._row(self.db.execute(text("""
            INSERT INTO improvement_opinion (consult_id, call_id, customer_id, customer_name, error_type, channel,
                                             title, content, customer_excerpt, related_incident_id, created_at)
            VALUES (:cid, :call, :cust, :cname, :et, :ch, :title, :content, :ex, :rel, :at) RETURNING *"""),
            {"cid": c["consult"]["consult_id"], "call": c["call_id"], "cust": c["cust"]["customer_id"],
             "cname": c["cust"]["customer_name"], "et": sc["error_type"], "ch": sc["channel"], "title": sc["title"],
             "content": improve.rule_summary(sc["title"], c["consult"]["summary"]), "ex": c["customer_text"][:1000],
             "rel": related["incident_id"] if related else None, "at": c["consult_at"] + timedelta(seconds=5)}))
        msg = f"개선의견 #{row['improvement_id']} 등록 - 알림·승인 대상 아님, 장애 누적에서 제외"
        if related:
            msg += f" · 관련 장애 {repo.incident_no(related['incident_id'])} '{related['title']}' 연결"
        self._run(c, [self._detect_step(c, None),
                      (improve.NAME, "DONE", msg, {"improvement_id": row["improvement_id"], "sent": False,
                                                   "related_incident_id": row["related_incident_id"]})], "DONE")
        self.counts["improvements"] += 1

    # ------------------------------------------------------------------ 실행
    def load(self) -> dict:
        d = START
        while d <= TODAY:
            rng = random.Random(d.toordinal() * 7)
            calls = self._plan(d)
            done = d < TODAY
            for c in calls:
                self._insert_call(c, done)
            if done:
                for c in calls:
                    self._insert_consult(c)
                p1 = [c for c in calls if c["kind"] == "P1"]
                for c in calls:
                    if c["kind"] == "GEN":
                        self._run(c, [self._detect_step(c, None)], "SKIPPED")
                    elif c["kind"] == "IMP":
                        self._improvement(c)
                    elif c["kind"] == "P1":
                        if c is p1[0]:
                            self._p1(p1, rng)
                    else:
                        self._single(c, rng)
            d += timedelta(days=1)
        return self.counts


def load_if_needed(db) -> dict | None:
    """과거 상담 데이터가 없으면 넣는다. 넣은 건수 반환 (이미 있으면 None)."""
    if db.execute(text("SELECT 1 FROM stt_call WHERE call_id LIKE 'CALL-1015-%' LIMIT 1")).first():
        return None
    counts = _Loader(db).load()
    db.commit()
    log.info("과거 상담 데이터 등록: %s", counts)
    return counts
