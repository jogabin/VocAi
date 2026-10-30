-- =====================================================================
-- 시연용 시드 데이터 (여러 번 실행해도 중복 생성되지 않음)
--   상담현황 통화 3건 (시나리오 검증자료의 STT 원문, 모두 가상 상담)
--   · CALL-0001 이체(출금 후 미입금)          : 이체 기본 P2 + 금전 피해 신호 → P1
--   · CALL-0006 인증(회사 직원 PC 전부 오류)  : 인증 기본 P2 → 관찰
--   · CALL-0011 이체(지급 기한 임박, 대체수단 없음) : P1
--   등급별 시연 통화(DEMO-*)는 11_demo_scripts.sql 에 있습니다.
--   시연을 다시 하려면 DB 초기화: python scripts/init_db.py --reset (배포 환경은 DB_RESET_TOKEN 변경)
-- =====================================================================

-- ---------- STT 통화 ----------
INSERT INTO stt_call (call_id, customer_id, customer_name, agent_name, inbound_channel, started_at, duration_sec) VALUES
 ('CALL-0001', 'CUST-10231', '김민수', '상담사 이수진', '콜센터', now() - interval '52 minutes', 214),
 ('CALL-0006', 'CUST-61733', '한지민', '상담사 정하나', '콜센터', now() - interval '29 minutes', 262),
 ('CALL-0011', 'CUST-71001', '한도윤', '상담사 이수진', '콜센터', now() - interval '3 minutes', 144)
ON CONFLICT (call_id) DO NOTHING;

-- ---------- STT 원문 ----------
INSERT INTO stt_utterance (call_id, seq, speaker, offset_sec, text) VALUES
 -- CALL-0001 : [P2→P1] 타행이체 출금 후 미입금 (이체 기본 P2 + 금전 피해 신호 → P1)
 ('CALL-0001', 1, 'AGENT',    0,  '안녕하세요, 고객센터 이수진입니다. 무엇을 도와드릴까요?'),
 ('CALL-0001', 2, 'CUSTOMER', 5,  '앱에서 타행으로 이체를 했는데 이십 분째 처리중으로만 나오고 완료가 안 돼요.'),
 ('CALL-0001', 3, 'AGENT',    14, '불편을 드려 죄송합니다. 이체하신 금액과 시간 확인 부탁드립니다.'),
 ('CALL-0001', 4, 'CUSTOMER', 20, '오후 두 시쯤 삼백만 원 보냈어요. 돈은 빠져나갔는데 상대방은 못 받았대요. 갤럭시 S24 안드로이드 앱이에요.'),
 ('CALL-0001', 5, 'AGENT',    34, '출금 후 미입금 건으로 확인됩니다. 전산 부서에 긴급으로 전달하겠습니다.'),

 -- CALL-0006 : [P2 관찰] 공동인증서 인증 모듈 오류 (인증 기본 P2 → 관찰)
 ('CALL-0006', 1, 'AGENT',    0,  '안녕하세요, 고객센터 정하나입니다.'),
 ('CALL-0006', 2, 'CUSTOMER', 4,  '인터넷뱅킹에서 공동인증서로 인증하려는데 인증서 오류가 나면서 진행이 안 돼요.'),
 ('CALL-0006', 3, 'AGENT',    14, '오류 코드가 표시되나요?'),
 ('CALL-0006', 4, 'CUSTOMER', 18, '인증 모듈 오류 코드 E-1203 이라고 나와요. 윈도우 11 PC고 엣지 브라우저예요.'),
 ('CALL-0006', 5, 'AGENT',    30, '다른 PC에서도 같은 증상인지 확인 가능하실까요?'),
 ('CALL-0006', 6, 'CUSTOMER', 35, '회사 직원들 PC에서도 전부 안 된다고 해요. 급여 이체를 해야 하는데 아무것도 안 돼요.'),
 ('CALL-0006', 7, 'AGENT',    46, '다수 고객 영향으로 보여 인증 오류로 접수하고 전산 부서에 바로 전달하겠습니다.'),

 -- CALL-0011 : [P1] 지급 기한이 임박한 이체 불가 (인터넷뱅킹도 같은 오류, 대체 계좌 없음)
 ('CALL-0011', 1,  'AGENT',    0,   '안녕하세요 고객센터 이수진입니다 무엇을 도와드릴까요'),
 ('CALL-0011', 2,  'CUSTOMER', 12,  '아 네 저 지금 이체를 해야 되는데요 앱에서 계속 오류가 나요'),
 ('CALL-0011', 3,  'AGENT',    24,  '네 고객님 확인을 위해 성함과 생년월일 말씀 부탁드립니다'),
 ('CALL-0011', 4,  'CUSTOMER', 36,  '한도윤이고요 구십 년 삼월 이일이요'),
 ('CALL-0011', 5,  'AGENT',    48,  '네 확인 감사합니다 어느 단계에서 어떤 문구가 나오나요'),
 ('CALL-0011', 6,  'CUSTOMER', 60,  '어 그게 계좌이체 화면이고 마지막 확인을 누르면 일시적으로 서비스를 이용할 수 없습니다 라고 나와요 앱을 다시 켜도 똑같아요'),
 ('CALL-0011', 7,  'AGENT',    72,  '핸드폰 기종이 어떻게 되시나요?'),
 ('CALL-0011', 8,  'CUSTOMER', 84,  '아이폰 프로 17이에요.'),
 ('CALL-0011', 9,  'AGENT',    96,  '언제까지 보내셔야 하는 거래인가요 인터넷뱅킹이나 다른 계좌로 대신 보내실 수 있을까요'),
 ('CALL-0011', 10, 'CUSTOMER', 108, '오늘 세 시까지 계약금을 보내야 하는데 십 분 남았어요 늦으면 계약이 취소될 수 있어요 인터넷뱅킹도 같은 오류고 지금 쓸 수 있는 다른 계좌도 없어요'),
 ('CALL-0011', 11, 'AGENT',    120, '이체가 계속 막히고 지급 기한이 임박한 상황을 긴급 건으로 전달하겠습니다 확인된 처리 상황을 안내드리겠습니다'),
 ('CALL-0011', 12, 'CUSTOMER', 132, '네 빨리 좀 부탁드려요')
