-- =====================================================================
-- VOC 기반 자율형 장애 알림 AI Agent - 테이블 정의 (PostgreSQL)
-- 실행: python scripts/init_db.py        (테이블 생성 + 시드)
--       python scripts/init_db.py --reset (기존 VOC 테이블 삭제 후 재생성)
-- =====================================================================

-- 1) STT 통화 (콜 단위)
CREATE TABLE IF NOT EXISTS stt_call (
    call_id        VARCHAR(30) PRIMARY KEY,
    customer_id    VARCHAR(30)  NOT NULL,
    customer_name  VARCHAR(50)  NOT NULL,
    agent_name     VARCHAR(50)  NOT NULL,
    inbound_channel VARCHAR(20) NOT NULL DEFAULT '콜센터',
    started_at     TIMESTAMPTZ  NOT NULL,
    duration_sec   INTEGER      NOT NULL DEFAULT 0
);

-- 2) STT 원문 (발화 단위)
CREATE TABLE IF NOT EXISTS stt_utterance (
    utterance_id   BIGSERIAL PRIMARY KEY,
    call_id        VARCHAR(30) NOT NULL REFERENCES stt_call(call_id) ON DELETE CASCADE,
    seq            INTEGER     NOT NULL,
    speaker        VARCHAR(10) NOT NULL CHECK (speaker IN ('AGENT', 'CUSTOMER')),
    offset_sec     INTEGER     NOT NULL DEFAULT 0,
    text           TEXT        NOT NULL,
    UNIQUE (call_id, seq)
);

-- 3) 상담이력
CREATE TABLE IF NOT EXISTS consult_history (
    consult_id     BIGSERIAL PRIMARY KEY,
    call_id        VARCHAR(30) REFERENCES stt_call(call_id),
    customer_id    VARCHAR(30) NOT NULL,
    customer_name  VARCHAR(50),
    agent_name     VARCHAR(50),
    consult_type   VARCHAR(30) NOT NULL,           -- 전산오류문의 / 일반문의 / 불만 / 기타
    channel        VARCHAR(20),                    -- 앱 / 웹 / ARS / 기타 (오류 발생 채널)
    summary        TEXT        NOT NULL,
    memo           TEXT,
    result_status  VARCHAR(20) NOT NULL DEFAULT '완료',  -- 완료 / 이관 / 보류
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_consult_created ON consult_history(created_at DESC);

-- 4) 업무담당자 (오류유형-담당자 매핑)
CREATE TABLE IF NOT EXISTS biz_owner (
    owner_id       SERIAL PRIMARY KEY,
    error_type     VARCHAR(20) NOT NULL,           -- 로그인 / 인증 / 조회 / 이체 / UI오류 / 기타
    system_name    VARCHAR(50) NOT NULL,
    owner_name     VARCHAR(50) NOT NULL,
    dept           VARCHAR(50) NOT NULL,
    role           VARCHAR(10) NOT NULL DEFAULT '담당',  -- 담당 / 부담당 / 팀장
    messenger_id   VARCHAR(50) NOT NULL,
    phone          VARCHAR(20),
    on_duty        BOOLEAN     NOT NULL DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS ix_owner_type ON biz_owner(error_type);

-- 5) 장애 알림 정보 (장애 이력 저장소 / RAG 지식베이스 겸용)
CREATE TABLE IF NOT EXISTS incident_alert (
    incident_id        BIGSERIAL PRIMARY KEY,
    title              VARCHAR(200) NOT NULL,
    error_type         VARCHAR(20)  NOT NULL,
    channel            VARCHAR(20),
    severity           VARCHAR(5)   NOT NULL DEFAULT 'P3',     -- P1 긴급 / P2 높음 / P3 보통 / P4 낮음
    status             VARCHAR(10)  NOT NULL DEFAULT '접수',   -- 관찰 / 접수 / 확인중 / 해결 / 오탐 / 미대상 (13_observe_manual_notify.sql)
    report_count       INTEGER      NOT NULL DEFAULT 1,
    mass_signal        BOOLEAN      NOT NULL DEFAULT FALSE,    -- 동시다발 대규모 장애 신호
    symptoms           TEXT,
    env_info           JSONB        NOT NULL DEFAULT '{}'::jsonb,  -- os / app_version / device / occurred_at_text
    analysis           TEXT,                                   -- 추정 원인 / 초기 분석 가이드
    similar_cases      JSONB        NOT NULL DEFAULT '[]'::jsonb,
    owner_id           INTEGER REFERENCES biz_owner(owner_id),
    notified_severity  VARCHAR(5),                             -- 마지막으로 알림을 보낸 심각도
    resolution         TEXT,                                   -- IT담당자 처리 결과 (지식 축적)
    first_reported_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_reported_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    resolved_at        TIMESTAMPTZ,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_incident_open ON incident_alert(error_type, status, last_reported_at DESC);

-- 6) 장애-제보(상담) 연결 (중복 제보 통합 결과)
CREATE TABLE IF NOT EXISTS incident_report (
    report_id      BIGSERIAL PRIMARY KEY,
    incident_id    BIGINT NOT NULL REFERENCES incident_alert(incident_id) ON DELETE CASCADE,
    consult_id     BIGINT NOT NULL REFERENCES consult_history(consult_id) ON DELETE CASCADE,
    similarity     NUMERIC(4, 3),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (incident_id, consult_id)
);

-- 7) 메신저 전송 이력
CREATE TABLE IF NOT EXISTS messenger_log (
    msg_id         BIGSERIAL PRIMARY KEY,
    incident_id    BIGINT REFERENCES incident_alert(incident_id) ON DELETE SET NULL,
    owner_id       INTEGER REFERENCES biz_owner(owner_id),
    receiver       VARCHAR(50)  NOT NULL,
    receiver_name  VARCHAR(50),
    title          VARCHAR(200) NOT NULL,
    body           TEXT         NOT NULL,
    transport      VARCHAR(10)  NOT NULL DEFAULT 'MOCK',   -- MOCK / WEBHOOK
    status         VARCHAR(10)  NOT NULL DEFAULT 'SENT',   -- SENT / FAILED
    error_message  TEXT,
    sent_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 8) 에이전트 실행 이력 (모니터 화면용)
CREATE TABLE IF NOT EXISTS agent_run (
    run_id         BIGSERIAL PRIMARY KEY,
    consult_id     BIGINT REFERENCES consult_history(consult_id) ON DELETE CASCADE,
    status         VARCHAR(10) NOT NULL DEFAULT 'RUNNING',  -- RUNNING / DONE / SKIPPED / FAILED
    outcome        VARCHAR(200),
    incident_id    BIGINT REFERENCES incident_alert(incident_id) ON DELETE SET NULL,
    llm_used       BOOLEAN     NOT NULL DEFAULT FALSE,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS agent_step (
    step_id        BIGSERIAL PRIMARY KEY,
    run_id         BIGINT NOT NULL REFERENCES agent_run(run_id) ON DELETE CASCADE,
    seq            INTEGER     NOT NULL,
    agent_name     VARCHAR(50) NOT NULL,
    status         VARCHAR(10) NOT NULL DEFAULT 'RUNNING',  -- RUNNING / DONE / SKIPPED / FAILED
    message        TEXT,
    output         JSONB       NOT NULL DEFAULT '{}'::jsonb,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_step_run ON agent_step(run_id, seq);
