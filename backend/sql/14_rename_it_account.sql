-- =====================================================================
-- 14. IT담당자 초기 계정 아이디 변경: user02 / user02 → user / user
--   - 이미 배포된 DB에도 적용되도록 서버 시작 때 한 번 실행합니다 (app/db_init.py 의 apply_updates).
--     실행 기록은 app_meta 에 남겨 다시 실행하지 않습니다. 그래서 나중에 user02 를 새로 만들어도 바뀌지 않습니다.
--   - user 가 이미 있으면 아무것도 하지 않습니다.
--   - 비밀번호도 초기값 user 로 바꿉니다 (로그인 실패 잠금도 풀림). 세션은 그대로라 로그인한 상태는 유지됩니다.
-- =====================================================================
UPDATE voc_user
   SET login_id = 'user',
       password_hash = 'pbkdf2_sha256$200000$271f628168521d174c60a5c3107cbe83$dc5298fde2586bc9b649c7217ce06178618e56224a1034137ef4eb9cee33a525',
       fail_count = 0,
       updated_by = 'migration-14',
       updated_at = now()
 WHERE login_id = 'user02'
   AND NOT EXISTS (SELECT 1 FROM voc_user u WHERE u.login_id = 'user');

-- 장애 처리 이력에 남은 처리자 아이디도 함께
UPDATE incident_action SET actor_login = 'user' WHERE actor_login = 'user02';