ON CONFLICT (call_id, seq) DO NOTHING;

-- ---------- 업무담당자 ----------
INSERT INTO biz_owner (error_type, system_name, owner_name, dept, role, messenger_id, phone, on_duty)
SELECT * FROM (VALUES
 ('로그인', '통합인증/로그인 시스템', '김도윤', '디지털채널개발팀', '담당',   '8913038773',   '010-1111-0001', TRUE),
 ('로그인', '통합인증/로그인 시스템', '이서준', '디지털채널개발팀', '부담당', '8913038773',  '010-1111-0002', TRUE),
 ('로그인', '통합인증/로그인 시스템', '박지성', '디지털채널개발팀', '팀장',   '8913038773', '010-1111-0003', TRUE),
 ('인증',   '공동인증/본인인증 모듈', '최유나', '보안인증운영팀',   '담당',   '8913038773',   '010-2222-0001', TRUE),
 ('인증',   '공동인증/본인인증 모듈', '정우성', '보안인증운영팀',   '팀장',   '8913038773','010-2222-0002', TRUE),
 ('조회',   '계좌/거래내역 조회',     '한소희', '코어뱅킹운영팀',   '담당',   '8913038773',   '010-3333-0001', TRUE),
 ('조회',   '계좌/거래내역 조회',     '오세훈', '코어뱅킹운영팀',   '팀장',   '8913038773',   '010-3333-0002', TRUE),
 ('이체',   '이체/송금 시스템',       '윤아름', '지급결제운영팀',   '담당',   '8913038773',  '010-4444-0001', TRUE),
 ('이체',   '이체/송금 시스템',       '장민호', '지급결제운영팀',   '팀장',   '8913038773',  '010-4444-0002', TRUE),
 ('UI오류', '모바일앱/웹 프론트엔드', '서지우', 'UX개발팀',         '담당',   '8913038773',   '010-5555-0001', TRUE),
 ('UI오류', '모바일앱/웹 프론트엔드', '문가영', 'UX개발팀',         '팀장',   '8913038773','010-5555-0002', TRUE),
 ('기타',   'IT 서비스데스크',        '배수현', 'IT운영지원팀',     '담당',   '8913038773', '010-6666-0001', TRUE)
) AS v(error_type, system_name, owner_name, dept, role, messenger_id, phone, on_duty)
WHERE NOT EXISTS (SELECT 1 FROM biz_owner);

