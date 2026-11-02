"""시연 초기 데이터(스냅샷) 만들기 — 초기화 때 만들어지는 상담을 실제 에이전트로 판별해 SQL로 저장

  1. 로컬 DB의 시연 데이터(상담·장애·알림·실행·개선의견)를 지우고 시드 SQL을 다시 넣음
  2. 과거 이력(전날까지 14일) 통화·상담이력을 넣고, 시드 통화(02·11 시드의 '진행' 통화)는 전날 저녁으로 옮겨 상담이력 등록
  3. 모든 상담을 등록 시각 순으로 실제 에이전트(LangGraph)로 판별 — 메신저는 MOCK, 단계 연출 지연 없음
     실행 뒤 그 실행이 만든 기록의 시각을 상담 등록 시각으로 옮김 (같은 증상 묶기도 상담 시각 기준)
  4. 하루가 끝날 때마다 그날 과거 이력 장애에 담당자 처리를 붙임 (app/history_seed.py 와 같은 규칙)
       알림 나간 장애 → IT담당자 처리완료 / 관찰 장애 → 고객 실수 유형은 오탐 종결, P1·P2 유형은 65% 수동 알림 후 처리완료,
       나머지는 미대상 종결. 시드 통화로 생긴 장애는 열린 채로 둠
  5. 결과를 sql/16_demo_snapshot.sql 로 내보냄 — 불러올 때 마지막 날이 '불러오는 날의 전날'이 되도록 시각·통화 ID 날짜를 옮김

사용 (backend 폴더에서):
  venv/Scripts/python.exe scripts/build_demo_snapshot.py            처음부터 (LLM 사용 시 1시간 이상)
  venv/Scripts/python.exe scripts/build_demo_snapshot.py --resume   중단된 판별 이어서
  venv/Scripts/python.exe scripts/build_demo_snapshot.py --export   판별 없이 지금 DB 내용만 다시 내보내기
"""
import argparse
import json
import logging
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from psycopg import sql as psql                     # noqa: E402
from psycopg.types.json import Jsonb                 # noqa: E402
from sqlalchemy import text                          # noqa: E402

from app import db_init, history_seed                # noqa: E402
from app.agents import pipeline, rules, summary      # noqa: E402
from app.database import SessionLocal, engine, settings  # noqa: E402
from app.services import repo                        # noqa: E402

log = logging.getLogger("snapshot")
KST = history_seed.KST
OUT = ROOT / "sql" / "16_demo_snapshot.sql"
META_KEY = "demo_snapshot_build"
HISTORY_CALL = r"^CALL-[0-9]{4}-[0-9]{2}$"
# 내보낼 표 (외래키 순서). customer 는 이 데이터가 쓰는 고객만, 없을 때만 넣음
TABLES = ["stt_call", "stt_utterance", "consult_history", "incident_alert", "agent_run", "agent_step",
          "incident_report", "incident_action", "messenger_log", "improvement_opinion"]
# 실행 뒤 시각을 옮길 표 (시각 컬럼은 DB에서 읽음)
RETIME_TABLES = ["agent_run", "agent_step", "incident_alert", "incident_report", "messenger_log", "improvement_opinion"]
_retime_cols: dict[str, list[str]] = {}


def retime_columns(db) -> dict[str, list[str]]:
    if not _retime_cols:
        for t in RETIME_TABLES:
            _retime_cols[t] = list(db.execute(text("""
                SELECT column_name FROM information_schema.columns
                 WHERE table_name = :t AND table_schema = current_schema() AND data_type LIKE 'timestamp%'"""), {"t": t}).scalars())
    return _retime_cols


