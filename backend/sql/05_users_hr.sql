-- =====================================================================
-- 05. 로그인 사용자 / 세션 / 인사정보(직원)
--   - 기존 users 테이블(연습용)은 건드리지 않습니다.
--   - 여러 번 실행해도 안전합니다 (IF NOT EXISTS / WHERE NOT EXISTS).
--   - 초기 계정: admin / admin (시스템관리자), user01 / user01 (상담사), user / user (IT담당자)
--     계정만 초기화: python scripts/init_db.py --reset-users
--   - 권한(auth_role) 4종: 상담사 / 센터관리자 / IT담당자 / 시스템관리자 (기존 DB 변환은 09_auth_roles.sql)
--     → 운영 환경에서는 로그인 후 사용자관리 화면에서 비밀번호를 바꾸세요.
-- =====================================================================

-- 1) 인사정보(직원): 상담사 / 센터관리자 / IT담당자
CREATE TABLE IF NOT EXISTS employee (
    emp_id            SERIAL       PRIMARY KEY,
    emp_no            VARCHAR(20)  NOT NULL UNIQUE,             -- 사번
    emp_name          VARCHAR(50)  NOT NULL,
    emp_group         VARCHAR(10)  NOT NULL
                      CHECK (emp_group IN ('상담사', '센터관리자', 'IT담당자')),
    dept              VARCHAR(50),                              -- 부서
    position          VARCHAR(30),                              -- 직급/직책
    duty_role         VARCHAR(10)                               -- IT담당자 알림 역할: 담당 / 부담당 / 팀장
                      CHECK (duty_role IS NULL OR duty_role IN ('담당', '부담당', '팀장')),
    duty_error_types  TEXT[]       NOT NULL DEFAULT '{}',       -- 담당 오류유형: 로그인 / 인증 / 조회 / 이체 / UI오류 / 기타
    duty_system       VARCHAR(100),                             -- 담당 시스템
    duty_detail       TEXT,                                     -- 업무담당 상세
    messenger_id      VARCHAR(50),
    phone             VARCHAR(20),
    email             VARCHAR(100),
    on_duty           BOOLEAN      NOT NULL DEFAULT TRUE,       -- 근무 중 (알림 수신 가능)
    use_yn            BOOLEAN      NOT NULL DEFAULT TRUE,       -- 재직/사용
    legacy_owner_id   INTEGER      UNIQUE,                      -- 기존 biz_owner.owner_id (이관 추적용)
    created_by        VARCHAR(50)  NOT NULL DEFAULT 'system',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_by        VARCHAR(50)  NOT NULL DEFAULT 'system',
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_employee_group ON employee(emp_group);
CREATE INDEX IF NOT EXISTS ix_employee_duty ON employee USING GIN (duty_error_types);

-- 2) 로그인 사용자
CREATE TABLE IF NOT EXISTS voc_user (
    user_id           SERIAL       PRIMARY KEY,
    login_id          VARCHAR(30)  NOT NULL UNIQUE,
    password_hash     TEXT         NOT NULL,                    -- pbkdf2_sha256$반복$salt$hash
    user_name         VARCHAR(50)  NOT NULL,
    auth_role         VARCHAR(10)  NOT NULL DEFAULT '상담사'
                      CHECK (auth_role IN ('상담사', '센터관리자', 'IT담당자', '시스템관리자')),
    emp_id            INTEGER      REFERENCES employee(emp_id) ON DELETE SET NULL,  -- 연결 직원(인사정보)
    email             VARCHAR(100),
    use_yn            BOOLEAN      NOT NULL DEFAULT TRUE,
    fail_count        INTEGER      NOT NULL DEFAULT 0,          -- 연속 로그인 실패 횟수
    last_login_at     TIMESTAMPTZ,
    pw_changed_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    created_by        VARCHAR(50)  NOT NULL DEFAULT 'system',
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_by        VARCHAR(50)  NOT NULL DEFAULT 'system',
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- 3) 로그인 세션 (토큰은 SHA-256 해시로만 저장)
CREATE TABLE IF NOT EXISTS voc_session (
    token_hash        VARCHAR(64)  PRIMARY KEY,
    user_id           INTEGER      NOT NULL REFERENCES voc_user(user_id) ON DELETE CASCADE,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_seen_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at        TIMESTAMPTZ  NOT NULL,
    client_info       VARCHAR(200)
);
CREATE INDEX IF NOT EXISTS ix_session_user ON voc_session(user_id);