-- ---------- 과거 장애 이력 (RAG 지식베이스) ----------
INSERT INTO incident_alert (title, error_type, channel, severity, status, report_count, symptoms, env_info,
                            analysis, owner_id, notified_severity, resolution,
                            first_reported_at, last_reported_at, resolved_at, created_at, updated_at)
SELECT v.title, v.error_type, v.channel, v.severity, v.status, v.report_count, v.symptoms, v.env_info::jsonb,
       v.analysis, (SELECT owner_id FROM biz_owner o WHERE o.error_type = v.error_type AND o.role = '담당' LIMIT 1),
       v.severity, v.resolution, v.ts, v.ts + interval '20 minutes', v.ts + interval '3 hours', v.ts, v.ts + interval '3 hours'
FROM (VALUES
 ('[앱] iOS 앱 업데이트 후 로그인 실패', '로그인', '앱', 'P1', '해결', 14,
  '앱 업데이트 후 로그인 시 일시적인 오류 메시지 발생, 로그인 화면으로 반복 복귀',
  '{"os":"iOS","app_version":"5.1.2","device":"아이폰"}',
  '신규 버전 배포 직후 iOS 단말에서만 발생',
  '원인: 5.1.2 배포 시 iOS 토큰 갱신(refresh token) 로직 오류. 조치: 서버측 토큰 검증 완화 후 5.1.3 핫픽스 배포.',
  now() - interval '62 days'),
 ('[앱] 비밀번호 오류 잠금 문의', '로그인', '앱', 'P4', '오탐', 1,
  '비밀번호 5회 오류로 로그인 잠금, 고객이 비밀번호를 잊어버림',
  '{"os":"Android"}',
  '고객 비밀번호 입력 오류로 인한 정상 잠금',
  '오탐: 시스템 장애 아님. 비밀번호 재설정 안내로 종결. (비밀번호 틀림/잠김/재설정 문의는 장애 알림 제외)',
  now() - interval '40 days'),
 ('[앱] 타행이체 처리중 지연', '이체', '앱', 'P1', '해결', 9,
  '타행 이체 후 처리중 상태 지속, 출금은 되었으나 수취인 미입금',
  '{"os":"Android"}',
  '대외기관(금융결제원) 연계 구간 응답 지연',
  '원인: 대외기관 회선 지연으로 타행이체 전문 타임아웃. 조치: 회선 절체 후 미처리 전문 재전송, 고객 입금 완료 확인.',
  now() - interval '25 days'),
 ('[웹] 공동인증서 인증 모듈 오류', '인증', '웹', 'P2', '해결', 4,
  '인터넷뱅킹 공동인증서 인증 시 인증 모듈 오류 코드 표시, 진행 불가',
  '{"os":"Windows","device":"PC"}',
  '인증 모듈 서버 인증서 만료 의심',
  '원인: 인증 모듈 서버 인증서 만료. 조치: 인증서 갱신 및 모듈 재기동.',
  now() - interval '18 days'),
 ('[웹] 크롬 브라우저 버튼 미동작', 'UI오류', '웹', 'P3', '해결', 3,
  'PC 크롬에서 신청 화면 다음 버튼 클릭 시 반응 없음, 화면 멈춤',
  '{"os":"Windows","device":"PC","browser":"Chrome"}',
  '브라우저 업데이트 이후 스크립트 호환성 문제',
  '원인: 크롬 최신 버전에서 deprecated API 사용으로 JS 오류. 조치: 프론트엔드 스크립트 수정 배포.',
  now() - interval '9 days')
) AS v(title, error_type, channel, severity, status, report_count, symptoms, env_info, analysis, resolution, ts)
WHERE NOT EXISTS (SELECT 1 FROM incident_alert);
