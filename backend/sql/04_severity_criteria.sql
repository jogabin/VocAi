-- =====================================================================
-- 장애등급 판별기준 (심각도 판별 에이전트가 읽는 기준 정보)
--   severity_grade        : 등급 정의 (P1~P4 의미, 알림 조건, 수신 역할)
--   severity_base_rule    : 오류유형·채널별 기본 등급
--   severity_adjust_rule  : 기본 등급을 올리거나 내리는 조정 규칙
-- 로컬: python scripts/init_db.py 가 자동 실행
-- Cloud SQL: Cloud SQL Studio 에서 01~03 다음에 실행
-- 여러 번 실행해도 기존 데이터는 바뀌지 않습니다.
-- =====================================================================

-- 1) 등급 정의
CREATE TABLE IF NOT EXISTS severity_grade (
    grade_code          VARCHAR(5)   PRIMARY KEY,               -- P1 ~ P4
    grade_name          VARCHAR(20)  NOT NULL,                  -- 긴급 / 높음 / 보통 / 낮음
    grade_order         INTEGER      NOT NULL UNIQUE,           -- 작을수록 심각 (P1 = 1)
    definition          TEXT         NOT NULL,                  -- 등급 정의 (LLM 프롬프트에 사용)
    judge_examples      TEXT,                                   -- 판단 예시 (LLM 프롬프트, 운영자 참고)
    notify_min_reports  INTEGER,                                -- 알림 최소 제보 건수 (NULL = 알림 없음)
    recipient_roles     VARCHAR(50)  NOT NULL DEFAULT '',       -- 수신 역할: '담당,부담당,팀장'
    target_ack_min      INTEGER,                                -- 목표 인지 시간(분) - 조직 기준으로 입력
    target_resolve_min  INTEGER,                                -- 목표 조치 시간(분) - 조직 기준으로 입력
    message_prefix      VARCHAR(50)  NOT NULL DEFAULT '[장애알림]',
    use_yn              BOOLEAN      NOT NULL DEFAULT TRUE,
    valid_from          DATE         NOT NULL DEFAULT CURRENT_DATE,
    valid_to            DATE,
    created_by          VARCHAR(50)  NOT NULL DEFAULT 'system',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_by          VARCHAR(50)  NOT NULL DEFAULT 'system',
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    change_reason       TEXT
);

-- 2) 오류유형·채널별 기본 등급
CREATE TABLE IF NOT EXISTS severity_base_rule (
    rule_id             SERIAL       PRIMARY KEY,
    error_type          VARCHAR(20)  NOT NULL,                  -- 로그인 / 인증 / 조회 / 이체 / UI오류 / 기타
    channel             VARCHAR(20),                            -- 앱 / 웹 / ARS / 기타 (NULL = 전체 채널)
    system_name         VARCHAR(50),                            -- 대상 시스템·업무
    base_grade          VARCHAR(5)   NOT NULL REFERENCES severity_grade(grade_code),
    rationale           TEXT,                                   -- 근거
    use_yn              BOOLEAN      NOT NULL DEFAULT TRUE,
    valid_from          DATE         NOT NULL DEFAULT CURRENT_DATE,
    valid_to            DATE,
    created_by          VARCHAR(50)  NOT NULL DEFAULT 'system',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_by          VARCHAR(50)  NOT NULL DEFAULT 'system',
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    change_reason       TEXT
);
CREATE INDEX IF NOT EXISTS ix_base_rule_type ON severity_base_rule(error_type);

-- 3) 등급 조정 규칙 (apply_order 오름차순으로 적용)
CREATE TABLE IF NOT EXISTS severity_adjust_rule (
    rule_code           VARCHAR(30)  PRIMARY KEY,
    rule_name           VARCHAR(100) NOT NULL,
    rule_type           VARCHAR(20)  NOT NULL
                        CHECK (rule_type IN ('KEYWORD', 'REPORT_COUNT', 'MASS_SIGNAL', 'FALSE_POSITIVE')),
    keywords            TEXT[],                                 -- KEYWORD / FALSE_POSITIVE: 고객 발화에서 찾을 단어
    threshold           INTEGER,                                -- REPORT_COUNT / MASS_SIGNAL: 기준 제보 건수
    action_type         VARCHAR(20)  NOT NULL
                        CHECK (action_type IN ('RAISE', 'SET_GRADE', 'FALSE_POSITIVE')),
    raise_steps         INTEGER,                                -- RAISE: 올릴 단계 수
    target_grade        VARCHAR(5)   REFERENCES severity_grade(grade_code),  -- SET_GRADE / FALSE_POSITIVE: 지정 등급
    condition_grade     VARCHAR(5)   REFERENCES severity_grade(grade_code),  -- 현재 등급이 이 값일 때만 적용 (NULL = 항상)
    target_error_type   VARCHAR(20),                            -- 적용 오류유형 (NULL = 전체)
    apply_order         INTEGER      NOT NULL DEFAULT 100,
    description         TEXT,
    use_yn              BOOLEAN      NOT NULL DEFAULT TRUE,
    valid_from          DATE         NOT NULL DEFAULT CURRENT_DATE,
    valid_to            DATE,
    created_by          VARCHAR(50)  NOT NULL DEFAULT 'system',
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_by          VARCHAR(50)  NOT NULL DEFAULT 'system',
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    change_reason       TEXT
);

-- 4) 장애에 판정 근거 기록
ALTER TABLE incident_alert ADD COLUMN IF NOT EXISTS criteria_version VARCHAR(40);
ALTER TABLE incident_alert ADD COLUMN IF NOT EXISTS applied_rules    JSONB NOT NULL DEFAULT '[]'::jsonb;

