-- =====================================================================
-- 10. 영향 기반 판별 보강 · 개선의견 분리
--   - 판별기준: P1 정의(기한 임박 + 대체수단 없음 + 지속 차단) · P2/P3 정의 보강
--   - 조정 규칙: 지속 차단(최소 P2) · 기한 임박(P1) · 정상 진행(최대 P3), 조치 유형 RAISE_TO / LOWER_TO 추가
--   - 대규모 장애 신호는 제보 건수가 아니라 독립 고객 수로 판단 (incident_alert.customer_count)
--   - 개선의견(improvement_opinion): 해결·완료된 건에 대한 문구·안내·절차 개선 요청. 알림·누적 대상 아님
--   여러 번 실행해도 안전합니다. 09_auth_roles.sql 이후에 실행하세요.
-- =====================================================================

-- 1) 조정 규칙 조치 유형: RAISE_TO(최소 등급) / LOWER_TO(최대 등급, 대규모 신호면 적용 안 함)
ALTER TABLE severity_adjust_rule DROP CONSTRAINT IF EXISTS severity_adjust_rule_action_type_check;
ALTER TABLE severity_adjust_rule ADD CONSTRAINT severity_adjust_rule_action_type_check
    CHECK (action_type IN ('RAISE', 'SET_GRADE', 'RAISE_TO', 'LOWER_TO', 'FALSE_POSITIVE'));

-- 2) 등급 정의 보강 (판별기준 관리 화면에서 고치지 않은 초기 데이터만)
UPDATE severity_grade SET
       definition = '여러 고객의 핵심 거래가 계속 막히거나 금전 피해가 발생하는 장애, 또는 지급 기한이 임박했는데 대체수단 없이 거래가 계속 막혀 중대한 피해가 예상되는 장애',
       judge_examples = '독립 고객 3명 이상 동일 증상 지속(대규모 장애 신호), 출금 후 미입금·이중 출금, 계약금 지급 마감 10분 전 앱·인터넷뱅킹 모두 이체 불가',
       updated_by = 'system', updated_at = now(), change_reason = '초기 데이터: 영향 기반 판별 보강'
 WHERE grade_code = 'P1' AND change_reason LIKE '초기 데이터%';
UPDATE severity_grade SET
       definition = '재시도 후에도 업무 진행이 계속 막히지만 기한 임박·중대한 피해·대체수단 없음·다수 고객 등 P1 조건은 확인되지 않은 장애',
       judge_examples = '신분증 촬영 후 같은 화면 반복, 인증서 수수료 출금 후 미발급, 신청 화면 항목 선택 불가',
       updated_by = 'system', updated_at = now(), change_reason = '초기 데이터: 영향 기반 판별 보강'
 WHERE grade_code = 'P2' AND change_reason LIKE '초기 데이터%';
UPDATE severity_grade SET
       definition = '일시 실패 후 정상 진행됐거나 영향이 제한적인 건',
       judge_examples = '신분증 인식 지연 후 재촬영으로 진행, ARS 인증 통화 끊김 후 재인증 완료, 화면 지연 후 재접속으로 접수 완료',
       updated_by = 'system', updated_at = now(), change_reason = '초기 데이터: 영향 기반 판별 보강'
 WHERE grade_code = 'P3' AND change_reason LIKE '초기 데이터%';
UPDATE severity_grade SET
       definition = '영향이 미미하거나 고객 실수·정상 동작으로 보이는 건 (해결된 건의 문구·절차 개선 요청은 개선의견으로 별도 기록)',
       updated_by = 'system', updated_at = now(), change_reason = '초기 데이터: 영향 기반 판별 보강'
 WHERE grade_code = 'P4' AND change_reason LIKE '초기 데이터%';