# ---------------------------------------------------------------------------- 담당자 처리 (과거 이력 규칙)
class Replay(history_seed._Loader):
    def _resolve(self, inc, sc, slots, start, work_min, resolve_min, rng):
        """IT담당자 처리완료. 모든 기록이 마지막 날(전날) 안에 들어가도록 마감 시각을 그날 23:30 으로."""
        limit = history_seed._kst(self.last, 23, 30)
        emp = self._staff(sc["error_type"], rng)
        t1 = min(start + timedelta(minutes=rng.randint(*work_min)), limit - timedelta(minutes=30))
        t2 = min(t1 + timedelta(minutes=rng.randint(*resolve_min)), limit)
        resolution = history_seed._fill(sc["resolution"], slots)
        self._action(inc["incident_id"], "진행중", "접수", "확인중",
                     f"확인 착수: {sc['title']} 관련 로그·영향 범위 점검", emp, t1)
        self._action(inc["incident_id"], "처리완료", "확인중", "해결", resolution, emp, t2)
        self._set_closed(inc, "해결", resolution, t2, emp)

    def plans(self) -> dict[str, dict]:
        """통화 ID → 과거 이력 계획(대본·유형·슬롯). 같은 기간이면 언제 불러도 같음."""
        out, d = {}, self.start
        while d <= self.last:
            for c in self._plan(d):
                out[c["call_id"]] = c
            d += timedelta(days=1)
        return out

    def follow_up(self, day: date, plans: dict) -> int:
        """그날 생긴 과거 이력 장애 중 아직 처리 기록이 없는 것에 담당자 처리를 붙임."""
        rows = repo._rows(self.db.execute(text("""
            SELECT i.*, (SELECT h.call_id FROM incident_report r JOIN consult_history h USING (consult_id)
                          WHERE r.incident_id = i.incident_id ORDER BY r.created_at LIMIT 1) AS first_call,
                   (SELECT max(m.sent_at) FROM messenger_log m WHERE m.incident_id = i.incident_id) AS last_sent
              FROM incident_alert i
             WHERE (i.first_reported_at AT TIME ZONE 'Asia/Seoul')::date = :d
               AND i.status IN ('접수', '관찰')
               AND NOT EXISTS (SELECT 1 FROM incident_action a WHERE a.incident_id = i.incident_id)
             ORDER BY i.first_reported_at"""), {"d": day}))
        limit = history_seed._kst(self.last, 23, 30)
        done = 0
        for inc in rows:
            c = plans.get(inc["first_call"] or "")
            if not c:
                continue                               # 시드 통화로 생긴 장애는 열린 채로
            sc, kind = c["sc"], c["kind"]
            rng = random.Random(inc["incident_id"] * 7919)
            if inc["status"] == "접수":                 # 에이전트가 알림을 보냄 → IT담당자 처리완료
                self._resolve(inc, sc, c["slots"], inc["last_sent"] or inc["last_reported_at"], (6, 14), (60, 150), rng)
            else:                                       # 관찰 → 센터관리자 확인
                mgr = self._manager(rng)
                seen = min(inc["last_reported_at"] + timedelta(minutes=rng.randint(8, 40)), limit - timedelta(minutes=60))
                if kind == "FP":
                    self._manager_close(inc, mgr, seen, "오탐", history_seed._fill(sc["resolution"], c["slots"]))
                elif kind in ("P1", "P2") and rng.random() < 0.65:
                    inc = self._manual_send(inc, mgr, seen)
                    self._resolve(inc, sc, c["slots"], seen, (10, 40), (90, 300), rng)
                else:
                    self._manager_close(inc, mgr, seen, "미대상", rng.choice(history_seed.CLOSE_REASONS))
            done += 1
        self.db.commit()
        return done


# ---------------------------------------------------------------------------- 준비
def period_meta(db, period=None):
    """판별 중인 기간을 app_meta 에 기억 (이어서 실행할 때 같은 기간 사용)."""
    if period:
        db.execute(text("INSERT INTO app_meta (key, value) VALUES (:k, :v) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"),
                   {"k": META_KEY, "v": json.dumps([period[0].isoformat(), period[1].isoformat()])})
        db.commit()
        return period
    v = db.execute(text("SELECT value FROM app_meta WHERE key = :k"), {"k": META_KEY}).scalar()
    if not v:
        raise SystemExit("이어서 할 기록이 없습니다. --resume 없이 처음부터 실행하세요.")
    a, b = json.loads(v)
    return date.fromisoformat(a), date.fromisoformat(b)


