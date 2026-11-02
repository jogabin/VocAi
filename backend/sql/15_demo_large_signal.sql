-- =====================================================================
-- 15. 대규모 장애 신호 시연 데이터 (시스템관리 > 시연 데이터 등록 · POST /api/admin/demo-data)
--   STT 원문 4건. 모두 가상 상담입니다.
--     PR_P1       : 이체 지급 기한 임박, 대체수단 없음 → P1 (1.상담대화_PR_P1.xlsx)   (상담현황만, 시연 때 상담이력 등록)
--   앱 비대면 계좌 개설 중 신분증 촬영 반복 실패 — 서로 다른 고객 3명의 같은 원인 제보 (시연확정용/대규모, ADR-015)
--     PR_P1_LG_1  : 1.신분증촬영반복_1_사전등록(상담사_정하나)   고객 노예린 (등록 기능이 상담이력 등록 + 에이전트 실행)
--     PR_P1_LG_2  : 2.신분증촬영반복_2_사전등록(상담사_이수진)   고객 백서현 (등록 기능이 상담이력 등록 + 에이전트 실행)
--     PR_P1_LG_3  : 3.신분증촬영반복_3_시연중등록(상담사_박지훈) 고객 엄소율 (상담현황만, 시연 때 등록 → 독립 고객 3명, 대규모 장애 신호)
--   PR_P1 이 2차 수신자(과거 유사 장애 처리자)에게도 알림이 가도록 과거 해결 사례 1건(가상)을 함께 넣습니다.
--   통화는 모두 '진행'으로 넣고, PR_P1_LG_1·2 의 상담완료 처리는 app/demo_data.py 가 합니다.
--   같은 장애로 묶이려면 60분 안에 이어서 등록해야 하므로, 시연 직전에 등록하세요.
--   다시 실행하면 이 4건(예전 PR_P1_LG_4 포함)과 그 상담으로 생긴 상담이력·에이전트 실행·장애를 지우고 새로 넣습니다.
-- =====================================================================

-- ---------- 이전에 등록한 이 시연 통화 정리 ----------
DROP TABLE IF EXISTS pg_temp.demo_ls_consult, pg_temp.demo_ls_incident, pg_temp.demo_ls_touched;
CREATE TEMP TABLE demo_ls_consult AS
SELECT consult_id FROM consult_history WHERE call_id IN ('PR_P1', 'PR_P1_LG_1', 'PR_P1_LG_2', 'PR_P1_LG_3', 'PR_P1_LG_4');

-- 이 상담들로만 이루어진 장애 (다른 상담 제보가 섞인 장애는 남기고 이 상담의 제보만 빠짐)
CREATE TEMP TABLE demo_ls_incident AS
SELECT r.incident_id FROM incident_report r
 GROUP BY r.incident_id
HAVING bool_and(r.consult_id IN (SELECT consult_id FROM demo_ls_consult));

-- 이 상담 제보가 섞인 다른 장애 (제보만 빠지고 장애는 남음 → 아래에서 건수 다시 계산)
CREATE TEMP TABLE demo_ls_touched AS
SELECT DISTINCT incident_id FROM incident_report
 WHERE consult_id IN (SELECT consult_id FROM demo_ls_consult)
   AND incident_id NOT IN (SELECT incident_id FROM demo_ls_incident);

DELETE FROM consult_history WHERE consult_id IN (SELECT consult_id FROM demo_ls_consult);   -- 실행·단계·제보·개선의견 함께 삭제
UPDATE incident_alert i
   SET report_count = (SELECT count(*) FROM incident_report r WHERE r.incident_id = i.incident_id),
       customer_count = (SELECT count(DISTINCT h.customer_id) FROM incident_report r
                           JOIN consult_history h ON h.consult_id = r.consult_id WHERE r.incident_id = i.incident_id)
 WHERE i.incident_id IN (SELECT incident_id FROM demo_ls_touched);
DELETE FROM messenger_log WHERE incident_id IN (SELECT incident_id FROM demo_ls_incident);
UPDATE improvement_opinion SET related_incident_id = NULL WHERE related_incident_id IN (SELECT incident_id FROM demo_ls_incident);
UPDATE agent_run SET incident_id = NULL WHERE incident_id IN (SELECT incident_id FROM demo_ls_incident);
DELETE FROM incident_alert WHERE incident_id IN (SELECT incident_id FROM demo_ls_incident);   -- 처리 이력·임베딩 함께 삭제
DELETE FROM stt_call WHERE call_id IN ('PR_P1', 'PR_P1_LG_1', 'PR_P1_LG_2', 'PR_P1_LG_3', 'PR_P1_LG_4');  -- 발화 함께 삭제
DROP TABLE demo_ls_consult, demo_ls_incident, demo_ls_touched;

