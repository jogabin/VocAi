-- =====================================================================
-- 15. 대규모 장애 신호 시연 데이터 (시스템관리 > 시연 데이터 등록 · POST /api/admin/demo-data)
--   STT 원문 4건. 모두 가상 상담입니다.
--     PR_P1       : 이체 지급 기한 임박, 대체수단 없음 → P1 (1.상담대화_PR_P1.xlsx)        (상담현황만, 시연 때 상담이력 등록)
--     PR_P1_LG_1  : 앱 7.4.0 업데이트 후 로그인 E-1032 오류, 1번째 고객  (등록 기능이 상담이력 등록 + 에이전트 실행)
--     PR_P1_LG_2  : 같은 증상 2번째 고객                                (등록 기능이 상담이력 등록 + 에이전트 실행)
--     PR_P1_LG_3  : 같은 증상 3번째 고객 → 대규모 장애 신호 → P1          (상담현황만, 시연 때 상담이력 등록)
--   PR_P1_LG 3건은 지금 중복 통합(증상 글자 유사도)으로도 하나로 묶이도록 같은 오류 문구·코드·앱 버전을 씁니다.
--   (로컬에서 실제 에이전트로 2회 확인: 2·3번째가 유사도 1.0으로 통합, 3번째에서 독립 고객 3명 → 대규모 신호)
--   통화는 모두 '진행'으로 넣고, PR_P1_LG_1·2 의 상담완료 처리는 app/demo_data.py 가 합니다.
--   같은 장애로 묶이려면 60분 안에 이어서 등록해야 하므로, 시연 직전에 등록하세요.
--   다시 실행하면 이 4건과 그 상담으로 생긴 상담이력·에이전트 실행·장애를 지우고 새로 넣습니다.
-- =====================================================================

-- ---------- 이전에 등록한 이 시연 통화 정리 ----------
DROP TABLE IF EXISTS pg_temp.demo_ls_consult, pg_temp.demo_ls_incident;
CREATE TEMP TABLE demo_ls_consult AS
SELECT consult_id FROM consult_history WHERE call_id IN ('PR_P1', 'PR_P1_LG_1', 'PR_P1_LG_2', 'PR_P1_LG_3');

-- 이 상담들로만 이루어진 장애 (다른 상담 제보가 섞인 장애는 남기고 이 상담의 제보만 빠짐)
CREATE TEMP TABLE demo_ls_incident AS
SELECT r.incident_id FROM incident_report r
 GROUP BY r.incident_id
HAVING bool_and(r.consult_id IN (SELECT consult_id FROM demo_ls_consult));

DELETE FROM consult_history WHERE consult_id IN (SELECT consult_id FROM demo_ls_consult);   -- 실행·단계·제보·개선의견 함께 삭제
DELETE FROM messenger_log WHERE incident_id IN (SELECT incident_id FROM demo_ls_incident);
UPDATE improvement_opinion SET related_incident_id = NULL WHERE related_incident_id IN (SELECT incident_id FROM demo_ls_incident);
UPDATE agent_run SET incident_id = NULL WHERE incident_id IN (SELECT incident_id FROM demo_ls_incident);
DELETE FROM incident_alert WHERE incident_id IN (SELECT incident_id FROM demo_ls_incident);   -- 처리 이력·임베딩 함께 삭제
DELETE FROM stt_call WHERE call_id IN ('PR_P1', 'PR_P1_LG_1', 'PR_P1_LG_2', 'PR_P1_LG_3');  -- 발화 함께 삭제
DROP TABLE demo_ls_consult, demo_ls_incident;

-- ---------- 시연 고객 (가상, 없을 때만) ----------
INSERT INTO customer (customer_id, customer_name, gender, age) VALUES
 ('CUST-71001', '한도윤', '남', 36),
 ('CUST-75004', '노예린', '여', 34),
 ('CUST-75005', '차민재', '남', 45),
 ('CUST-75006', '엄소율', '여', 30)
ON CONFLICT (customer_id) DO NOTHING;

-- ---------- STT 통화 (같은 증상 1·2번째 제보가 먼저, 60분 안) ----------
INSERT INTO stt_call (call_id, customer_id, customer_name, agent_name, inbound_channel, started_at, duration_sec) VALUES
 ('PR_P1_LG_1', 'CUST-75004', '노예린', '상담사 이수진', '콜센터', now() - interval '15 minutes', 84),
 ('PR_P1_LG_2', 'CUST-75005', '차민재', '상담사 정하나', '콜센터', now() - interval '10 minutes', 84),
 ('PR_P1',      'CUST-71001', '한도윤', '상담사 이수진', '콜센터', now() - interval '4 minutes', 144),
 ('PR_P1_LG_3', 'CUST-75006', '엄소율', '상담사 박지훈', '콜센터', now() - interval '2 minutes', 84);

