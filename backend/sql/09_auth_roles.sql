-- =====================================================================
-- 09. 로그인 권한 4종으로 변경 (화면 설계서 SCR-01~10 권한 기준)
--   이후: 상담사 / 센터관리자 / IT담당자 / 시스템관리자
--   IT담당자 = 장애 알림을 받아 장애를 처리하는 프로그램 사용자 (시스템 관리 권한 아님)
--
--   화면별 권한
--     SCR-02 상담현황, SCR-03 상담이력등록 : 상담사, 센터관리자, 시스템관리자
--     SCR-04 장애 알림 모니터, SCR-05 장애 상세정보 : 전체 (장애 처리 등록은 IT담당자)
--     SCR-08 판별기준 관리 : IT담당자, 시스템관리자
--     SCR-06 사용자관리, SCR-07 인사정보, SCR-09 고객정보, SCR-10 상담데이터 : 시스템관리자
--
--   기존 계정 변환
--     (가) 처음 체계(관리자 / 일반)
--           관리자 → 시스템관리자
--           일반   → 연결 직원 그룹: 상담사 → 상담사, 센터관리자 → 센터관리자, IT담당자 → IT담당자, 미연결 → 상담사
--     (나) 2026-10-18 중간 체계(상담사 / 센터관리자 / 관리자 / 시스템관리자)
--           관리자 → IT담당자
--   여러 번 실행해도 안전합니다 (이미 IT담당자 포함 4종 체계면 아무것도 하지 않음).
-- =====================================================================
DO $$
DECLARE
    c record;
    old_scheme     boolean := false;   -- (가)
    interim_scheme boolean := false;   -- (나)
BEGIN
    FOR c IN SELECT conname, pg_get_constraintdef(oid) AS def
               FROM pg_constraint
              WHERE conrelid = 'voc_user'::regclass AND contype = 'c'
                AND pg_get_constraintdef(oid) LIKE '%auth_role%'
    LOOP
        IF c.def NOT LIKE '%IT담당자%' THEN
            IF c.def LIKE '%일반%' THEN
                old_scheme := true;
            ELSIF c.def LIKE '%시스템관리자%' THEN
                interim_scheme := true;
            END IF;
            EXECUTE format('ALTER TABLE voc_user DROP CONSTRAINT %I', c.conname);
        END IF;
    END LOOP;

    IF old_scheme THEN
        UPDATE voc_user SET auth_role = '시스템관리자', updated_by = 'migration-09', updated_at = now()
         WHERE auth_role = '관리자';
        UPDATE voc_user u
           SET auth_role = COALESCE((SELECT CASE e.emp_group WHEN '센터관리자' THEN '센터관리자'
                                                             WHEN 'IT담당자'   THEN 'IT담당자'
                                                             ELSE '상담사' END
                                       FROM employee e WHERE e.emp_id = u.emp_id), '상담사'),
               updated_by = 'migration-09', updated_at = now()
         WHERE u.auth_role = '일반';
    ELSIF interim_scheme THEN
        UPDATE voc_user SET auth_role = 'IT담당자', updated_by = 'migration-09', updated_at = now()
         WHERE auth_role = '관리자';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                    WHERE conrelid = 'voc_user'::regclass AND contype = 'c'
                      AND pg_get_constraintdef(oid) LIKE '%IT담당자%') THEN
        ALTER TABLE voc_user ADD CONSTRAINT voc_user_auth_role_check
            CHECK (auth_role IN ('상담사', '센터관리자', 'IT담당자', '시스템관리자'));
    END IF;
END $$;

ALTER TABLE voc_user ALTER COLUMN auth_role SET DEFAULT '상담사';