-- ---------------------------------------------------------------------
-- 초기 데이터
-- ---------------------------------------------------------------------

-- IT담당자: 기존 업무담당자(biz_owner)를 그대로 이관
INSERT INTO employee (emp_no, emp_name, emp_group, dept, position, duty_role, duty_error_types,
                      duty_system, duty_detail, messenger_id, phone, on_duty, legacy_owner_id)
SELECT 'IT' || lpad(o.owner_id::text, 4, '0'), o.owner_name, 'IT담당자', o.dept,
       CASE o.role WHEN '팀장' THEN '팀장' ELSE '대리' END,
       o.role, ARRAY[o.error_type], o.system_name,
       o.system_name || ' ' || o.error_type || ' 장애 ' || o.role,
       o.messenger_id, o.phone, o.on_duty, o.owner_id
  FROM biz_owner o
 WHERE NOT EXISTS (SELECT 1 FROM employee e WHERE e.legacy_owner_id = o.owner_id);

-- 상담사 / 센터관리자
INSERT INTO employee (emp_no, emp_name, emp_group, dept, position, duty_detail, messenger_id, phone)
SELECT * FROM (VALUES
 ('CS0001', '이수진', '상담사',     '고객센터 1팀', '선임상담사', '개인고객 전자금융 상담', '8913038773',   '010-7777-0001'),
 ('CS0002', '박지훈', '상담사',     '고객센터 1팀', '상담사',     '개인고객 전자금융 상담', '8913038773', '010-7777-0002'),
 ('CS0003', '정하나', '상담사',     '고객센터 2팀', '상담사',     '이체·카드 상담',         '8913038773',   '010-7777-0003'),
 ('CM0001', '강민정', '센터관리자', '고객센터',     '센터장',     '고객센터 운영 총괄, VOC 장애 알림 시스템 관리', '8913038773', '010-8888-0001'),
 ('CM0002', '조현우', '센터관리자', '고객센터 1팀', '팀장',       '1팀 상담 품질·장애 VOC 1차 확인', '8913038773', '010-8888-0002')
) AS v(emp_no, emp_name, emp_group, dept, position, duty_detail, messenger_id, phone)
WHERE NOT EXISTS (SELECT 1 FROM employee e WHERE e.emp_no = v.emp_no);

-- 로그인 계정
INSERT INTO voc_user (login_id, password_hash, user_name, auth_role, emp_id)
SELECT v.login_id, v.pw, v.user_name, v.auth_role, (SELECT emp_id FROM employee WHERE emp_name = v.user_name ORDER BY emp_id LIMIT 1)
  FROM (VALUES
   ('admin',  'pbkdf2_sha256$200000$865e4d65724ca288e44ab67830c067a1$0a8a13755e0715453c4e9643a343e8719d8fc6e6c11f9e3df44669ca4161f74a', '강민정', '시스템관리자'),
   ('user01', 'pbkdf2_sha256$200000$c707025bdc136efdc4fd723d3d6f968c$e711c8c31136c297753614d0db2870f0f67ac1cf5d0cbc5f8e75fde0743cd040', '이수진', '상담사'),
   ('user',   'pbkdf2_sha256$200000$271f628168521d174c60a5c3107cbe83$dc5298fde2586bc9b649c7217ce06178618e56224a1034137ef4eb9cee33a525', '김도윤', 'IT담당자')
  ) AS v(login_id, pw, user_name, auth_role)
 WHERE NOT EXISTS (SELECT 1 FROM voc_user u WHERE u.login_id = v.login_id)
   -- 예전 IT담당자 계정(user02)이 있는 DB는 새로 만들지 않고 14_rename_it_account.sql 에서 이름을 바꿈
   AND NOT (v.login_id = 'user' AND EXISTS (SELECT 1 FROM voc_user u WHERE u.login_id = 'user02'));