-- ---------- STT 원문 ----------
INSERT INTO stt_utterance (call_id, seq, speaker, offset_sec, text) VALUES
 -- PR_P1 : 1.상담대화_PR_P1.xlsx
 ('PR_P1', 1, 'AGENT', 0, '안녕하세요 고객센터 이수진입니다 무엇을 도와드릴까요'),
 ('PR_P1', 2, 'CUSTOMER', 12, '아 네 저 지금 이체를 해야 되는데요 앱에서 계속 오류가 나요'),
 ('PR_P1', 3, 'AGENT', 24, '네 고객님 확인을 위해 성함과 생년월일 말씀 부탁드립니다'),
 ('PR_P1', 4, 'CUSTOMER', 36, '한도윤이고요 구십 년 삼월 이일이요'),
 ('PR_P1', 5, 'AGENT', 48, '네 확인 감사합니다 어느 단계에서 어떤 문구가 나오나요'),
 ('PR_P1', 6, 'CUSTOMER', 60, '어 그게 계좌이체 화면이고 마지막 확인을 누르면 일시적으로 서비스를 이용할 수 없습니다 라고 나와요 앱을 다시 켜도 똑같아요'),
 ('PR_P1', 7, 'AGENT', 72, '핸드폰 기종이 어떻게 되시나요?'),
 ('PR_P1', 8, 'CUSTOMER', 84, '아이폰 프로 17이에요.'),
 ('PR_P1', 9, 'AGENT', 96, '언제까지 보내셔야 하는 거래인가요 인터넷뱅킹이나 다른 계좌로 대신 보내실 수 있을까요'),
 ('PR_P1', 10, 'CUSTOMER', 108, '오늘 세 시까지 계약금을 보내야 하는데 십 분 남았어요 늦으면 계약이 취소될 수 있어요 인터넷뱅킹도 같은 오류고 지금 쓸 수 있는 다른 계좌도 없어요'),
 ('PR_P1', 11, 'AGENT', 120, '이체가 계속 막히고 지급 기한이 임박한 상황을 긴급 건으로 전달하겠습니다 확인된 처리 상황을 안내드리겠습니다'),
 ('PR_P1', 12, 'CUSTOMER', 132, '네 빨리 좀 부탁드려요'),
 -- PR_P1_LG_1 : 앱 로그인 E-1032 오류, 1번째 고객 (사전 제보)
 ('PR_P1_LG_1', 1, 'AGENT', 0, '안녕하세요, 고객센터 이수진입니다. 무엇을 도와드릴까요?'),
 ('PR_P1_LG_1', 2, 'CUSTOMER', 12, '앱 로그인 버튼을 누르면 ''일시적인 오류가 발생했습니다 E-1032'' 문구가 뜨고 로그인이 안 돼요.'),
 ('PR_P1_LG_1', 3, 'AGENT', 24, '언제부터 그러셨나요?'),
 ('PR_P1_LG_1', 4, 'CUSTOMER', 36, '오늘 앱을 7.4.0으로 업데이트하고 나서부터요. 앱을 다시 켜도 똑같이 E-1032 오류로 로그인이 안 돼요.'),
 ('PR_P1_LG_1', 5, 'AGENT', 48, '사용하시는 기종 확인 부탁드립니다.'),
 ('PR_P1_LG_1', 6, 'CUSTOMER', 60, '갤럭시 S25예요.'),
 ('PR_P1_LG_1', 7, 'AGENT', 72, '확인했습니다. 담당 부서에 바로 전달하겠습니다.'),
 -- PR_P1_LG_2 : 같은 증상 2번째 고객 (사전 제보)
 ('PR_P1_LG_2', 1, 'AGENT', 0, '안녕하세요, 고객센터 정하나입니다.'),
 ('PR_P1_LG_2', 2, 'CUSTOMER', 12, '앱에서 로그인하려고 하면 ''일시적인 오류가 발생했습니다 E-1032'' 문구가 나오고 로그인이 안 돼요.'),
 ('PR_P1_LG_2', 3, 'AGENT', 24, '언제부터 그러셨나요?'),
 ('PR_P1_LG_2', 4, 'CUSTOMER', 36, '아침에 앱을 7.4.0으로 업데이트한 뒤부터요. 앱을 껐다 켜도 똑같이 E-1032 오류로 로그인이 안 돼요.'),
 ('PR_P1_LG_2', 5, 'AGENT', 48, '기종 확인 부탁드립니다.'),
 ('PR_P1_LG_2', 6, 'CUSTOMER', 60, '갤럭시 S24예요.'),
 ('PR_P1_LG_2', 7, 'AGENT', 72, '확인했습니다. 담당 부서에 바로 전달하겠습니다.'),
 -- PR_P1_LG_3 : 같은 증상 3번째 고객 → 대규모 장애 신호 (시연 때 등록)
 ('PR_P1_LG_3', 1, 'AGENT', 0, '안녕하세요, 고객센터 박지훈입니다.'),
 ('PR_P1_LG_3', 2, 'CUSTOMER', 12, '앱 로그인을 하려는데 ''일시적인 오류가 발생했습니다 E-1032'' 문구가 뜨면서 로그인이 안 돼요.'),
 ('PR_P1_LG_3', 3, 'AGENT', 24, '언제부터 그러셨나요?'),
 ('PR_P1_LG_3', 4, 'CUSTOMER', 36, '오늘 앱을 7.4.0으로 업데이트한 다음부터요. 앱을 다시 깔아도 똑같이 E-1032 오류로 로그인이 안 돼요.'),
 ('PR_P1_LG_3', 5, 'AGENT', 48, '기종 확인 부탁드립니다.'),
 ('PR_P1_LG_3', 6, 'CUSTOMER', 60, '갤럭시 S23이에요.'),
 ('PR_P1_LG_3', 7, 'AGENT', 72, '확인했습니다. 담당 부서에 바로 전달하겠습니다.');

-- 통화 → 상담사(인사정보) 연결
UPDATE stt_call s SET agent_emp_id = e.emp_id
  FROM employee e
 WHERE s.call_id IN ('PR_P1', 'PR_P1_LG_1', 'PR_P1_LG_2', 'PR_P1_LG_3') AND e.emp_group = '상담사'
   AND e.emp_name = regexp_replace(s.agent_name, '^상담사\s*', '');