def prepare() -> tuple[date, date]:
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("TRUNCATE " + ", ".join(db_init.DEMO_TABLES) + " RESTART IDENTITY")
        for name in db_init.DEMO_SQL_FILES:
            cur.execute((db_init.ROOT / "sql" / name).read_text(encoding="utf-8"))
        db_init._meta_table(cur)
        raw.commit()
    finally:
        raw.close()
    with SessionLocal() as db:
        loader = Replay(db)
        counts = loader.load(results=False)
        log.info("과거 이력 통화·상담 등록 %s (%s ~ %s)", counts, loader.start, loader.last)
        # 시드 통화('진행')를 전날 저녁으로 옮기고 상담이력 등록 (서로 간격은 그대로)
        seeds = repo._rows(db.execute(text("SELECT * FROM stt_call WHERE consult_status = '진행' ORDER BY started_at")))
        if seeds:
            shift = history_seed._kst(loader.last, 18, 0) - seeds[0]["started_at"]
            ids = [s["call_id"] for s in seeds]
            db.execute(text("UPDATE stt_call SET started_at = started_at + :d WHERE call_id = ANY(:ids)"), {"d": shift, "ids": ids})
            db.execute(text("UPDATE stt_utterance SET created_at = created_at + :d WHERE call_id = ANY(:ids)"), {"d": shift, "ids": ids})
            for s in seeds:
                call = repo.get_stt_call(db, s["call_id"])
                text_ = " ".join(u["text"] for u in call["utterances"] if u["speaker"] == "CUSTOMER")
                issue = bool(rules.issue_signals(text_))
                at = call["started_at"] + timedelta(seconds=call["duration_sec"] + 90)
                db.execute(text("""
                    INSERT INTO consult_history (call_id, customer_id, customer_name, agent_name, consult_type, channel,
                                                 summary, result_status, registered_by, created_at)
                    VALUES (:call, :cid, :cname, :aname, :ct, :ch, :sm, :rs, 'admin', :at)"""),
                    {"call": call["call_id"], "cid": call["customer_id"], "cname": call["customer_name"],
                     "aname": call["agent_name"], "ct": "전산오류문의" if issue else "일반문의",
                     "ch": rules.detect_channel(text_), "sm": summary.draft(call)["summary"],
                     "rs": "이관" if issue else "완료", "at": at})
                db.execute(text("UPDATE stt_call SET consult_status = '상담완료', completed_at = :at WHERE call_id = :id"),
                           {"at": at, "id": call["call_id"]})
            log.info("시드 통화 %d건 → %s 저녁으로 옮겨 상담이력 등록", len(seeds), loader.last)
        db.commit()
        return period_meta(db, (loader.start, loader.last))


# ---------------------------------------------------------------------------- 판별
def retime(db, run_id: int, wall: datetime, at: datetime) -> None:
    """이 실행이 만든 기록(벽시계 wall 이후)의 시각을 상담 등록 시각(at) 기준으로 옮김."""
    delta = at + timedelta(seconds=2) - wall
    for table, cols in retime_columns(db).items():
        sets = ", ".join(f"{c} = CASE WHEN {c} >= :w THEN {c} + :d ELSE {c} END" for c in cols)
        cond = " OR ".join(f"{c} >= :w" for c in cols)
        db.execute(text(f"UPDATE {table} SET {sets} WHERE {cond}"), {"w": wall, "d": delta})
    db.commit()