-- =====================================================================
-- 초기 데이터 (기존 app/agents/rules.py 기준을 그대로 옮김)
-- =====================================================================
INSERT INTO severity_grade (grade_code, grade_name, grade_order, definition, judge_examples,
                            notify_min_reports, recipient_roles, message_prefix,
                            created_by, updated_by, change_reason) VALUES
 ('P1', '긴급', 1,
  '다수 고객에게 영향을 주거나 금전 피해가 발생하는 장애',
  '동일 오류 3건 이상 동시 제보(대규모 장애 신호), 출금 후 미입금·이중 출금, 전체 고객 로그인 불가',
  1, '담당,부담당,팀장', '[장애알림]', 'system', 'system', '초기 데이터: rules.py 기준 이관'),
 ('P2', '높음', 2,
  '로그인·인증·이체 등 핵심 기능을 사용할 수 없는 장애',
  '특정 OS·앱 버전에서 로그인 실패, 공동인증서 인증 모듈 오류, 타행이체 처리 지연',
  NULL, '담당,부담당', '[장애알림]', 'system', 'system', '초기 데이터: rules.py 기준 이관 (알림 없음 - 알림은 P1만)'),
 ('P3', '보통', 3,
  '일부 기능 지연이나 화면 오류로 불편하지만 우회가 가능한 장애',
  '거래내역 조회 지연, 특정 브라우저에서 버튼 미동작',
  NULL, '담당', '[장애알림]', 'system', 'system', '초기 데이터: rules.py 기준 이관 (알림 없음 - 알림은 P1만)'),
 ('P4', '낮음', 4,
  '영향이 미미하거나 고객 실수·정상 동작으로 보이는 건',
  '비밀번호 5회 오류 잠금, 단순 사용법 문의',
  NULL, '', '[장애알림]', 'system', 'system', '초기 데이터: rules.py 기준 이관 (알림 없음)')
ON CONFLICT (grade_code) DO NOTHING;

-- 장애 알림 대상을 P1 로 한정: 이전 초기 데이터로 만든 DB 의 P2·P3 알림 조건을 비움
-- (판별기준 관리 화면에서 고친 행은 change_reason 이 바뀌므로 건드리지 않음)
UPDATE severity_grade
   SET notify_min_reports = NULL, updated_by = 'system', updated_at = now(),
       change_reason = '초기 데이터: 알림 대상 P1 한정 (P2·P3 알림 없음)'
 WHERE grade_code IN ('P2', 'P3') AND notify_min_reports IS NOT NULL
   AND change_reason LIKE '초기 데이터: rules.py 기준 이관%';

INSERT INTO severity_base_rule (error_type, channel, system_name, base_grade, rationale,
                                created_by, updated_by, change_reason)
SELECT v.error_type, NULL, v.system_name, v.base_grade, v.rationale, 'system', 'system', '초기 데이터: rules.py 기준 이관'
FROM (VALUES
 ('이체',   '이체/송금 시스템',       'P2', '금전 거래 기능. 실패 시 고객 자금에 직접 영향'),
 ('인증',   '공동인증/본인인증 모듈', 'P2', '인증 실패 시 대부분의 거래 진행 불가'),
 ('로그인', '통합인증/로그인 시스템', 'P2', '로그인 실패 시 서비스 전체 이용 불가'),
 ('조회',   '계좌/거래내역 조회',     'P3', '지연은 불편하지만 거래 자체는 가능'),
 ('UI오류', '모바일앱/웹 프론트엔드', 'P3', '특정 화면·브라우저 한정, 우회 가능한 경우가 많음'),
 ('기타',   'IT 서비스데스크',        'P4', '유형 미분류. 추가 제보로 재판정')
) AS v(error_type, system_name, base_grade, rationale)
WHERE NOT EXISTS (SELECT 1 FROM severity_base_rule);

INSERT INTO severity_adjust_rule (rule_code, rule_name, rule_type, keywords, threshold, action_type,
                                  raise_steps, target_grade, condition_grade, apply_order, description,
                                  created_by, updated_by, change_reason) VALUES
 ('ESC_IMPACT', '영향범위 확대 신호', 'KEYWORD',
  ARRAY['돈이 빠져나','돈은 빠져나','출금은 되','이중 출금','이중출금','전체','모든 고객','주변 사람들도','다 안 된','전부 안','아무것도 안'],
  NULL, 'RAISE', 1, NULL, NULL, 10,
  '금전 피해나 다수 고객 영향을 말하면 1단계 상향', 'system', 'system', '초기 데이터: rules.py 기준 이관'),
 ('RPT_MULTI', '복수 제보 시 P4 상향', 'REPORT_COUNT',
  NULL, 2, 'SET_GRADE', NULL, 'P3', 'P4', 20,
  '같은 장애로 2건 이상 제보되면 P4를 P3로 올림', 'system', 'system', '초기 데이터: rules.py 기준 이관'),
 ('MASS_P1', '대규모 장애 신호', 'MASS_SIGNAL',
  NULL, 3, 'SET_GRADE', NULL, 'P1', NULL, 30,
  '60분 내 같은 장애 제보가 기준 건수 이상이면 P1. 기준 건수는 중복통합 에이전트도 사용', 'system', 'system', '초기 데이터: rules.py 기준 이관'),
 ('FP_CUSTOMER', '고객 귀책 오탐', 'FALSE_POSITIVE',
  ARRAY['비밀번호를 몇 번 틀','비밀번호 틀','잊어버','잠겼','재설정','5회 오류'],
  NULL, 'FALSE_POSITIVE', NULL, 'P4', NULL, 90,
  '과거 오탐 사례와 유사하고 고객 귀책 단어가 있으면 P4로 내리고 알림 제외 (대규모 신호면 적용 안 함)', 'system', 'system', '초기 데이터: rules.py 기준 이관')
ON CONFLICT (rule_code) DO NOTHING;
