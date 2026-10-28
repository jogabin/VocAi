-- =====================================================================
-- 13. 관찰 여부 · 수동 알림 · 미대상 상태
--   알림 조건에 맞지 않는 장애의 처리 방식을 등급 정의에서 정합니다.
--     관찰 여부 체크   → '관찰' 로 등록: 센터관리자가 보고 IT담당자를 지정해 수동 알림 전송(→ 대기중) 또는 종결
--     관찰 여부 미체크 → '미대상' 으로 자동 종결 (같은 증상 추가 제보가 쌓이면 재판정)
--   내부 상태(incident_alert.status) ↔ 화면 처리상태
--     관찰 = 관찰 / 접수 = 대기중 / 확인중 = 진행중 / 해결 = 처리완료 / 미대상 = 미대상 / 오탐 = 오탐(고객 실수·정상 동작)
--   '미대상' 은 RAG 오탐 사례로 쓰지 않습니다 (오탐 = 사람이 확인한 고객 귀책 건만).
--   여러 번 실행해도 안전합니다. 12_incident_no.sql 이후에 실행하세요.
-- =====================================================================
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'severity_grade' AND column_name = 'observe_yn') THEN
        ALTER TABLE severity_grade ADD COLUMN observe_yn BOOLEAN NOT NULL DEFAULT FALSE;
        -- 초기값: P2 만 관찰 (P1 은 자동 알림, P3 · P4 는 미대상)
        UPDATE severity_grade SET observe_yn = TRUE, updated_by = 'system', updated_at = now(),
               change_reason = '초기 데이터: 관찰 여부 추가'
         WHERE grade_code = 'P2';
    END IF;
END $$;
COMMENT ON COLUMN severity_grade.observe_yn IS '알림 미대상일 때 관찰로 등록(센터관리자 확인) 여부. FALSE 면 미대상 자동 종결';

-- 처리 이력의 처리상태: 관찰 · 오탐 추가 (미대상 = 등급 기준 자동 종결 · 센터관리자 종결)
ALTER TABLE incident_action DROP CONSTRAINT IF EXISTS incident_action_process_status_check;
ALTER TABLE incident_action ADD CONSTRAINT incident_action_process_status_check
    CHECK (process_status IN ('관찰', '대기중', '진행중', '미대상', '오탐', '처리완료'));