-- ---------- PR_P1 과거 유사 해결 사례 (가상) ----------
--   PR_P1 알림의 2차 수신자(비슷한 과거 장애를 처리한 담당자)가 나오도록, 같은 증상을 대외계연계팀 김태호가 처리한 해결 사례.
--   1차 담당(지급결제운영팀 윤아름·장민호)과 다른 사람이라 2차로 함께 알림을 받습니다. 제목으로 찾아 지우고 다시 넣습니다.
DELETE FROM messenger_log WHERE incident_id IN (SELECT incident_id FROM incident_alert WHERE title = '[앱] 계좌이체 최종 확인 단계 ''일시적으로 서비스를 이용할 수 없습니다'' 오류');
UPDATE agent_run SET incident_id = NULL WHERE incident_id IN (SELECT incident_id FROM incident_alert WHERE title = '[앱] 계좌이체 최종 확인 단계 ''일시적으로 서비스를 이용할 수 없습니다'' 오류');
UPDATE improvement_opinion SET related_incident_id = NULL
 WHERE related_incident_id IN (SELECT incident_id FROM incident_alert WHERE title = '[앱] 계좌이체 최종 확인 단계 ''일시적으로 서비스를 이용할 수 없습니다'' 오류');
DELETE FROM incident_alert WHERE title = '[앱] 계좌이체 최종 확인 단계 ''일시적으로 서비스를 이용할 수 없습니다'' 오류';

INSERT INTO incident_alert (title, error_type, channel, severity, status, report_count, customer_count, symptoms, env_info,
                            analysis, notified_severity, resolution, first_reported_at, last_reported_at, resolved_at,
                            created_at, updated_at, owner_emp_id, resolved_by_emp_id)
SELECT '[앱] 계좌이체 최종 확인 단계 ''일시적으로 서비스를 이용할 수 없습니다'' 오류', '이체', '앱', 'P1', '해결', 3, 3,
       '앱 계좌이체 화면에서 마지막 확인을 누르면 ''일시적으로 서비스를 이용할 수 없습니다'' 문구가 나오고 이체가 되지 않음. 앱을 다시 켜도 같고 인터넷뱅킹도 같은 오류.',
       '{"os": "iOS", "device": "아이폰 15", "error_message": "일시적으로 서비스를 이용할 수 없습니다"}'::jsonb,
       '계좌이체 최종 확인(승인 요청) 단계에서만 실패해 대외계 연계 구간을 우선 점검. 같은 시간대 앱·인터넷뱅킹 모두 실패.',
       'P1',
       '대외계 연계 게이트웨이의 이체 승인 요청 연결이 모두 사용 중이어서 최종 확인 단계에서 응답 시간 초과 발생. 게이트웨이 연결을 다시 시작하고 동시 연결 수를 늘린 뒤 정상화, 실패한 거래는 고객에게 다시 시도하도록 안내.',
       now() - interval '5 days', now() - interval '5 days' + interval '25 minutes', now() - interval '5 days' + interval '2 hours 40 minutes',
       now() - interval '5 days', now() - interval '5 days' + interval '2 hours 40 minutes',
       (SELECT emp_id FROM employee WHERE emp_name = '윤아름' AND emp_group <> '상담사' LIMIT 1),
       (SELECT emp_id FROM employee WHERE emp_name = '김태호' AND emp_group <> '상담사' LIMIT 1);

INSERT INTO incident_action (incident_id, process_status, status_before, status_after, content, emp_id, actor_login, actor_name, created_at)
SELECT i.incident_id, v.ps, v.b, v.a, v.c, e.emp_id, lower(e.emp_no), e.emp_name, i.first_reported_at + v.t
  FROM incident_alert i
  JOIN employee e ON e.emp_id = i.resolved_by_emp_id
  CROSS JOIN (VALUES
    ('진행중', '접수', '확인중', '확인 착수: 이체 최종 확인 단계 오류, 대외계 연계 게이트웨이 응답 시간 점검', interval '30 minutes'),
    ('처리완료', '확인중', '해결', '대외계 연계 게이트웨이의 이체 승인 요청 연결이 모두 사용 중이어서 최종 확인 단계에서 응답 시간 초과 발생. 게이트웨이 연결을 다시 시작하고 동시 연결 수를 늘린 뒤 정상화, 실패한 거래는 고객에게 다시 시도하도록 안내.', interval '2 hours 40 minutes')
  ) AS v(ps, b, a, c, t)
 WHERE i.title = '[앱] 계좌이체 최종 확인 단계 ''일시적으로 서비스를 이용할 수 없습니다'' 오류';

-- ---------- 시연 고객 (가상, 없을 때만) ----------
INSERT INTO customer (customer_id, customer_name, gender, age) VALUES
 ('CUST-71001', '한도윤', '남', 36),
 ('CUST-75004', '노예린', '여', 34),
 ('CUST-75006', '엄소율', '여', 30),
 ('CUST-75007', '백서현', '여', 33)
ON CONFLICT (customer_id) DO NOTHING;

