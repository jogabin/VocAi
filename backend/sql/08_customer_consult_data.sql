-- =====================================================================
-- 08. 고객정보 · 상담데이터 등록 (신규 화면 2종)
--   - customer: 고객정보 관리 화면 (고객번호 자동 채번)
--   - stt_call.customer_id → customer 연결, 상담사(인사정보) 연결
--   - 상담데이터 등록 화면에서 만드는 통화 ID 채번용 시퀀스
--   여러 번 실행해도 안전합니다. 07_incident_process.sql 이후에 실행하세요.
-- =====================================================================
CREATE SEQUENCE IF NOT EXISTS customer_no_seq START 90001;
CREATE SEQUENCE IF NOT EXISTS stt_call_no_seq START 1;

CREATE TABLE IF NOT EXISTS customer (
    customer_id     VARCHAR(30)  PRIMARY KEY,                 -- 고객번호 (CUST-90001 형식, 자동 채번)
    customer_name   VARCHAR(50)  NOT NULL,
    phone           VARCHAR(20),                              -- 핸드폰번호 (010-0000-0000)
    gender          VARCHAR(2)   CHECK (gender IS NULL OR gender IN ('남', '여')),
    age             INTEGER      CHECK (age IS NULL OR age BETWEEN 0 AND 130),
    created_by      VARCHAR(50)  NOT NULL DEFAULT 'system',
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_by      VARCHAR(50)  NOT NULL DEFAULT 'system',
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_customer_phone ON customer(phone) WHERE phone IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_customer_name ON customer(customer_name);

-- 통화의 상담사(인사정보) 연결
ALTER TABLE stt_call ADD COLUMN IF NOT EXISTS agent_emp_id INTEGER REFERENCES employee(emp_id) ON DELETE SET NULL;
ALTER TABLE stt_call ADD COLUMN IF NOT EXISTS created_by   VARCHAR(50);          -- 상담데이터 등록 화면에서 만든 경우 등록자

-- 시연 데이터 고객 (기존 STT 통화 10건의 고객)
INSERT INTO customer (customer_id, customer_name, phone, gender, age)
SELECT * FROM (VALUES
 ('CUST-10231', '김민수', '010-2381-4402', '남', 34),
 ('CUST-20877', '이영희', '010-5521-0937', '여', 41),
 ('CUST-31502', '박준호', '010-7712-3348', '남', 29),
 ('CUST-40119', '최서연', '010-9034-2215', '여', 37),
 ('CUST-55210', '정다은', '010-4418-7720', '여', 52),
 ('CUST-61733', '한지민', '010-3392-1184', '여', 26),
 ('CUST-72048', '윤성호', '010-6620-4471', '남', 45),
 ('CUST-80562', '강미래', '010-2275-9013', '여', 33),
 ('CUST-91204', '오태양', '010-8841-3306', '남', 58),
 ('CUST-93377', '서하늘', '010-5507-6629', '여', 22)
) AS v(customer_id, customer_name, phone, gender, age)
WHERE NOT EXISTS (SELECT 1 FROM customer c WHERE c.customer_id = v.customer_id);

-- 그 밖에 통화에만 있는 고객도 고객정보로 이관 (연락처 등은 비워 둠)
INSERT INTO customer (customer_id, customer_name)
SELECT DISTINCT ON (s.customer_id) s.customer_id, s.customer_name
  FROM stt_call s
 WHERE NOT EXISTS (SELECT 1 FROM customer c WHERE c.customer_id = s.customer_id)
 ORDER BY s.customer_id, s.started_at DESC;

-- 통화 → 고객 연결 (FK)
DO $$ BEGIN
    ALTER TABLE stt_call ADD CONSTRAINT fk_stt_call_customer FOREIGN KEY (customer_id) REFERENCES customer(customer_id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- 통화 → 상담사 연결 ("상담사 이수진" → 인사정보 이수진)
UPDATE stt_call s SET agent_emp_id = e.emp_id
  FROM employee e
 WHERE s.agent_emp_id IS NULL AND e.emp_group = '상담사'
   AND e.emp_name = regexp_replace(s.agent_name, '^상담사\s*', '');

-- 통화 ID 시퀀스를 기존 최대 번호 다음부터
SELECT setval('stt_call_no_seq',
              greatest(coalesce((SELECT max(substring(call_id FROM '^CALL-(\d+)$')::int) FROM stt_call), 0), 1),
              (SELECT count(*) > 0 FROM stt_call));
