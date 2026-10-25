-- =====================================================================
-- 06. 상담현황 / 상담이력 / 메신저 전송 개선 (2단계)
--   - 통화별 상담상태(진행/상담완료), 관리자 대화 추가 이력
--   - 상담이력 등록자, 장애 담당자·처리자를 인사정보(employee)와 연결
--   - 메신저 이력에 수신 구분(1차/2차)·상세 링크 기록
--   여러 번 실행해도 안전합니다. 05_users_hr.sql 이후에 실행하세요.
-- =====================================================================

-- 1) 상담상태
ALTER TABLE stt_call ADD COLUMN IF NOT EXISTS consult_status VARCHAR(10) NOT NULL DEFAULT '진행';
ALTER TABLE stt_call ADD COLUMN IF NOT EXISTS completed_at   TIMESTAMPTZ;
DO $$ BEGIN
    ALTER TABLE stt_call ADD CONSTRAINT ck_stt_call_status CHECK (consult_status IN ('진행', '상담완료'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
-- 이미 상담이력이 있는 통화는 상담완료로
UPDATE stt_call c SET consult_status = '상담완료',
       completed_at = (SELECT max(created_at) FROM consult_history h WHERE h.call_id = c.call_id)
 WHERE consult_status = '진행'
   AND EXISTS (SELECT 1 FROM consult_history h WHERE h.call_id = c.call_id);

-- 2) 관리자가 추가한 대화 표시
ALTER TABLE stt_utterance ADD COLUMN IF NOT EXISTS added_by   VARCHAR(50);      -- NULL = STT 원본
ALTER TABLE stt_utterance ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- 3) 상담이력 등록자 (로그인 아이디)
ALTER TABLE consult_history ADD COLUMN IF NOT EXISTS registered_by VARCHAR(50);

-- 4) 장애 담당자 / 처리자 (인사정보)
ALTER TABLE incident_alert ADD COLUMN IF NOT EXISTS owner_emp_id       INTEGER REFERENCES employee(emp_id) ON DELETE SET NULL;
ALTER TABLE incident_alert ADD COLUMN IF NOT EXISTS resolved_by_emp_id INTEGER REFERENCES employee(emp_id) ON DELETE SET NULL;
-- 기존 담당자(biz_owner) → 인사정보로 연결, 과거 해결 건은 담당자를 처리자로
UPDATE incident_alert i SET owner_emp_id = e.emp_id
  FROM employee e WHERE e.legacy_owner_id = i.owner_id AND i.owner_emp_id IS NULL;
UPDATE incident_alert SET resolved_by_emp_id = owner_emp_id
 WHERE status = '해결' AND resolved_by_emp_id IS NULL AND owner_emp_id IS NOT NULL;

-- 5) 메신저 이력: 수신자(인사정보) / 1차·2차 구분 / 상세 링크
ALTER TABLE messenger_log ADD COLUMN IF NOT EXISTS emp_id         INTEGER REFERENCES employee(emp_id) ON DELETE SET NULL;
ALTER TABLE messenger_log ADD COLUMN IF NOT EXISTS recipient_type VARCHAR(10);   -- 1차(담당) / 2차(유사장애 처리자)
ALTER TABLE messenger_log ADD COLUMN IF NOT EXISTS link_url       TEXT;
UPDATE messenger_log m SET emp_id = e.emp_id
  FROM employee e WHERE e.legacy_owner_id = m.owner_id AND m.emp_id IS NULL;

-- 6) 시연용: 과거 해결 장애의 처리자를 별도 담당자로 지정 (메신저 2차 수신자 시연)
INSERT INTO employee (emp_no, emp_name, emp_group, dept, position, duty_role, duty_error_types,
                      duty_system, duty_detail, messenger_id, phone)
SELECT * FROM (VALUES
 ('IT0101', '정다은', 'IT담당자', '모바일앱개발팀', '책임', '담당', ARRAY['UI오류'], '모바일 앱(iOS/Android)',
  'iOS·Android 앱 배포·핫픽스, 앱 토큰/세션 처리', 'jung.daeun', '010-9999-0101'),
 ('IT0102', '김태호', 'IT담당자', '대외계연계팀', '책임', '부담당', ARRAY['기타'], '타행·대외기관 연계',
  '타행이체·오픈뱅킹 대외기관 연계 장애 대응', 'kim.taeho', '010-9999-0102')
) AS v(emp_no, emp_name, emp_group, dept, position, duty_role, duty_error_types, duty_system, duty_detail, messenger_id, phone)
WHERE NOT EXISTS (SELECT 1 FROM employee e WHERE e.emp_no = v.emp_no);

UPDATE incident_alert SET resolved_by_emp_id = (SELECT emp_id FROM employee WHERE emp_no = 'IT0101')
 WHERE title = '[앱] iOS 앱 업데이트 후 로그인 실패' AND status = '해결'
   AND resolved_by_emp_id IS NOT DISTINCT FROM owner_emp_id;
UPDATE incident_alert SET resolved_by_emp_id = (SELECT emp_id FROM employee WHERE emp_no = 'IT0102')
 WHERE title = '[앱] 타행이체 처리중 지연' AND status = '해결'
   AND resolved_by_emp_id IS NOT DISTINCT FROM owner_emp_id;