UPDATE severity_adjust_rule SET
       rule_name = '대규모 장애 신호',
       description = '60분 내 같은 장애를 겪은 독립 고객 수가 기준 이상이면 P1 (같은 고객의 재문의·중복 등록은 1명). 기준 수는 중복통합 에이전트도 사용',
       updated_by = 'system', updated_at = now(), change_reason = '초기 데이터: 독립 고객 수 기준'
 WHERE rule_code = 'MASS_P1' AND change_reason LIKE '초기 데이터%';

-- 3) 영향 기반 조정 규칙
INSERT INTO severity_adjust_rule (rule_code, rule_name, rule_type, keywords, threshold, action_type,
                                  raise_steps, target_grade, condition_grade, apply_order, description,
                                  created_by, updated_by, change_reason) VALUES
 ('PERSIST_P2', '지속 차단', 'KEYWORD',
  ARRAY['지웠다 다시 깔','다시 깔았','껐다 켰는데','캐시도 지우고','다시 켜도 똑같','다시 켜도 같','다시 해도 똑같','다시 해도 안','계속 그래요','지금도 같은','두 번 했는데 똑같','다시 발급하려고 해도 오류'],
  NULL, 'RAISE_TO', NULL, 'P2', NULL, 5,
  '재시도·재설치 후에도 같은 오류로 업무 진행이 막히면 최소 P2', 'system', 'system', '초기 데이터: 영향 기반 판별 보강'),
 ('URGENT_P1', '기한 임박·대체수단 없음·지속 차단', 'KEYWORD',
  ARRAY['기한:분 남았','기한:까지 보내야','기한:까지 이체해야','기한:까지 입금해야','기한:시까지 보내','기한:마감이 얼마 안','대체수단:다른 계좌도 없','대체수단:다른 방법도 없','대체수단:인터넷뱅킹도 같은','대체수단:인터넷뱅킹도 안','대체수단:대신 보낼 수 없','대체수단:다른 은행 계좌도 없','지속:계속 오류','지속:다시 켜도 똑같','지속:다시 해도 똑같','지속:다시 해도 안','지속:계속 실패','지속:똑같아요'],
  NULL, 'RAISE_TO', NULL, 'P1', NULL, 15,
  '기한·대체수단·지속 그룹 단어가 모두 확인되면 단일 고객이어도 P1 (그룹:단어 형식, 그룹마다 하나 이상)', 'system', 'system', '초기 데이터: 영향 기반 판별 보강'),
 ('RECOVERED_P3', '일시 실패 후 정상 진행', 'KEYWORD',
  ARRAY['이번에는 됐','이제 열려','지금은 됐','넘어갔어요','완료라고 나와','완료됐다고 나와','접수 완료라고','등록 완료라고'],
  NULL, 'LOWER_TO', NULL, 'P3', NULL, 25,
  '재시도 후 정상 진행·완료가 확인되면 최대 P3 (대규모 장애 신호면 적용 안 함)', 'system', 'system', '초기 데이터: 영향 기반 판별 보강')
ON CONFLICT (rule_code) DO NOTHING;

-- 4) 장애의 독립 고객 수
ALTER TABLE incident_alert ADD COLUMN IF NOT EXISTS customer_count INTEGER NOT NULL DEFAULT 1;

-- 5) 개선의견
CREATE TABLE IF NOT EXISTS improvement_opinion (
    improvement_id      BIGSERIAL PRIMARY KEY,
    consult_id          BIGINT       NOT NULL REFERENCES consult_history(consult_id) ON DELETE CASCADE,
    call_id             VARCHAR(30),
    customer_id         VARCHAR(30)  NOT NULL,
    customer_name       VARCHAR(50),
    error_type          VARCHAR(20),
    channel             VARCHAR(20),
    title               VARCHAR(200) NOT NULL,
    content             TEXT         NOT NULL,                  -- 상담요약
    customer_excerpt    TEXT,                                   -- 고객 발화
    related_incident_id BIGINT REFERENCES incident_alert(incident_id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_improvement_created ON improvement_opinion(created_at DESC);
