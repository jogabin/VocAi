-- =====================================================================
-- 07. 장애 처리 이력 (3단계)
--   장애 상세정보 화면에서 IT담당자가 등록하는 처리 상태 · 처리 내용을 이력으로 남깁니다.
--   화면 처리상태 ↔ 내부 상태 대응 (13_observe_manual_notify.sql 에서 관찰 · 미대상 · 오탐 분리)
--     관찰     = 관찰 (알림 미대상, 센터관리자 확인 대기)
--     대기중   = 접수 (자동·수동 알림 발송)
--     진행중   = 확인중
--     처리완료 = 해결
--     미대상   = 미대상 (등급 기준 자동 종결 · 센터관리자 종결)
--     오탐     = 오탐 (고객 실수·정상 동작)
--   여러 번 실행해도 안전합니다. 06_consult_agent.sql 이후에 실행하세요.
-- =====================================================================
CREATE TABLE IF NOT EXISTS incident_action (
    action_id       BIGSERIAL    PRIMARY KEY,
    incident_id     BIGINT       NOT NULL REFERENCES incident_alert(incident_id) ON DELETE CASCADE,
    process_status  VARCHAR(10)  NOT NULL CHECK (process_status IN ('관찰', '대기중', '진행중', '미대상', '오탐', '처리완료')),
    status_before   VARCHAR(10),                              -- 내부 상태 (변경 전)
    status_after    VARCHAR(10)  NOT NULL,                    -- 내부 상태 (변경 후)
    content         TEXT,                                     -- 처리 내용
    emp_id          INTEGER      REFERENCES employee(emp_id) ON DELETE SET NULL,
    actor_login     VARCHAR(50)  NOT NULL,                    -- 등록자 로그인 아이디
    actor_name      VARCHAR(50),
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_incident_action ON incident_action(incident_id, action_id);

-- 과거 해결/오탐 장애는 처리 결과를 첫 처리 이력으로 옮겨 둠 (상세 화면 표시용)
INSERT INTO incident_action (incident_id, process_status, status_before, status_after, content, emp_id,
                             actor_login, actor_name, created_at)
SELECT i.incident_id, CASE i.status WHEN '해결' THEN '처리완료' ELSE '오탐' END, '접수', i.status,
       i.resolution, coalesce(i.resolved_by_emp_id, i.owner_emp_id), 'system',
       (SELECT emp_name FROM employee e WHERE e.emp_id = coalesce(i.resolved_by_emp_id, i.owner_emp_id)),
       coalesce(i.resolved_at, i.updated_at)
  FROM incident_alert i
 WHERE i.status IN ('해결', '오탐') AND i.resolution IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM incident_action a WHERE a.incident_id = i.incident_id);