-- ---------- STT 통화 (같은 증상 1·2번째 제보가 먼저, 60분 안 · 고객 3명 모두 다름) ----------
INSERT INTO stt_call (call_id, customer_id, customer_name, agent_name, inbound_channel, started_at, duration_sec) VALUES
 ('PR_P1_LG_1', 'CUST-75004', '노예린', '상담사 정하나', '콜센터', now() - interval '15 minutes', 84),
 ('PR_P1_LG_2', 'CUST-75007', '백서현', '상담사 이수진', '콜센터', now() - interval '10 minutes', 108),
 ('PR_P1',      'CUST-71001', '한도윤', '상담사 이수진', '콜센터', now() - interval '4 minutes', 144),
 ('PR_P1_LG_3', 'CUST-75006', '엄소율', '상담사 박지훈', '콜센터', now() - interval '2 minutes', 108);

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
 -- PR_P1_LG_1 : 1.신분증촬영반복_1_사전등록(상담사_정하나).xlsx
 ('PR_P1_LG_1', 1, 'AGENT', 0, '안녕하세요, 고객센터 정하나입니다. 무엇을 도와드릴까요?'),
 ('PR_P1_LG_1', 2, 'CUSTOMER', 12, '앱 계좌 개설에서 신분증 촬영이 계속 실패해요.'),
 ('PR_P1_LG_1', 3, 'AGENT', 24, '촬영 후에 어떤 화면이 나오나요?'),
 ('PR_P1_LG_1', 4, 'CUSTOMER', 36, '찍으면 다시 찍으라고만 하고요, 밝은 데서 안내선에 맞춰 여러 번 해도 똑같아요. 앱을 껐다 켰는데도 그래요.'),
 ('PR_P1_LG_1', 5, 'AGENT', 48, '오늘 꼭 완료하셔야 하는 신청인가요?'),
 ('PR_P1_LG_1', 6, 'CUSTOMER', 60, '급한 건 아니에요.'),
 ('PR_P1_LG_1', 7, 'AGENT', 72, '화면과 하신 조치를 남겨 확인 후 전달하겠습니다.'),
 -- PR_P1_LG_2 : 2.신분증촬영반복_2_사전등록(상담사_이수진).xlsx
 ('PR_P1_LG_2', 1, 'AGENT', 0, '안녕하세요, 고객센터 이수진입니다. 성함과 휴대폰 번호 뒷자리 말씀해 주시겠어요?'),
 ('PR_P1_LG_2', 2, 'CUSTOMER', 12, '백서현입니다. 뒷자리는 육이삼사예요.'),
 ('PR_P1_LG_2', 3, 'AGENT', 24, '확인됐습니다. 어떤 일로 연락 주셨나요?'),
 ('PR_P1_LG_2', 4, 'CUSTOMER', 36, '비대면 계좌 개설하는데 신분증 촬영이 실패로 나와요.'),
 ('PR_P1_LG_2', 5, 'AGENT', 48, '다시 촬영해 보셨나요? 기기와 촬영 환경도 알려 주시겠어요?'),
 ('PR_P1_LG_2', 6, 'CUSTOMER', 60, '다시 찍어도 똑같아요. 아이폰이고 조명도 바꾸고 케이스도 빼 봤어요.'),
 ('PR_P1_LG_2', 7, 'AGENT', 72, '언제까지 개설이 필요하신가요?'),
 ('PR_P1_LG_2', 8, 'CUSTOMER', 84, '한 시간째 이래요. 기한은 없어요.'),
 ('PR_P1_LG_2', 9, 'AGENT', 96, '확인해서 전달하겠습니다.'),
 -- PR_P1_LG_3 : 3.신분증촬영반복_3_시연중등록(상담사_박지훈).xlsx
 ('PR_P1_LG_3', 1, 'AGENT', 0, '고객센터 박지훈입니다. 무엇을 도와드릴까요?'),
 ('PR_P1_LG_3', 2, 'CUSTOMER', 12, '아 네 저기 제가 앱에서 계좌를 새로 만들고 있는데요'),
 ('PR_P1_LG_3', 3, 'AGENT', 24, '네, 말씀하세요. 진행 중에 어떤 문제가 있으신가요?'),
 ('PR_P1_LG_3', 4, 'CUSTOMER', 36, '계좌 개설하다가 신분증 촬영이 자꾸 실패했다고 나와요'),
 ('PR_P1_LG_3', 5, 'AGENT', 48, '다른 신분증으로도 해 보셨나요?'),
 ('PR_P1_LG_3', 6, 'CUSTOMER', 60, '면허증으로 바꿔서 해 봐도 마찬가지고 앱을 지웠다 다시 깔았는데도 그래요'),
 ('PR_P1_LG_3', 7, 'AGENT', 72, '알겠습니다. 오늘 안에 꼭 해야 하는 신청인가요?'),
 ('PR_P1_LG_3', 8, 'CUSTOMER', 84, '오늘 안에 해야 하는 건 아니에요'),
 ('PR_P1_LG_3', 9, 'AGENT', 96, '확인해서 전달하겠습니다.');

-- 통화 → 상담사(인사정보) 연결
UPDATE stt_call s SET agent_emp_id = e.emp_id
  FROM employee e
 WHERE s.call_id IN ('PR_P1', 'PR_P1_LG_1', 'PR_P1_LG_2', 'PR_P1_LG_3', 'PR_P1_LG_4') AND e.emp_group = '상담사'
   AND e.emp_name = regexp_replace(s.agent_name, '^상담사\s*', '');