def judge(period, limit: int | None = None) -> None:
    settings.agent_step_delay_sec = 0
    settings.messenger_provider, settings.messenger_webhook_url = "mock", ""
    with SessionLocal() as db:
        loader = Replay(db, period)
        plans = loader.plans()
        # 실패·중단된 실행은 지우고 다시 판별
        db.execute(text("DELETE FROM agent_run WHERE status IN ('FAILED', 'RUNNING')"))
        db.commit()
        todo = repo._rows(db.execute(text("""
            SELECT consult_id, call_id, created_at FROM consult_history h
             WHERE NOT EXISTS (SELECT 1 FROM agent_run r WHERE r.consult_id = h.consult_id)
             ORDER BY created_at, consult_id""")))
        todo = todo[:limit] if limit else todo
        total = len(todo)
        log.info("판별할 상담 %d건", total)
        day = None
        t0 = time.time()
        for n, c in enumerate(todo, 1):
            cday = c["created_at"].astimezone(KST).date()
            if day and cday != day:
                log.info("  %s 담당자 처리 %d건", day, loader.follow_up(day, plans))
            day = cday
            wall = db.execute(text("SELECT clock_timestamp()")).scalar() - timedelta(milliseconds=5)
            run_id = pipeline.start_run(db, c["consult_id"])
            pipeline.execute(run_id, c["consult_id"])
            retime(db, run_id, wall, c["created_at"])
            r = db.execute(text("SELECT status, outcome FROM agent_run WHERE run_id = :r"), {"r": run_id}).first()
            eta = (time.time() - t0) / n * (total - n)
            log.info("[%d/%d] %s %s %s · 남은 시간 약 %d분", n, total, c["call_id"], r[0], (r[1] or "")[:80], eta // 60)
        if day:
            log.info("  %s 담당자 처리 %d건", day, loader.follow_up(day, plans))
        # 이어서 실행한 경우 등 처리 기록이 빠진 날이 없도록 전체 기간 한 번 더 (이미 처리한 장애는 건너뜀)
        d = loader.start
        while d <= loader.last:
            loader.follow_up(d, plans)
            d += timedelta(days=1)


# ---------------------------------------------------------------------------- 내보내기
def export(period, out: Path = OUT) -> None:
    raw = engine.raw_connection()
    conn = raw.driver_connection                     # psycopg 연결 (값을 SQL 문자로 바꿀 때 사용)
    try:
        cur = raw.cursor()
        base_last = period[1]
        lines = [
            "-- =====================================================================",
            "-- 16. 시연 초기 데이터 스냅샷 (scripts/build_demo_snapshot.py 로 만든 파일, 직접 고치지 마세요)",
            f"--   과거 이력 {period[0]} ~ {period[1]} 와 시드 통화를 실제 에이전트(LangGraph)로 판별한 결과입니다. 메신저는 MOCK 기록.",
            "--   모두 가상 상담입니다. 불러올 때 마지막 날이 '불러오는 날의 전날'이 되도록 시각과 통화 ID 날짜(CALL-MMDD-NN)를 옮깁니다.",
            "--   (메시지 본문·실행 메시지 안에 글자로 쓴 날짜는 옮기지 않습니다)",
            "--   db_init 이 시연 표(DEMO_TABLES)를 비운 뒤 실행합니다.",
            "-- =====================================================================",
            "DROP TABLE IF EXISTS pg_temp.demo_shift;",
            f"CREATE TEMP TABLE demo_shift AS SELECT ((now() AT TIME ZONE 'Asia/Seoul')::date - 1) - DATE '{base_last.isoformat()}' AS days;",
            "CREATE OR REPLACE FUNCTION pg_temp.ts(t timestamptz) RETURNS timestamptz LANGUAGE sql AS",
            "  $$ SELECT t + make_interval(days => (SELECT days FROM demo_shift)) $$;",
            "CREATE OR REPLACE FUNCTION pg_temp.cid(id text) RETURNS text LANGUAGE sql AS",
            f"  $$ SELECT CASE WHEN id ~ '{HISTORY_CALL}'",
            f"            THEN 'CALL-' || to_char(to_date('{base_last.year}' || substr(id, 6, 4), 'YYYYMMDD')",
            "                 + (CASE WHEN substr(id, 6, 2)::int > " + str(base_last.month) + f" THEN -365 ELSE 0 END)",
            "                 + (SELECT days FROM demo_shift), 'MMDD') || substr(id, 10)",
            "            ELSE id END $$;",
            "",
        ]

        def columns(table):
            cur.execute("""SELECT column_name, data_type FROM information_schema.columns
                            WHERE table_name = %s AND table_schema = current_schema() AND is_generated = 'NEVER'
                            ORDER BY ordinal_position""", (table,))
            return cur.fetchall()

        def value(v, col, dtype):
            if v is None:
                return "NULL"
            if dtype == "jsonb":
                return psql.Literal(Jsonb(v)).as_string(conn)
            if dtype.startswith("timestamp"):
                return f"pg_temp.ts({psql.Literal(v).as_string(conn)})"
            if dtype == "date":
                return f"({psql.Literal(v).as_string(conn)}::date + (SELECT days FROM demo_shift))"
            if col == "call_id":
                return f"pg_temp.cid({psql.Literal(v).as_string(conn)})"
            return psql.Literal(v).as_string(conn)

        def dump(table, where="", conflict=""):
            cols = columns(table)
            names = [c for c, _ in cols]
            cur.execute(f"SELECT {', '.join(names)} FROM {table} {where} ORDER BY 1")
            rows = cur.fetchall()
            lines.append(f"-- {table}: {len(rows)}건")
            for i in range(0, len(rows), 200):
                chunk = rows[i:i + 200]
                vals = ",\n".join("(" + ", ".join(value(v, c, t) for v, (c, t) in zip(r, cols)) + ")" for r in chunk)
                lines.append(f"INSERT INTO {table} ({', '.join(names)}) VALUES\n{vals}{conflict};")
            lines.append("")
            return len(rows)

        dump("customer", "WHERE customer_id IN (SELECT customer_id FROM stt_call UNION SELECT customer_id FROM consult_history)",
             "\nON CONFLICT (customer_id) DO NOTHING")
        counts = {t: dump(t) for t in TABLES}
        # 일련번호를 넣은 마지막 번호 다음부터
        for t in TABLES + ["customer"]:
            cur.execute("""SELECT a.attname, pg_get_serial_sequence(%s, a.attname) FROM pg_attribute a
                            WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
                              AND pg_get_serial_sequence(%s, a.attname) IS NOT NULL""", (t, t, t))
            for col, seq in cur.fetchall():
                lines.append(f"SELECT setval('{seq}', coalesce((SELECT max({col}) FROM {t}), 0) + 1, false);")
        lines.append("SELECT setval('stt_call_no_seq', greatest(coalesce((SELECT max(substring(call_id FROM '^CALL-(\\d+)$')::int)"
                     " FROM stt_call), 0), 1), (SELECT count(*) > 0 FROM stt_call));")
        lines.append("DROP TABLE demo_shift;")
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        log.info("내보냄 %s (%.1f MB) %s", out, out.stat().st_size / 1e6, counts)
    finally:
        raw.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", action="store_true", help="중단된 판별 이어서")
    ap.add_argument("--export", action="store_true", help="판별 없이 지금 DB 내용만 내보내기")
    ap.add_argument("--limit", type=int, help="시험용: 이번에 판별할 상담 수")
    ap.add_argument("--out", help="시험용: 내보낼 파일 (기본 sql/16_demo_snapshot.sql)")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", stream=sys.stdout)
    for name in ("httpx", "voc.pipeline", "voc.severity", "app.db_init"):
        logging.getLogger(name).setLevel(logging.WARNING)
    with SessionLocal() as db:
        period = period_meta(db) if (a.resume or a.export) else None
    if not period:
        period = prepare()
    if not a.export:
        judge(period, a.limit)
    export(period, Path(a.out) if a.out else OUT)


if __name__ == "__main__":
    main()
