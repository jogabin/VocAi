-- =====================================================================
-- 12. 장애번호 (ERR-0001 형식)
--   상담 번호(#상담ID)·실행 번호(run #) 와 헷갈리지 않도록 장애는 'ERR-' 접두어 번호로 표시합니다.
--   incident_id(내부 키)에서 계산되는 저장 컬럼이라 따로 채번하지 않습니다. (9999 초과 시 자릿수 그대로)
--   앱 표시 형식(app/services/repo.py incident_no, frontend utils/format.js incidentNo)과 같아야 합니다.
--   여러 번 실행해도 안전합니다.
-- =====================================================================
ALTER TABLE incident_alert ADD COLUMN IF NOT EXISTS incident_no VARCHAR(20)
    GENERATED ALWAYS AS ('ERR-' || lpad(incident_id::text, greatest(4, length(incident_id::text)), '0')) STORED;
CREATE UNIQUE INDEX IF NOT EXISTS ux_incident_no ON incident_alert(incident_no);
