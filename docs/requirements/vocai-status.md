# 요건 대비 구현 현황 (VocAi)

상태: 확인 대기
근거: 요건 문서(scope.md, requirements.md, tabs/*)와 구현된 코드(커밋 fba80ab)를 맞대어 읽었습니다. 그 뒤 커밋 e5e0d5d ~ 160f999에서 바뀐 부분은 아래 0-04, 0-09, 0-12, 0-13, 1-01, 1-06, 2-23, 4-08 행과 6장만 다시 읽어 고쳤고, 나머지 행은 다시 읽지 않았습니다. 앱을 실행해 확인한 것은 아닙니다. 사람이 읽고 확인한 것도 아닙니다.

## 1. 읽는 법

- 요건 문서는 팀이 정한 목표 기준선이고, 이 문서는 제출 코드가 그 가운데 무엇을 하는지 보여 줍니다. 요건 번호는 requirements.md와 tabs/의 번호를 그대로 썼고 모두 93개입니다(공통 28, 탭 1~7 65).
- 상태 말뜻: `구현`(요건대로 동작하는 코드가 있음) / `부분`(일부만 있거나 모양이 다름, 무엇이 다른지 한 줄 적음) / `다름`(같은 목적이지만 다른 방식) / `향후 과제`(코드에서 찾지 못함, 이번 제출 범위 밖: [ADR-011](../adr/ADR-011-future-work-scope.md)) / `확인 못 함`(코드만으로 판단할 수 없음).
- 요건에 적힌 항목이 하나라도 빠졌으면 `부분`으로 두었습니다. 문구나 한계값만 다른 것은 `구현`으로 두고 비고에 적었습니다.
- `근거`의 경로는 저장소 맨 위 폴더 기준입니다. 역할 이름은 요건 쪽 이름을 썼고, VocAi의 권한 이름과의 대응은 2장에 있습니다.

## 2. 화면 대응표

요건의 탭 7개와 VocAi 화면의 대응입니다. 메뉴의 화면 번호(SCR-xx)는 `frontend/src/App.vue`의 `MENUS`에 적힌 것입니다.

| 요건 탭 | VocAi 화면 | 경로 | 파일 | 관계 |
|---|---|---|---|---|
| 1 상담등록 | SCR-02 상담현황 + SCR-03 상담이력등록 (메뉴에는 숨김, 상담현황에서 상담을 눌러 들어감) | `#/stt`, `#/consult?call=` | `frontend/src/views/ConsultStatusView.vue`, `ConsultRegisterView.vue`, `components/voc/AgentGraph.vue`, `AgentTimeline.vue`, `ChatTranscript.vue` | 1:2 |
| 2 장애승인 | SCR-04 장애 알림 모니터 + SCR-05 장애 상세정보 (센터관리자·시스템관리자에게만 보이는 수동 알림·종결 패널) | `#/monitor`, `#/incident?id=` | `frontend/src/views/IncidentMonitorView.vue`, `IncidentDetailView.vue` | 1:2, 탭 3과 같은 화면을 씀 |
| 3 장애처리 | 위와 같은 두 화면 (IT담당자에게만 보이는 처리 등록 패널) | `#/monitor`, `#/incident?id=` | `IncidentMonitorView.vue`, `IncidentDetailView.vue` | 탭 2·3 : 화면 2 (N:1) |
| 4 판별기준관리 | SCR-08 판별기준 관리 | `#/criteria` | `frontend/src/views/CriteriaView.vue` | 1:1 |
| 5 담당자관리 | SCR-06 사용자관리 + SCR-07 인사정보 관리 (메뉴의 '시스템관리' 묶음) | `#/users`, `#/employees` | `frontend/src/views/UserAdminView.vue`, `EmployeeView.vue` | 1:2 |
| 6 시험상담등록 | SCR-09 고객정보 관리 + SCR-10 상담데이터 등록 (같은 '시스템관리' 묶음) | `#/customers`, `#/consult-data` | `frontend/src/views/CustomerView.vue`, `ConsultDataView.vue` | 1:2 |
| 7 성과측정 | 대응하는 화면 없음 | - | - | 없음 |

요건에 없는 VocAi 화면입니다.

| VocAi 화면 | 경로 | 파일 | 요건 쪽 관련 |
|---|---|---|---|
| SCR-11 개선의견 목록 | `#/improvements` | `frontend/src/views/ImprovementView.vue` | 0-20은 개선 의견을 기록까지만 하라고 해서 보는 화면은 요건에 없음 |
| 로그인 | (로그인 전 모든 주소) | `frontend/src/views/LoginView.vue` | 공통 0-01 |
| API 테스트 | `#/api-test` (메뉴에는 숨김, 시스템관리자) | `frontend/src/views/ApiTestView.vue` | 없음 |

요건의 역할과 VocAi 권한(`auth_role`)의 대응입니다. 한 사용자에게 권한이 하나만 붙습니다.

| 요건의 역할 | VocAi 권한 | 쓸 수 있는 화면 (`App.vue`의 `MENUS`, `backend/app/services/auth.py`) |
|---|---|---|
| 상담사 | 상담사 | 상담현황, 상담이력등록, 장애 알림 모니터와 상세(처리 등록은 못 함), 개선의견 목록 |
| 상담사관리자 | 센터관리자 | 상담사와 같은 화면 + 장애 상세에서 관찰 장애 수동 알림·종결 |
| IT 담당자 | IT담당자 | 장애 알림 모니터와 상세(처리 등록), 개선의견 목록. 상담현황·판별기준은 못 씀 |
| 관리자 | 시스템관리자 | 모든 화면. 장애 처리 등록은 못 함 |

## 3. 한눈에 요약

| 구분 | 구현 | 부분 | 다름 | 향후 과제 | 확인 못 함 | 합계 |
|---|---|---|---|---|---|---|
| 공통 0-xx | 3 | 19 | 2 | 3 | 1 | 28 |
| 탭 1 상담등록 | 5 | 5 | 0 | 4 | 0 | 14 |
| 탭 2 장애승인 | 3 | 13 | 0 | 2 | 0 | 18 |
| 탭 3 장애처리 | 2 | 5 | 1 | 0 | 0 | 8 |
| 탭 4 판별기준관리 | 1 | 4 | 0 | 3 | 0 | 8 |
| 탭 5 담당자관리 | 0 | 5 | 0 | 1 | 0 | 6 |
| 탭 6 시험상담등록 | 2 | 3 | 1 | 1 | 0 | 7 |
| 탭 7 성과측정 | 0 | 2 | 0 | 2 | 0 | 4 |
| 합계 | 16 | 56 | 4 | 16 | 1 | 93 |

총평입니다.

- 93개 가운데 76개는 코드에 대응하는 기능이 있습니다: 요건대로 동작하는 것 16개, 핵심 흐름은 동작하고 세부 항목이 빠진 것 56개, 같은 목적을 다른 방식으로 구현한 것 4개입니다. 16개는 향후 과제([5장](#5-향후-과제))이고 1개는 확인 못 했습니다.
- 상담이력 등록 → AI 판단(장애 감지, 같은 장애 묶기, 등급, 오탐 대조) → 알림 → 처리 결과를 다음 판단에 쓰는 흐름은 LangGraph로 구현돼 있고, 진행 단계를 그림으로 보여 주는 화면도 있습니다.
- 향후 과제는 성과측정의 정답 비교와 지금 방식 비교(7-01, 7-03), 시험 상담 정답(6-03), 텔레그램 고객 대화(1-12~1-13, 1-15), 고객 안내 기록(1-10), 장애 다시 열기(0-24), 'AI 판단 실패' 처리(0-23), 화면 권한 설정(5-06), 판별 기준 기록 보기·되돌리기와 LLM 고르기(4-04, 4-06), 사람이 바로잡은 판단 모으기(4-08), 장애 내용 고치기(2-20), 목록 정렬(2-23), 세 칸 화면(0-26)입니다.
- 구조가 다른 곳은 다음과 같습니다. 탭 2·3이 장애 알림 모니터와 장애 상세 두 화면에 합쳐져 있습니다. P2·P3 승인 대신 '관찰' 등급(기본값은 P2)을 센터관리자가 수동으로 알리거나 종결하고, P3·P4는 '미대상'으로 자동 종결됩니다. 개선 의견은 P4가 아니라 별도 목록에 기록합니다. 사용자관리와 인사정보가 나뉘어 있고, 한 사용자에게 역할이 하나이며 화면 권한은 코드에 고정돼 있습니다.

## 4. 탭별 상세 표

### 4-0. 공통 요건 (0-xx)

| 요건 번호 | 요건 한 줄 요약 | 상태 | VocAi에서는 | 근거 |
|---|---|---|---|---|
| 0-01 | 자기 계정으로 로그인, 계정 네 개, 회원가입 없음, 처음 비밀번호 변경 | 부분 | 로그인 화면과 계정별 권한이 있고 회원가입은 없으며 관리자가 계정을 만듭니다. 시드 계정은 3개(admin, user01, user: 관리자, 상담사, IT 담당자)라 요건의 user, user1, user2와 일부 아이디가 다르고 상담사관리자 계정은 없습니다. 처음 비밀번호를 바꾸게 하는 처리는 없습니다(0-25). | `frontend/src/views/LoginView.vue`, `backend/app/routers/auth_api.py` (`login`), `backend/sql/05_users_hr.sql`, `backend/app/routers/admin_api.py` (`create_user`) |
| 0-02 | 화면 권한에서 켜진 탭의 일만 함, 역할 넷, 역할 여러 개 | 다름 | 권한(상담사, 센터관리자, IT담당자, 시스템관리자)마다 쓸 수 있는 화면이 코드에 고정돼 있습니다. 화면 권한을 켜고 끄는 기능이 없고 한 사용자에게 권한이 하나만 붙습니다. 처리 등록은 IT담당자만, 수동 알림·종결은 센터관리자·시스템관리자만 합니다. | `frontend/src/App.vue` (`MENUS`의 `roles`), `frontend/src/composables/useAuth.js`, `backend/app/services/auth.py` (`require_roles`, `is_it_staff`), `backend/sql/09_auth_roles.sql` |
| 0-03 | 상담이력과 대화 원문을 읽고 장애인지 판단, 규칙과 AI가 다르면 '판단 갈림' | 부분 | 대화 원문 분석과 상담이력 분석을 따로 한 뒤 하나라도 장애면 장애로 보고, 장애도 개선의견도 아니면 `장애 아님 → END`로 끝냅니다. 신호어 사전(규칙)과 LLM을 함께 쓰지만 LLM 응답이 오면 규칙 결과를 덮어쓰고 '판단 갈림' 표시는 남기지 않습니다. 신호어 사전은 화면에서 못 고칩니다. | `backend/app/agents/detection.py` (`analyze_stt`, `analyze_consult`, `_combine`, `run`), `backend/app/agents/graph.py` (`route_after_detect`), `backend/app/agents/rules.py` (`ISSUE_SIGNALS`) |
| 0-04 | 원인이 업무 규칙이어도 장애로 기록, 상담사가 확인한 고객 쪽 잘못은 넘기지 않음 | 부분 | 원인과 상관없이 등급 기준으로 처리하고 LLM 지시문에 원인을 단정하지 말라는 문구가 있습니다. 상담 결과에 '고객 쪽 잘못으로 확인'을 적는 칸이 없어(완료, 이관, 보류뿐) 그 건을 넘기지 않는 규칙이 없습니다. 대신 고객 발화에 고객 귀책 단어가 있고 과거 오탐 사례와 비슷하면 AI가 오탐으로 뺍니다(0-13). 장애 감지 보강으로, 비슷한 유형 상담의 처리 결과가 고객 입력 오류·상품 조건·오탐이면 P1에서 빼고 등급 상한을 P4로 둡니다(LLM을 쓸 때만, 유형 상담 자료는 초안). | `backend/app/agents/severity.py` (`SYSTEM_TMPL`, 2차 오탐 대조), `frontend/src/views/ConsultRegisterView.vue` (`RESULTS`), `backend/app/agents/p1_flow.py` |
| 0-05 | 장애 내용 정리(오류 유형, 채널, 발생 단계, 오류 문구, 기존 조치, 거래 영향, 기한, 대체수단, 원인), 출처 구분 | 부분 | 오류 유형(6종), 채널, 제목, 증상, 재현 정보(OS, 기기, 앱 버전, 브라우저, 오류 코드, 오류 문구, 발생 시점)와 '초기 분석'(추정 원인, 점검 포인트)을 남깁니다. 발생 단계, 기존 조치, 거래 영향, 기한, 대체수단은 항목으로 나눠 적지 않고, 고객이 말한 것, 상담사가 확인한 것, 확인 안 됨을 구분해 적지도 않습니다. | `backend/app/agents/detection.py`, `backend/app/agents/rules.py` (`extract_env`), `backend/app/agents/severity.py` (`_rule_analysis`), `frontend/src/views/IncidentDetailView.vue` ('장애 정보' 카드) |
| 0-06 | 같은 장애 제보 묶기(최근 1시간 + 1시간 밖 미처리, 기준 점수는 탭 4에서 관리) | 부분 | 같은 오류 유형의 열린 장애 가운데 마지막 제보가 60분 안인 것과 증상 유사도(문자 bigram), 채널·환경 가산점으로 비교해 0.30 이상이면 묶습니다. 60분이 지난 미처리 장애는 비교하지 않습니다. 기준 점수(0.30, 증상 최소 0.20)는 코드 상수이고 시간 창은 환경 설정값(`DEDUP_WINDOW_MIN`)이라 화면에서 못 고칩니다. | `backend/app/agents/dedup.py` (`MERGE_THRESHOLD`, `_score`, `run`), `backend/app/services/repo.py` (`find_open_incidents`), `backend/app/database.py` (`dedup_window_min`) |
| 0-07 | 같은 고객의 재문의는 같은 장애에 연결하되 영향받은 고객 수에는 세지 않음 | 구현 | 같은 장애에 묶인 상담은 연결하고 영향받은 고객 수(`customer_count`)는 고객번호 기준으로 중복 없이 셉니다. 제보 건수(`report_count`)에는 재문의도 들어갑니다. | `backend/app/agents/dedup.py` (`run`), `backend/app/services/repo.py` (`count_incident_customers`) |
| 0-08 | 서로 다른 고객 3명이 모이면 대규모 장애 신호로 표시, 그것만으로 P1로 올리지 않음 | 부분 | 60분 안에 독립 고객이 기준(기본 3명, 판별기준 화면에서 수정) 이상이면 대규모 장애 신호로 표시하고 모니터의 '동일유형 장애'에 셉니다. 요건과 달리 이 신호가 있으면 등급을 P1로 지정하는 규칙(MASS_P1)이 있고 LLM 판단보다 우선합니다. | `backend/app/agents/dedup.py`, `backend/app/agents/severity.py` (`mass_signal` 분기), `backend/sql/04_severity_criteria.sql` (`MASS_P1`), `frontend/src/views/IncidentMonitorView.vue` |
| 0-09 | 장애마다 P1~P4 등급과 판단 근거(적용한 기준, 기준 버전) | 구현 | 장애에 등급, 기준 버전(`criteria_version`), 적용한 규칙 코드(`applied_rules`)를 저장하고 상세 화면에 보입니다. 판단 문장은 상담이력 화면의 실행 타임라인에서 볼 수 있고, 등록 직후에는 판별 결과 팝업에서도 근거를 봅니다. 비고: 등급 이름은 긴급, 높음, 보통, 낮음이고 판별기준 화면에서 바꿉니다. | `backend/app/agents/severity.py` (`reasons`, `applied`), `backend/app/agents/notify.py` (`register`), `frontend/src/views/IncidentDetailView.vue` ('판정 근거'), `frontend/src/components/voc/RunResultModal.vue` |
| 0-10 | P1 기준 셋(긴급 거래 차단, 여러 고객 핵심 기능 불가, 기존 장애 영향 확대), 기한은 수치 없이 AI가 근거 | 부분 | 첫째는 기한, 대체수단, 지속 차단 단어 그룹이 모두 있으면 P1로 올리는 키워드 규칙(URGENT_P1)과 LLM 판단으로 구현돼 있습니다. 둘째는 독립 고객 3명 신호(MASS_P1)로 올립니다. 셋째는 통합된 기존 장애보다 등급이 낮아지지 않게 하는 것과 영향범위 확대 단어 때문에 1단계 올리는 것뿐입니다. 기준 문장은 화면에서 고치고 기한을 수치로 정하지 않습니다. 막힌 거래가 핵심 거래인지는 따로 보지 않고, 기한의 근거를 알림·상세에 따로 보이는 항목도 없습니다. | `backend/sql/10_impact_improvement.sql` (`URGENT_P1`, `PERSIST_P2`), `backend/sql/04_severity_criteria.sql`, `backend/app/agents/severity.py` |
| 0-11 | P1이 아니면 P2~P4 기준 | 구현 | 등급 정의 문장(P2는 재시도 후에도 계속 막힘, P3는 일시 실패 후 정상 진행, P4는 영향 미미·고객 실수)과 조정 규칙(PERSIST_P2 최소 P2, RECOVERED_P3 최대 P3)으로 나누고 판별기준 화면에서 고칩니다. | `backend/sql/10_impact_improvement.sql`, `frontend/src/views/CriteriaView.vue` |
| 0-12 | 새 제보가 묶이면 등급 재판단, 업무 조건 건은 1시간 안 서로 다른 고객 3명이면 한 단계 올림, 같은 미해결 오류만 셈, 등급은 내리지 않음 | 부분 | 새 제보가 묶일 때마다 판단을 다시 하고 기존 등급보다 낮아지지 않습니다. 되풀이 상향은 '업무 조건으로 보이는 건'을 따로 가르지 않고, 누적 제보 2건이면 P4를 P3로 올리는 규칙(RPT_MULTI) 하나뿐입니다. 같은 고객의 재문의도 건수에 들어가고 P3에서 P2로 올리는 규칙은 없습니다. 해결·오탐으로 닫힌 장애에는 묶이지 않아 세지 않고, 상담사가 통화 중 해결했다고 AI(LLM)가 판단한 건도 미해결 독립 고객 집계에서 뺍니다. 원인 확정에 따른 제외는 없습니다. 개선의견은 세지 않습니다. | `backend/app/agents/severity.py` (`_apply_adjust_rules`), `backend/app/agents/dedup.py`, `backend/app/services/repo.py` (`find_open_incidents`), `backend/sql/04_severity_criteria.sql` (`RPT_MULTI`), `backend/app/agents/p1_flow.py` |
| 0-13 | 과거 오탐과 비슷하고 지금 위험이 없으면 오탐으로 판별해 알림에서 뺌, 근거를 남기고 'IT 담당자가 바로잡음' | 부분 | 알림 대상(P1)으로 판정된 건만 과거 오탐 사례와 비교합니다. 비슷함 점수가 기준 이상이고 고객 발화에 고객 귀책 단어(오탐 규칙의 단어 목록)가 있으며 대규모 신호가 아닐 때 '오탐' 상태로 등록하고 알림을 뺍니다. 적용 규칙과 비슷한 사례를 상세에 보이고, IT담당자가 상태를 바꿔 바로잡습니다. 지금 위험이 없는지를 따로 다시 판단하지 않고, 비슷함 점수 기준(문자열 유사도는 코드 상수 0.25, 임베딩은 환경 설정값 0.60)은 화면에서 못 고칩니다. 이와 별개로 장애 감지 단계에서 비슷한 유형 상담이 오탐 계열이면 P1에서 빼는 판정이 앞서 있습니다(0-04). | `backend/app/agents/severity.py` (2차 대조), `backend/app/agents/notify.py` (`register`), `backend/app/database.py` (`rag_fp_similarity`), `frontend/src/views/IncidentDetailView.vue` |
| 0-14 | P1은 승인 없이 IT 담당자에게 알림(업무 분장, 담당·부담당·팀장, '업무 담당 미배정' 표시, 모의 알림함) | 부분 | P1(알림 최소 제보 1건)은 승인 없이 바로 보냅니다. 받는 사람은 담당 오류 유형이 맞는 근무 중 IT담당자 가운데 등급별 수신 역할(P1은 담당, 부담당, 팀장)에 해당하는 사람입니다. 업무(상품, 서비스) 기준 분장과 '업무 담당 미배정' 표시는 없고 담당을 못 찾으면 '기타' 유형 담당으로 대체합니다. 알림은 설정한 방식(시스템 안 기록, 텔레그램, 웹훅)으로 가고 사용자별 알림함은 없습니다. 센터관리자에게 P1을 따로 알리지 않습니다. | `backend/app/agents/notify.py` (`primary_recipients`, `run`), `backend/app/services/messenger.py`, `backend/sql/04_severity_criteria.sql` |
| 0-15 | P2·P3는 상담사관리자가 승인하면 알림, P4는 기록만, 고쳐서 승인·반려, 과거 반려 사례와 비슷하면 목록에서 뺌 | 다름 | 기본 설정은 P2만 '관찰'로 등록하고, 센터관리자·시스템관리자가 장애 상세에서 등급, 수신자, 제목·본문을 고쳐 보내거나 알림 없이 종결(미대상, 오탐)합니다. P3·P4는 '미대상'으로 자동 종결되고(센터관리자가 나중에 수동으로 알리는 것은 가능), P4를 기록만 하는 목록은 따로 없습니다. 반려 사유는 종결 사유로 남지만 반려 사례를 다음 판단에 쓰지 않습니다. 관찰 여부는 등급 정의에서 바꿉니다. | `backend/sql/13_observe_manual_notify.sql`, `backend/app/routers/voc_api.py` (`manual_notify`, `close_incident`), `frontend/src/views/IncidentDetailView.vue` |
| 0-16 | 알림에 담을 내용(등급, 증상, 발생 단계·오류 문구, 거래 영향·기한·대체수단, 고객 수, 판단 근거, 원인으로 보이는 것, 과거 사례, 상세 연결) | 부분 | 알림 본문에 등급, 증상, 재현 정보(오류 코드·문구 포함), 누적 제보와 독립 고객 수, 초기 분석(추정 원인), 과거 해결 사례, 수신자(1차·2차), 장애 상세 링크를 담습니다. 거래 영향·기한·대체수단과 등급 판단 근거 항목은 없고, 확인되지 않은 것은 '확인 안 됨' 대신 '-'로 보입니다. | `backend/app/agents/notify.py` (`compose`) |
| 0-17 | 이미 알렸으면 다시 알리지 않음, 등급이 오르거나 새 위험이 확인되면 다시 알림 | 부분 | 마지막으로 알린 등급(`notified_severity`)보다 현재 등급이 같거나 낮으면 중복 발송을 생략하고, 등급이 오르면 '[등급 상향 A→B]' 머리말과 변경 근거를 붙여 다시 보냅니다. 등급 말고 '새 위험'을 따로 판단하지는 않습니다. | `backend/app/agents/notify.py` (`run`) |
| 0-18 | 알릴 담당자를 못 찾거나 못 보내면 표시 | 부분 | 전송 실패는 알림 기록에 FAILED로 남고 상세의 '메신저 전송 정보'에 '실패'로 보입니다(실패 이유는 DB에만 있고 화면에는 안 나옵니다). 담당자를 못 찾은 경우는 표시가 없고, 실행 타임라인 메시지에 '1차 없음'만 남으며 알림을 보낸 것으로 기록(`notified_severity`)됩니다. | `backend/app/services/messenger.py` (`send_message`), `backend/app/agents/notify.py` (`run`), `frontend/src/views/IncidentDetailView.vue` |
| 0-19 | 처리가 끝난 장애의 결과를 다음 판단의 과거 사례로 씀(검수 없이 바로, 판단 전에 등록된 것만) | 부분 | 처리완료·오탐으로 등록한 장애는 검수 없이 바로 유사 사례 검색(기본은 문자열 유사도, 설정하면 임베딩), LLM 프롬프트, 2차 수신자 선택에 쓰입니다. '미대상' 종결은 쓰지 않습니다. 판단 시점 이후에 등록된 결과를 빼는 제한은 없어 상담을 재실행하면 나중 결과가 섞일 수 있습니다. | `backend/app/services/repo.py` (`search_knowledge`), `backend/app/agents/severity.py` (`_similar_cases`), `backend/app/routers/voc_api.py` (`_embed_incident`) |
| 0-20 | 개선 의견이면 P4로 기록, 장애에 딸린 것은 연결, 되풀이돼도 등급을 올리지 않음 | 부분 | 개선 의견은 장애 등급 P4가 아니라 별도 테이블과 목록에 기록합니다. 비슷한 최근 장애(30일, 오탐 제외)가 있으면 그 장애에 연결하고, 장애 등급과 누적 건수에는 영향이 없습니다. | `backend/app/agents/improve.py`, `backend/sql/10_impact_improvement.sql` (`improvement_opinion`), `frontend/src/views/ImprovementView.vue` |
| 0-21 | 단계마다 시각을 남김(등록, 판단, 등급, 승인 요청, 승인·반려, 알림, 담당 확인, 첫 회신, 첫 안내) | 부분 | 상담이력 등록(`created_at`), 에이전트 단계별 시작·종료(`agent_step`), 알림 발송(`sent_at`), 처리 상태 변경(`incident_action.created_at`), 처리 완료(`resolved_at`) 시각이 남습니다. 승인 요청, 승인·반려, 담당 확인, 첫 회신, 첫 고객 안내를 구분한 시각은 없습니다. | `backend/app/services/repo.py` (`start_step`, `add_action`), `backend/sql/01_schema.sql`, `backend/sql/07_incident_process.sql` |
| 0-22 | 상담, 고객, 담당자는 모두 가상, 실제 사례는 유형으로 바꿔 씀 | 확인 못 함 | 시드의 고객, 직원, 연락처는 만든 값으로 보이고 실제 데이터를 가져오는 코드는 없습니다. 다만 시연 원문이 실제 사례나 실제 상품 이름에서 왔는지는 코드로 판단할 수 없습니다. | `backend/sql/05_users_hr.sql`, `backend/sql/08_customer_consult_data.sql`, `backend/sql/11_demo_scripts.sql`, `backend/app/history_seed.py` |
| 0-23 | 등급을 못 정하면 승인 목록에 'AI 판단 실패'로 올림 | 향후 과제 | LLM 호출이 실패하거나 키가 없으면 규칙 기반 결과로 이어 갑니다. 그래프 실행 자체가 실패하면 실행 이력(`agent_run`)만 FAILED로 남고 장애나 확인 목록에는 올라가지 않습니다. | `backend/app/agents/llm.py` (`ask_json`), `backend/app/agents/pipeline.py` (`execute`) |
| 0-24 | 조치 완료된 장애에 새 상담이 묶이면 다시 열어 '접수'로 되돌림 | 향후 과제 | 해결·오탐으로 닫힌 장애는 묶음 후보에서 빠집니다. 같은 증상으로 다시 문의하면 새 장애로 등록되고 이전 장애는 과거 해결 사례로만 참조됩니다. | `backend/app/services/repo.py` (`find_open_incidents`), `backend/app/agents/dedup.py` |
| 0-25 | 처음 비밀번호로 로그인하면 새 비밀번호를 먼저 정함, 영문+숫자 8자 이상, 초기화하면 기존 로그인 종료 | 부분 | 비밀번호 규칙(영문과 숫자 포함 8자 이상)과 초기화·사용 중지 때 기존 로그인 종료는 있습니다. 처음 비밀번호과 첫 로그인 때 변경 강제는 없고 관리자가 비밀번호를 직접 입력합니다. 본인 비밀번호 변경은 API(`POST /api/auth/password`)만 있고 화면은 없습니다. | `backend/app/services/auth.py` (`check_password_rule`, `revoke_user_sessions`), `backend/app/routers/admin_api.py` (`update_user`), `backend/app/routers/auth_api.py` (`change_password`), `frontend/src/api/authApi.js` |
| 0-26 | 탭 1~3에서 목록, 내용, AI 판단 세 칸을 한 화면에 두고 크기 조절 | 향후 과제 | 목록 화면에서 행을 눌러 상세 화면으로 이동하는 방식이고, 상세는 2열(장애 정보, 처리·이력)입니다. 세 칸 배치와 칸 크기 조절은 없습니다. AI와 대화하는 칸도 없습니다. | `frontend/src/views/ConsultStatusView.vue`, `frontend/src/views/IncidentDetailView.vue` (`.grid-detail`), `frontend/src/views/ConsultRegisterView.vue` (`.grid-2`) |
| 0-27 | 텔레그램을 고객 역할과 직원 알림에 씀, 토큰은 설정값으로만, 보낸 결과와 이유를 화면에서 봄 | 부분 | 직원 알림은 텔레그램 봇으로 보내고 토큰은 환경 설정값(`TELEGRAM_BOT_TOKEN`)으로만 받습니다. 알림 방식 설정(`MESSENGER_PROVIDER`)을 비워 두면 시스템 안 기록(MOCK) 방식으로 동작하고, 방식만 텔레그램으로 두고 토큰이 없으면 전송이 실패로 기록됩니다. 보낸 결과(SENT, FAILED)와 오류 문구는 DB에 남지만 화면에는 결과만 보입니다. 봇이 받은 말을 상담으로 만드는 코드(고객 역할)는 없고, 봇이 받은 대화 목록을 조회하는 기능(chat_id 찾기)만 있습니다. | `backend/app/services/messenger.py`, `backend/app/routers/voc_api.py` (`telegram_chats`), `backend/app/database.py` |
| 0-28 | 화면 위쪽에서 AI 사용 상태와 텔레그램 연결 상태를 봄 | 부분 | 장애 알림 모니터 화면 위쪽에 'LLM 공급자·모델' 또는 '규칙 기반 모드', RAG 방식, 메신저 방식(MOCK, WEBHOOK, TELEGRAM) 배지를 보입니다. 다른 화면에는 없고, 'AI 키가 없어 판단이 실패함'이나 텔레그램 '연결됨, 연결 실패' 상태는 없습니다(설정한 방식만 보입니다). | `frontend/src/views/IncidentMonitorView.vue`, `backend/app/routers/voc_api.py` (`monitor_summary`) |

### 4-1. 탭 1 상담등록

| 요건 번호 | 요건 한 줄 요약 | 상태 | VocAi에서는 | 근거 |
|---|---|---|---|---|
| 1-01 | 이력을 등록할 상담을 목록에서 찾음(상담번호, 일시, 고객, 채널, 상태, 진행 먼저, 기간, 검색, 자동 갱신) | 부분 | 상담현황에서 진행·상담완료를 구분하고 진행을 먼저 보이며, 조회 기간(기본 최근 7일), 검색(고객명, 통화 ID, 고객번호, 대화 내용), 5초 자동 갱신, 열 머리글 정렬(오름차순·내림차순), 15건씩 페이지 이동이 있습니다. 채널 열은 없고 텔레그램 상담은 목록에 없습니다. | `frontend/src/views/ConsultStatusView.vue`, `backend/app/routers/voc_api.py` (`list_stt`), `backend/app/services/repo.py` (`list_stt_calls`) |
| 1-02 | 대화 원문을 보면서 상담이력을 씀 | 구현 | 상담이력등록 화면 왼쪽에 대화 원문(말풍선), 오른쪽에 상담이력 입력 칸이 함께 있습니다. | `frontend/src/views/ConsultRegisterView.vue`, `frontend/src/components/voc/ChatTranscript.vue` |
| 1-03 | 상담이력 등록(유형, 채널, 결과, 요약), 결과에 '고객 쪽 잘못으로 확인' | 부분 | 상담 유형(전산오류문의, 일반문의, 불만, 기타), 채널(앱, 웹, ARS, 기타), 요약을 적고 고객 정보는 통화에 붙은 값으로 고정됩니다. 상담 결과는 완료, 이관, 보류뿐이라 '고객 쪽 잘못으로 확인'이 없고 그 건을 넘기지 않는 처리도 없습니다. | `frontend/src/views/ConsultRegisterView.vue`, `backend/app/routers/voc_api.py` (`ConsultIn`, `create_consult`) |
| 1-04 | 한 상담의 이력은 한 번만 등록, 재문의는 새 상담 | 구현 | 이미 상담완료된 통화는 409로 막고 화면은 조회 전용으로 바뀝니다. 재문의는 새 통화(상담)로 등록해야 합니다. | `backend/app/routers/voc_api.py` (`create_consult`), `frontend/src/views/ConsultRegisterView.vue` (`isDone`) |
| 1-05 | 상담이력을 등록하면 AI 판단 시작 | 구현 | 등록 응답 뒤 백그라운드로 LangGraph 에이전트를 실행합니다. | `backend/app/routers/voc_api.py` (`create_consult`), `backend/app/agents/pipeline.py`, `backend/app/agents/graph.py` |
| 1-06 | AI 판단 진행 단계를 바뀌는 대로 보고 끝나면 결과를 한 줄로 봄 | 부분 | 에이전트 단계(장애감지, 중복제보 통합, 심각도 판별, 메신저 전송 또는 장애이력 등록 또는 개선의견 등록)가 1초 간격으로 갱신돼 그래프와 타임라인에 보이고 단계마다 결과 메시지가 남습니다. 요건의 '결과 한 줄'은 마지막 단계 메시지와, 실행이 끝나면 열리는 판별 결과 팝업(등급, 알림 여부와 이후 처리, 근거)으로 대신하며 '승인 대기' 결과는 없고(관찰, 미대상으로 표시), 단계 이름도 요건과 다릅니다. 끝난 뒤 장애 상세로 가는 버튼이 있습니다. | `frontend/src/views/ConsultRegisterView.vue` (`pollRun`), `frontend/src/components/voc/AgentTimeline.vue`, `backend/app/agents/graph.py` (`NODES`), `frontend/src/components/voc/RunResultModal.vue` |
| 1-08 | AI가 대화 원문으로 상담 요약 초안을 만들고 상담사가 고쳐 씀 | 구현 | '상담요약 초안 작성' 버튼(상담 화면을 열 때 한 번 자동 실행)이 상담사 관점의 [문의] [확인] [처리] 3줄을 만들고, AI 초안임을 안내 문구로 알립니다. 지시문에 대화에 없는 내용을 추측하지 말라고 적혀 있습니다. 비고: LLM을 못 쓰면 규칙 기반 초안이고 그렇게 안내합니다. | `backend/app/agents/summary.py`, `backend/app/routers/voc_api.py` (`summary_draft`), `frontend/src/views/ConsultRegisterView.vue` (`draftSummary`) |
| 1-09 | 묶인 장애의 처리 상태, 회신, 확정 원인, 고객 최종 해결, 고객 안내 기록을 봄, '확인 안 됨' 표기 | 부분 | 등록 뒤 '장애 ERR-xxxx 상세 보기' 버튼으로 장애 상세(등급, 처리 상태, 처리 이력)로 이동해 볼 수 있습니다. 탭 1 안에서 보는 영역은 없고, 확정 원인, 고객 최종 해결, 고객 안내 기록과 '확인 안 됨' 표기 규칙은 없습니다. | `frontend/src/views/ConsultRegisterView.vue` (`run-foot` 버튼), `frontend/src/views/IncidentDetailView.vue` |
| 1-10 | 고객에게 안내한 기록을 남김(고객, 방법, 일시, 내용, 쌓기) | 향후 과제 | 고객 안내 기록을 입력하거나 저장하는 화면, API, 테이블이 없습니다. | `backend/app/routers/voc_api.py`, `backend/sql/*.sql` (해당 항목 없음) |
| 1-11 | 상담 중 진행 중인 장애를 찾아봄(나중) | 부분 | 장애 알림 모니터(모든 권한)에서 건수 박스와 조회 기간으로 장애 목록을 볼 수 있습니다. 오류 유형, 채널, 증상으로 찾는 검색은 없고 상담 화면 안에서 찾는 기능도 없습니다. | `frontend/src/views/IncidentMonitorView.vue` |
| 1-12~1-13 | 텔레그램으로 온 말이 진행 중 상담이 됨, 상담사가 화면에서 답함 | 향후 과제 | 봇이 받은 메시지를 상담이나 고객으로 등록하는 코드와 상담사 답장 입력이 없습니다. 봇이 받은 대화 목록을 조회하는 기능(chat_id 찾기)만 있습니다. | `backend/app/services/messenger.py` (`telegram_chats`만 있음), `frontend/src/views/ConsultRegisterView.vue` (답장 입력 없음) |
| 1-14 | AI 판단 진행을 단계 그림으로 봄(지나간, 지금, 가지 않은 단계) | 구현 | LangGraph 구조와 같은 흐름도에서 지나간 단계(초록), 지금 단계(깜빡임), 가지 않은 단계(점선)를 구분하고 장애가 아니면 END로 끝나는 경로를 보입니다. 비고: 오른쪽 AI 칸이 아니라 상담이력등록 화면 아래쪽 카드에 있습니다. | `frontend/src/components/voc/AgentGraph.vue`, `frontend/src/views/ConsultRegisterView.vue` |
| 1-15 | 텔레그램 고객에게 고객 안내를 그 자리에서 보냄 | 향후 과제 | 고객 안내 기록(1-10)이 없고 텔레그램으로 안내를 보내는 기능도 없습니다. | `backend/app/services/messenger.py` (직원 알림 전송만 있음) |

### 4-2. 탭 2 장애승인

| 요건 번호 | 요건 한 줄 요약 | 상태 | VocAi에서는 | 근거 |
|---|---|---|---|---|
| 2-01 | 모든 장애를 급한 것부터 봄('AI 판단 실패'는 맨 앞) | 부분 | 장애 알림 모니터의 '장애 정보 등록' 박스 목록에 상태와 관계없이 모든 장애(오탐, 미대상 포함)가 보입니다. 정렬은 등급 순이 아니라 최근 제보 순이고 'AI 판단 실패'는 없습니다. 개선 의견은 이 목록에 없습니다. | `frontend/src/views/IncidentMonitorView.vue`, `backend/app/services/repo.py` (`list_incidents`) |
| 2-02 | 목록에서 장애 번호, 등급, 증상 요약, 오류 유형, 고객 수, 대규모 신호, 승인 상태, 처리 상태, 담당, 처음 들어온 시각, 처리 날짜를 앎 | 부분 | 장애번호, 등급, 처리상태, 제목, 오류유형·채널, 누적 제보·고객 수·'동일유형 다발' 표시, 담당자, 메신저 전송 건수, 최근 제보(경과 시간)가 보입니다. 증상 요약(제목으로 대신), 승인 상태, 처음 들어온 시각, 처리 날짜 열은 없습니다. | `frontend/src/views/IncidentMonitorView.vue` (목록 표) |
| 2-03 | 처리하지 않은 P1과 대규모 신호 장애를 따로 모아 봄(나중) | 구현 | '긴급 장애'(최상위 등급, 미처리)와 '동일유형 장애'(대규모 신호) 박스를 누르면 해당 장애만 모아 보입니다. | `frontend/src/views/IncidentMonitorView.vue` (`BOXES`), `backend/app/services/repo.py` (`BOX_SQL`) |
| 2-04 | 장애 건수를 한눈에 봄(박스, 조회 기간, 박스를 누르면 목록, 미처리 P1은 눈에 띄게) | 구현 | 건수 박스 6개(장애 정보 등록, 긴급 장애, 관찰(확인 대기), 메신저 알림 전송, 동일유형 장애, 장애 처리 완료), 조회 기간 선택, 박스 클릭 시 목록 전환, 긴급 장애가 있으면 깜빡임, 3초 자동 새로고침이 있습니다. 비고: 요건의 '승인 대기'는 '관찰(확인 대기)' 박스입니다. | `frontend/src/views/IncidentMonitorView.vue`, `backend/app/routers/voc_api.py` (`monitor_counts`) |
| 2-06 | 장애 하나의 상세(내용, 등급·근거, 묶인 상담·고객 수·요약, 발생 현황, 예상 영향 범위, 과거 사례, 오탐 근거, 승인·알림·처리·등급 고침·내용 고침·고객 안내 기록) | 부분 | 장애 정보(오류 유형, 채널, 등급, 알림 발송 등급, 누적 제보, 담당자, 처리자, 증상, 재현 정보), 판정 근거(기준 버전, 적용 규칙 코드), 초기 분석, 과거 유사 사례, 제보 상담(요약), 처리 이력, 메신저 전송 정보(받은 사람, 시각, 성공·실패, 본문)가 있습니다. 영향받은 고객 수, 예상 영향 범위, 늘어나는 추이, 승인 기록 영역, 확정한 원인, 장애 내용 고친 기록, 고객 안내 기록은 없고 '확인 안 됨' 표기도 없습니다. 등급 변경은 처리 이력 문구로만 남습니다. | `frontend/src/views/IncidentDetailView.vue` |
| 2-08 | AI가 오탐으로 판별한 기록을 지우지 않고 다음 판단의 과거 오탐 사례로 씀 | 구현 | 오탐으로 판별한 장애는 '오탐' 상태로 목록에 남고, 상세에서 적용 규칙과 과거 유사 사례를 볼 수 있으며, 다음 판단의 2차 오탐 대조에 쓰입니다. | `backend/app/agents/notify.py` (`register`), `backend/app/services/repo.py` (`search_knowledge`), `backend/app/agents/severity.py` |
| 2-12 | 승인을 기다리는 P2·P3와 'AI 판단 실패'를 모아 봄(급한 것부터) | 부분 | '관찰(확인 대기)' 박스가 알림 미대상 관찰 장애(기본값은 P2)를 모아 보여 줍니다. P3는 기본이 미대상 자동 종결이라 올라오지 않고 'AI 판단 실패'도 없으며 정렬은 급한 순이 아닙니다. 오탐은 올라오지 않습니다. | `frontend/src/views/IncidentMonitorView.vue` (`observing`), `backend/sql/13_observe_manual_notify.sql` |
| 2-13 | 승인 전에 판단에 필요한 내용(오류 내용, 발생 현황, 고객 영향, 등급 근거, 알림 발송안)을 봄 | 부분 | 장애 상세에서 오류 내용, 누적 제보, 판정 근거, 초기 분석, 유사 사례를 보고, 같은 화면의 수동 알림 패널에서 알림 발송안(추천 수신자 1차·2차, 자동 작성한 메시지)을 봅니다. 고객 영향(거래 불가, 예상 영향 범위)과 늘어나는 추이는 없습니다. | `frontend/src/views/IncidentDetailView.vue`, `backend/app/routers/voc_api.py` (`manual_notify_preview`), `backend/app/agents/notify.py` (`manual_draft`) |
| 2-14 | 등급과 알림 내용을 고친 뒤 승인(AI 처음 판단과 함께 남김, P4로 고치면 기록만) | 부분 | 센터관리자·시스템관리자가 관찰·미대상 장애에서 알림 등급, 수신자(1차·2차), 제목·본문을 고쳐 'IT담당자 알림 전송 → 대기중'을 누르면 알림이 가고, 등급 변경과 메모가 처리 이력에 남습니다. '승인'이라는 단계 이름은 없고 이미 알림이 나간 장애에는 쓸 수 없으며, 처음 등급은 처리 이력 문구에만 남고 P4로 고치면 기록만 하는 규칙은 없습니다. | `frontend/src/views/IncidentDetailView.vue` (`sendManual`), `backend/app/routers/voc_api.py` (`manual_notify`) |
| 2-15 | 알릴 필요 없는 장애를 반려(이유 필수, 반려 사례를 다음 판단에 씀) | 부분 | '알림 없이 종결'(미대상 또는 오탐)이 반려에 해당하고 종결 사유(2자 이상)를 꼭 적어야 하며 처리 이력에 남습니다. 반려 사례를 다음 판단에 쓰고 비슷한 건을 확인 목록에서 빼는 처리는 없습니다(미대상은 과거 사례로 쓰지 않고, 오탐으로 종결한 건만 과거 오탐 사례로 씁니다). | `backend/app/routers/voc_api.py` (`close_incident`), `backend/sql/13_observe_manual_notify.sql` |
| 2-16 | 승인하면 알림(받는 사람·내용 수정, 모의 알림함, 누가 언제 승인했는지 남김) | 부분 | 알림을 보낼 때 추천 수신자를 고치고 메시지를 고쳐 보내며, 누가 언제 보냈는지는 처리 이력(처리자, 시각)에 남습니다. 알림은 설정한 방식(시스템 안 기록, 텔레그램, 웹훅)으로 갑니다. 요건의 사용자별 모의 알림함은 없고(3-10), 「승인」이라는 단계 이름 대신 「수동 알림 전송」입니다. | `backend/app/routers/voc_api.py` (`manual_notify`), `backend/app/services/messenger.py` |
| 2-17 | 승인 대기 중 장애가 바뀌면 바로 반영(P1로 오르면 바로 알림, 알린 장애가 오르면 다시 승인 목록) | 부분 | 새 제보가 묶이면 등급을 다시 판단하고, P1로 오르면 승인 없이 바로 알리며 관찰·미대상 장애는 '접수'로 바뀌어 확인 대기 박스에서 빠집니다. 미대상이던 장애가 관찰 등급으로 오르면 다시 관찰로 엽니다. 이미 알린 장애의 등급이 올랐을 때 다시 확인 목록에 올리는 처리는 없습니다. | `backend/app/agents/notify.py` (`register`), `backend/app/agents/dedup.py` |
| 2-18 | 'AI 판단 실패' 장애를 AI로 다시 판단시킴(나중) | 부분 | 시스템관리자가 상담이력등록 화면의 '재실행' 버튼으로 상담 하나에 대해 에이전트를 다시 돌립니다. 장애 상세에서 다시 판단시키는 기능과 'AI 판단 실패' 상태는 없습니다. | `frontend/src/views/ConsultRegisterView.vue` (`rerun`), `backend/app/routers/voc_api.py` (`rerun`) |
| 2-19 | 장애 등급을 언제든 이유를 적고 고침(고친 등급대로 알림, 내려도 다시 알리지 않음) | 부분 | 등급은 관찰·미대상 장애에 수동 알림을 보낼 때만 화면에서 고칠 수 있고(이유는 선택 메모) 알린 장애의 등급을 언제든 고치는 화면은 없습니다. `PATCH /api/incidents/{id}`에 등급 필드가 있지만 화면에서 쓰지 않습니다. | `frontend/src/views/IncidentDetailView.vue`, `backend/app/routers/voc_api.py` (`manual_notify`, `update_incident`) |
| 2-20 | IT 담당자와 상담사관리자가 AI가 정리한 장애 내용을 고침(나중) | 향후 과제 | 장애 내용을 고치는 화면과 고친 기록이 없습니다. | `frontend/src/views/IncidentDetailView.vue` (읽기만 있음) |
| 2-22 | 목록을 승인 대기, 처리한 것, 자동 처리된 P1, 전체로 나눠 봄 | 부분 | 건수 박스로 목록을 나눠 봅니다(전체, 긴급, 관찰, 메신저 알림 전송, 동일유형, 처리 완료). 요건의 '처리한 것(승인·반려)'과 '자동 처리된 P1' 구분은 없습니다. | `frontend/src/views/IncidentMonitorView.vue`, `backend/app/services/repo.py` (`BOX_SQL`) |
| 2-23 | 목록을 등록 날짜와 처리 날짜로 오름차순·내림차순 정렬 | 향후 과제 | 장애 알림 모니터 목록에는 표 머리를 눌러 정렬하는 기능이 없고 최근 제보 순으로 고정돼 있습니다(상담현황 목록에는 열 정렬이 있습니다). | `frontend/src/views/IncidentMonitorView.vue`, `backend/app/services/repo.py` (`list_incidents`) |
| 2-24 | 장애 상세의 묶인 상담에서 그 상담(대화 원문)으로 감 | 부분 | 제보 상담 표의 행을 누르면 상담이력등록 화면(대화 원문)이 열립니다. 표에는 상담 번호, 등록 시각, 고객, 상담사, 요약이 보입니다. 요건과 다른 점: 상담 화면 권한이 없는 IT담당자는 누르면 권한 안내 화면이 나옵니다(요건은 연결 자체를 숨기라고 함). | `frontend/src/views/IncidentDetailView.vue` (제보 상담 표), `frontend/src/App.vue` |

### 4-3. 탭 3 장애처리

| 요건 번호 | 요건 한 줄 요약 | 상태 | VocAi에서는 | 근거 |
|---|---|---|---|---|
| 3-08 | 처리 상태와 처리 내용 등록(접수, 확인 중, 조치 완료, 오탐, 고객 최종 해결, 원인 확정, 다시 열기) | 부분 | IT담당자만 장애 상세에서 처리 상태(대기중, 진행중, 오탐, 처리완료)와 처리 내용을 등록하고 등록할 때마다 처리 이력이 쌓입니다. 처리완료·오탐은 처리 내용이 필수이고 등록한 결과는 바로 과거 사례로 씁니다. 고객 최종 해결, 원인 확정(프로그램, 업무 조건, 고객 쪽), 다시 열기 전용 상태는 없지만 처리 등록에서 대기중·진행중으로 되돌릴 수는 있고, 상태 이름도 요건과 다릅니다. 시스템관리자는 처리 등록을 못 합니다. | `frontend/src/views/IncidentDetailView.vue` (`submit`), `backend/app/routers/voc_api.py` (`add_incident_action`), `backend/app/services/repo.py` (`PROCESS_TO_STATUS`) |
| 3-09 | AI의 오탐 판별을 바로잡음(바로잡으면 등급에 따라 다시 알림) | 부분 | 오탐 장애에서 IT담당자가 처리 상태를 다른 값으로 바꾸면 바로잡힙니다. 바로잡은 뒤 등급에 따라 다시 알리는 처리는 없습니다. | `backend/app/routers/voc_api.py` (`add_incident_action`), `frontend/src/views/IncidentDetailView.vue` |
| 3-10 | 자기에게 온 알림을 시스템 안의 모의 알림함에서 봄 | 다름 | 사용자별 알림함 화면이 없습니다. 알림 제목, 본문, 상세 링크와 수신자, 시각, 성공 여부는 장애 상세의 '메신저 전송 정보'에 장애별로 남습니다. | `frontend/src/views/IncidentDetailView.vue` ('메신저 전송 정보'), `backend/app/services/repo.py` (`list_messenger_logs`) |
| 3-11 | IT에 넘어온 장애와 오탐 장애를 급한 것부터 봄 | 부분 | IT 담당자 전용 목록은 없고 모든 권한이 같은 장애 알림 모니터 목록을 봅니다. 승인 대기, 반려, P4를 빼는 처리나 오탐만 모아 보는 박스는 없습니다. | `frontend/src/views/IncidentMonitorView.vue` |
| 3-12 | 장애 상세를 탭 2와 같은 내용으로 봄 | 구현 | 모든 권한이 같은 상세 화면을 같은 내용으로 보고, 권한에 따라 쓰기 패널(IT담당자는 처리 등록, 센터관리자는 수동 알림·종결)만 달라집니다. | `frontend/src/views/IncidentDetailView.vue` |
| 3-13 | 자기 몫의 건수를 한눈에 봄(안 본 알림, 처리 중, P1, 오탐, 처리 끝) | 부분 | 모니터 박스는 전체 장애 기준이라 내 몫이 아닙니다. 긴급(최상위 등급 미처리)과 처리 완료 건수는 있고, '아직 안 본 알림', '처리 중인 장애', '오탐으로 판별된 건' 박스는 없습니다. | `frontend/src/views/IncidentMonitorView.vue`, `backend/app/services/repo.py` (`monitor_counts`) |
| 3-14 | 알림을 텔레그램으로도 받음(못 보내도 알림함에는 들어오고 이유가 남음) | 부분 | 알림 방식을 텔레그램으로 설정하면 담당자 정보의 메신저 ID(chat_id)로 같은 본문을 보내고, 못 보내도 알림 기록(FAILED, 오류 문구)이 남습니다. 오류 문구는 화면에 나오지 않고, 요건의 「알림함에는 들어옴」은 모의 알림함이 없어 해당하지 않습니다(3-10). | `backend/app/services/messenger.py` (`send_message`), `frontend/src/views/EmployeeView.vue` |
| 3-15 | 비슷한 과거 장애를 처리한 사람에게도 알림(1차·2차 표시, 중복 없음) | 구현 | 유사 사례 중 해결된 장애의 처리자(근무 중, 메신저 ID 있음, 1차와 중복 제외)를 2차 수신자로 더하고 알림 기록에 1차·2차로 표시합니다. 비고: '최대 2명' 제한은 없고 유사 사례 최대 3건에서 나옵니다. | `backend/app/agents/notify.py` (`secondary_recipients`), `backend/app/services/repo.py` (`past_resolvers`) |

### 4-4. 탭 4 판별기준관리

| 요건 번호 | 요건 한 줄 요약 | 상태 | VocAi에서는 | 근거 |
|---|---|---|---|---|
| 4-01 | AI가 지금 쓰는 판별 기준 전체와 기준 버전을 봄 | 부분 | 등급 정의(정의, 판단 예시, 알림 기준, 관찰 여부, 수신 역할, 목표 시간, 머리말), 기본 등급 규칙(오류 유형·채널별), 조정 규칙(키워드, 제보 건수, 대규모 신호, 오탐, 적용 순서, 켜기·끄기)과 기준 버전을 봅니다. 대규모 신호 기준(독립 고객 3명)과 오탐 단어 목록은 보이지만 같은 장애 묶기 기준 점수, 오탐 기준 점수, 장애 표현 목록은 코드나 환경 설정값이라 화면에 없습니다. | `frontend/src/views/CriteriaView.vue`, `backend/app/services/criteria.py`, `backend/sql/04_severity_criteria.sql` |
| 4-02 | 기준의 문장과 수치를 고침(이유 필수, 누가 언제 무엇을 고쳤는지 남김) | 부분 | 등급 정의 문장, 건수, 단어 목록, 알림 조건 등을 고칠 수 있고, 수정 창에서는 변경 사유를 꼭 입력하게 하고 등록과 규칙 스위치 조작에서는 선택입니다(서버는 강제하지 않음). 마지막 수정자와 시각이 표에 보이지만 이전 내용은 덮어써서 무엇을 고쳤는지의 이력은 남지 않습니다. | `frontend/src/views/CriteriaView.vue` (`validate`), `backend/app/services/criteria.py` (`_write`) |
| 4-03 | 고친 기준은 다음 판단부터 씀(판단 근거에 판 번호 남김) | 구현 | 저장하면 5초 안에 다음 판단부터 적용되고, 이미 판단한 장애는 다시 판단하지 않으며, 장애에는 판단 때 쓴 기준 버전과 규칙 코드가 남습니다. | `backend/app/services/criteria.py` (`load`, `invalidate`), `backend/app/agents/severity.py` |
| 4-04 | 기준을 고친 기록을 보고 이전 판으로 되돌림 | 향후 과제 | 기준 이력 테이블, 화면, 되돌리기가 없습니다. 수정은 행을 그대로 갱신합니다. | `backend/app/services/criteria.py` (`_write`는 UPDATE), `backend/sql/04_severity_criteria.sql` |
| 4-05 | 기준마다 판단 예시(가상 사례와 판단)를 붙이고 AI가 판단 때 봄 | 부분 | 등급 정의마다 '판단 예시' 글 한 칸이 있고 정의와 함께 LLM 지시문에 들어갑니다. 가상 상담 내용과 판단(등급 또는 오탐)을 쌍으로 적는 구조와 규칙(오탐 기준 등)마다 붙이는 기능은 없습니다. | `frontend/src/views/CriteriaView.vue`, `backend/app/services/criteria.py` (`llm_definitions`) |
| 4-06 | 제품 AI가 쓸 LLM(Claude 또는 GPT와 모델)을 화면에서 고름 | 향후 과제 | 화면에서 고르는 기능이 없습니다. LLM 공급자와 모델은 환경 설정값(`LLM_PROVIDER`, `LLM_MODEL`)으로 바꿉니다. | `backend/app/database.py`, `backend/app/agents/llm.py`, `axhub.yaml` |
| 4-07 | 판단 예시를 고치고 지움(고칠 때 이유, 지운 것은 기록에 남음) | 부분 | 판단 예시 글을 고칠 수 있고(변경 사유 필수) 지운 예시를 기록에 남기는 처리는 없습니다. | `frontend/src/views/CriteriaView.vue` |
| 4-08 | AI와 사람이 다르게 본 판단을 모아 보고 예시로 더함 | 향후 과제 | 승인할 때 바꾼 등급, 오탐 바로잡음 등을 모아 보여 주는 화면과 '판단 예시로 더하기'가 없습니다. 현업이 확인한 결과를 유형 상담 자료(`type_cases.json`)에 사람이 직접 고쳐 반영하는 방식은 있지만, 화면에서 모으거나 더하는 기능은 없습니다. | `frontend/src/views/CriteriaView.vue` (해당 화면 없음), `backend/app/data/type_cases.json` |

### 4-5. 탭 5 담당자관리

| 요건 번호 | 요건 한 줄 요약 | 상태 | VocAi에서는 | 근거 |
|---|---|---|---|---|
| 5-01 | 사용자를 더하고 고침(이름, 역할, 부서, 계정, 처음 비밀번호, 역할 여러 개, 심사용 계정 네 개) | 부분 | 사용자관리에서 로그인 아이디(중복 불가), 이름, 권한(하나), 연결 직원(인사정보의 부서)을 더하고 고칩니다. 회원가입과 사용자 삭제는 없고 사용 중지로 처리하며, 본인 계정의 권한 변경과 사용 중지는 막습니다. 역할 여러 개, 처음 비밀번호과 첫 로그인 때 변경, 심사용 계정 네 개 규칙은 없습니다. | `frontend/src/views/UserAdminView.vue`, `backend/app/routers/admin_api.py` (`create_user`, `update_user`) |
| 5-02 | IT 담당자의 업무 분장 관리(오류 유형별, 업무(상품, 서비스)별 담당·부담당·팀장) | 부분 | 인사정보 관리에서 IT담당자마다 알림 역할(담당, 부담당, 팀장), 담당 오류 유형(복수 선택), 담당 시스템과 업무 상세(글)를 정합니다. 오류 유형별 분장은 되지만 업무(상품, 서비스) 목록과 업무별 분장은 없습니다. | `frontend/src/views/EmployeeView.vue`, `backend/app/routers/admin_api.py` (`EmployeeIn`, `_normalize_duty`) |
| 5-04 | 비밀번호 초기화, 잠금 해제, 사용 중지·다시 사용, 5회 실패 잠금, 심사용 계정 보호 | 부분 | 관리자가 새 비밀번호를 입력해 초기화(기존 로그인 종료), 잠금 해제 버튼, 사용 중지와 다시 사용, 5회 연속 실패 잠금, 중지 계정 로그인 불가가 있습니다. 초기화한 비밀번호를 처음 비밀번호로 바꾸고 안내하는 처리와 심사용 계정의 초기화·중지 금지는 없습니다. | `frontend/src/views/UserAdminView.vue`, `backend/app/services/auth.py` (`login`), `backend/app/routers/admin_api.py` (`update_user`) |
| 5-05 | 근무하지 않는 담당자는 알림 대상에서 빠짐(모두 근무하지 않으면 '찾지 못함' 표시) | 부분 | 인사정보의 '근무 중' 체크를 바꾸고, 근무 외 담당자는 알림 대상에서 빠집니다. 맡은 사람이 모두 근무하지 않을 때 '찾지 못함' 표시는 없고 '기타' 유형 담당으로 대체됩니다. | `frontend/src/views/EmployeeView.vue`, `backend/app/services/repo.py` (`find_it_staff`), `backend/app/agents/notify.py` (`primary_recipients`) |
| 5-06 | 역할마다 쓸 수 있는 화면(탭)을 켜고 끔 | 향후 과제 | 화면 권한을 설정하는 화면과 저장 항목이 없습니다. 권한별 화면은 코드에 고정돼 있습니다. | `frontend/src/App.vue` (`MENUS`), `backend/app/services/auth.py` |
| 5-07 | 담당자 정보에 부서, 직급, 텔레그램을 적고 대화 목록에서 골라 이음('연결됨' 표시, 끊기, 한 사람에게만) | 부분 | 부서와 직급은 글로 적고, 텔레그램은 'chat_id 찾기' 버튼으로 봇에게 말을 건 대화 목록을 불러와 고르면 메신저 ID에 들어갑니다(직접 입력도 가능). '텔레그램 연결됨' 표시와 연결 끊기 버튼은 없고, 같은 chat_id를 한 사람에게만 붙이는 검사가 없어 시드 데이터에서 같은 ID를 여러 담당자가 씁니다. | `frontend/src/views/EmployeeView.vue` (`findTelegramChats`), `backend/app/routers/voc_api.py` (`telegram_chats`), `backend/sql/05_users_hr.sql` |

### 4-6. 탭 6 시험상담등록

| 요건 번호 | 요건 한 줄 요약 | 상태 | VocAi에서는 | 근거 |
|---|---|---|---|---|
| 6-01 | 가상 고객 등록·수정(이름, 핸드폰, 성별, 나이, 번호 자동, 검색, 텔레그램 고객 표시) | 부분 | 고객정보 관리에서 이름, 핸드폰 번호(010-0000-0000 형식, 중복 불가), 성별, 나이를 등록·수정하고, 고객번호는 자동으로 붙고, 이름·번호·고객번호로 찾으며, 최근 상담과 상담 건수를 보입니다. 텔레그램 고객 표시와 시험 데이터 되돌리기 연동은 없습니다. | `frontend/src/views/CustomerView.vue`, `backend/app/routers/customer_api.py` (`create_customer`, `update_customer`) |
| 6-02 | 가상 상담 넣기(고객, 상담사, 일시, 채널, 대화 원문) | 부분 | 상담데이터 등록에서 고객, 상담사(인사정보), 상담일자·최초시간, 대화 줄(고객·상담사)을 넣으면 '진행' 상태 상담으로 상담현황에 나타납니다. 고객 말이 없는 상담과 현재보다 5분 넘게 미래인 일시는 막습니다. 채널을 넣는 칸은 없고 상담사가 이력 등록 때 고릅니다. | `frontend/src/views/ConsultDataView.vue`, `backend/app/routers/customer_api.py` (`create_consult_data`) |
| 6-03 | 시험 상담마다 정답(장애 여부, 등급, 오탐 여부, 묶일 상담)을 적어 둠 | 향후 과제 | 정답을 입력하는 칸, 테이블, 화면이 없습니다. | `backend/sql/*.sql`, `frontend/src/views/ConsultDataView.vue` (해당 항목 없음) |
| 6-04 | 시연용 묶음을 한 번에 넣고 처음 상태로 되돌림(판단을 끝낸 장애는 넣지 않음, 일시는 넣는 시각 기준) | 다름 | 관리자 화면의 '묶음 넣기·되돌리기'는 없습니다. 시연 상담(등급별 16건과 사전 제보 6건, 초기 시드 통화 10건, '진행' 상태, 시작 시각은 넣는 시각 기준 `now() - interval`)은 DB를 처음 만들 때 SQL로 들어가고, 되돌리기는 배포 설정값(`DB_RESET_TOKEN`)이나 `init_db.py --reset`으로 DB 전체를 다시 만드는 방식입니다. 이때 판단까지 끝난 과거 상담과 장애(10/15~10/28, 하루 20건)도 에이전트를 돌리지 않고 같은 형식으로 함께 들어가 '판단을 미리 끝낸 장애는 넣지 않는다'와 다릅니다. | `backend/sql/11_demo_scripts.sql`, `backend/scripts/demo_scripts.py`, `backend/app/db_init.py` (`reset_once`), `backend/app/history_seed.py` |
| 6-05 | 시연용 묶음 준비(등급마다 3건 이상, 묶일 상담, P2에서 P1 상향, 업무 조건 되풀이, 과거 오탐 유사, 고객 쪽 잘못, 딸린 개선 의견) | 부분 | 등급(P1~P4)마다 4건(16건), 같은 장애로 묶일 서로 다른 고객의 사전 제보 6건, 앞 P2 장애와 같은 주제의 개선 의견 대본이 있습니다. 업무 조건 되풀이, 고객 쪽 잘못으로 확인된 상담, 과거 오탐과 비슷한 상담은 시연 묶음에 없고(과거 상담 시드에만 있음), 실제 판단 결과는 실행해야 압니다. | `backend/scripts/demo_scripts.py`, `backend/sql/11_demo_scripts.sql`, `backend/demo/stt_excel/` |
| 6-06 | 엑셀 파일로 상담을 올림(양식 내려받기, 미리보기, 오류 줄 안내, .xlsx만) | 구현 | '엑셀로 불러오기'와 '양식 내려받기'가 있고 양식 열은 화자(고객, 상담사)와 대화내용입니다. 올린 파일은 대화 줄로 바뀌어 미리보기에 보이고 확인 뒤 등록하며, 형식이 틀리면 어느 줄이 왜 안 되는지(최대 5줄) 알려 줍니다. 비고: .xlsx(.xlsm 포함)만 받고 2MB, 200줄까지입니다. | `frontend/src/views/ConsultDataView.vue`, `backend/app/services/dialog_excel.py`, `backend/app/routers/customer_api.py` |
| 6-07 | 대화 줄 만들기·순서 바꾸기·미리보기 후 상담 넣기 | 구현 | 줄마다 말한 사람 배지를 눌러 고객·상담사를 바꾸고, 위·아래로 옮기고, 지울 수 있으며, 미리보기는 상담 화면과 같은 말풍선 모양입니다. 고객 말이 없는 상담은 넣을 수 없습니다. | `frontend/src/views/ConsultDataView.vue`, `frontend/src/components/voc/ChatTranscript.vue` |

### 4-7. 탭 7 성과측정

| 요건 번호 | 요건 한 줄 요약 | 상태 | VocAi에서는 | 근거 |
|---|---|---|---|---|
| 7-01 | 시험 상담에 대한 AI 판단이 정답과 얼마나 맞았는지 봄 | 향후 과제 | 정답이 없고 맞힘 건수를 세는 코드와 화면이 없습니다. | `backend/app`, `frontend/src/views` (해당 코드 없음) |
| 7-02 | 단계마다 걸린 시간을 건마다와 평균으로 봄(승인 구간, 알림 → 담당 확인 구간 포함) | 부분 | 상담이력을 등록한 뒤 에이전트 단계별 소요 시간(초)이 상담이력등록 화면의 실행 타임라인에 건마다 보입니다. 구간별 평균, 승인 구간, 알림 발송에서 담당 확인까지의 구간은 없고 성과측정 화면도 없습니다. 비고: 단계 시간에 시연용 지연(`AGENT_STEP_DELAY_SEC`, 기본 1.0초)이 들어갑니다. | `frontend/src/components/voc/AgentTimeline.vue`, `backend/app/services/repo.py` (`_attach_steps`), `backend/app/database.py` |
| 7-03 | 걸린 시간을 지금 방식(30분 이상)과 나란히 보여 주고 출처를 적음 | 향후 과제 | 비교 화면과 출처 표시가 없습니다. | `frontend/src/views` (해당 화면 없음) |
| 7-04 | 기간별 장애 건수와 처리 시간을 봄(나중) | 부분 | 장애 알림 모니터에서 조회 기간별 장애 등록 건수와 처리 완료 건수를 박스로 봅니다. 처리 시간 집계는 없습니다. | `frontend/src/views/IncidentMonitorView.vue`, `backend/app/routers/voc_api.py` (`monitor_counts`) |

## 5. 향후 과제

코드에 없는 요건 16개입니다. 요건에서 지우지 않고 이번 제출 범위 밖으로 나눴습니다([ADR-011](../adr/ADR-011-future-work-scope.md)). 규모는 코드를 읽고 한 추정이며 개발 담당과 확인하지 않았습니다.

| 묶음 | 요건 | 내용 | 규모(추정) |
|---|---|---|---|
| 화면 구성 | 0-26 | 탭 1~3의 목록·내용·AI 판단 세 칸 화면과 칸 크기 조절 | 대 |
| 텔레그램 고객 대화 | 1-12, 1-13, 1-15 | 봇이 받은 말을 진행 중 상담으로 만들고, 상담사 답장과 고객 안내를 텔레그램으로 보냄 | 대 |
| 성과 측정 | 6-03, 7-01, 7-03 | 시험 상담의 정답 입력, AI 판단과 정답의 일치 집계, 지금 방식과 시간 비교 | 대 |
| 화면 권한 | 5-06 | 역할마다 쓸 화면을 화면에서 켜고 끔 (지금은 코드에 고정) | 대 |
| 판단 기준 관리 | 4-04, 4-06, 4-08 | 기준 고친 기록과 되돌리기, 화면에서 LLM 고르기, AI와 사람이 다르게 본 판단 모으기 | 중 |
| 장애 처리 | 0-23, 0-24, 2-20 | 「AI 판단 실패」 처리, 처리 끝난 장애 다시 열기, 장애 내용 고치기 | 중 |
| 고객 안내 | 1-10 | 고객에게 안내한 기록 남기기 | 중 |
| 목록 | 2-23 | 목록을 날짜로 오름차순·내림차순 정렬 | 소 |

## 6. VocAi에만 있는 기능

요건에 없거나 요건보다 넓게 구현된 것입니다. 괄호 안은 관련 요건 번호입니다.

| 기능 | 내용 | 근거 |
|---|---|---|
| LangGraph 흐름도 API | 에이전트 그래프 구조를 노드·간선과 mermaid 텍스트로 돌려주는 `GET /api/agent-graph` (화면의 단계 그림은 1-14) | `backend/app/agents/graph.py` (`GRAPH_SPEC`, `mermaid`), `backend/app/routers/voc_api.py` (`agent_graph`) |
| 에이전트 실행 이력 | 실행(`agent_run`)과 단계(`agent_step`)를 기록하고, 모니터 아래 '최근 에이전트 실행' 표와 상담 화면 타임라인(원문·상담이력 분석 결과, RAG 검색 결과, 2차 오탐 대조 결과, 단계별 소요 초)으로 보입니다 | `frontend/src/components/voc/AgentTimeline.vue`, `frontend/src/views/IncidentMonitorView.vue`, `backend/app/services/repo.py` (`list_runs`) |
| 임베딩 RAG | 로컬 Ollama 임베딩(기본 `bge-m3`)과 pgvector 검색, pgvector가 없으면 `real[]` 계산, 임베딩 서버가 없으면 문자열 유사도로 대체합니다. 기본값은 문자열 유사도입니다(0-12, 0-13) | `backend/app/services/rag.py`, `backend/app/database.py` (`rag_search`), `backend/sql/03_pgvector.sql` |
| 개선의견 목록 화면 | 개선 의견 기록을 보고 고객 발화를 펼쳐 보며 관련 장애로 이동합니다(0-20은 기록까지만) | `frontend/src/views/ImprovementView.vue`, `backend/app/routers/voc_api.py` (`list_improvements`) |
| 개선의견 판별 규칙 | 해결·완료 표현과 개선 요청 표현이 있고 지금 막힌 업무가 없으면 개선 의견으로 분류합니다 | `backend/app/agents/rules.py` (`is_improvement`), `backend/app/agents/detection.py` |
| 엑셀 추출·복사등록 | 업로드(6-06) 말고도 상담이력 화면에서 원문 대화를 같은 양식의 엑셀로 내려받고, 같은 대화를 상담데이터 등록 화면에 복사해 새 상담으로 등록합니다 | `frontend/src/views/ConsultRegisterView.vue` (`copyDialog`, `exportDialog`), `backend/app/routers/customer_api.py` (`dialog_excel_export`) |
| 장애번호 규칙 | 장애를 `ERR-0001` 형식 번호로 보이고 DB에도 저장 컬럼(`incident_no`)으로 둡니다 | `backend/sql/12_incident_no.sql`, `backend/app/services/repo.py` (`incident_no`), `frontend/src/utils/format.js` |
| 판별 기준 구조 | 등급 정의(알림 최소 제보 건수, 관찰 여부, 수신 역할, 목표 인지·조치 시간, 메시지 머리말, 사용 여부, 적용 종료일), 오류 유형·채널별 기본 등급 규칙, 조정 규칙 5가지 조치(RAISE, SET_GRADE, RAISE_TO, LOWER_TO, FALSE_POSITIVE)와 적용 순서, 기준 테이블이 비면 코드 기본값 사용(출처 DB, CODE 표시) | `backend/sql/04_severity_criteria.sql`, `backend/app/services/criteria.py`, `frontend/src/views/CriteriaView.vue` |
| 관찰·미대상 상태 | 알림 조건을 못 채운 장애를 '관찰'(센터관리자 확인) 또는 '미대상'(자동 종결)으로 등록하고, 추가 제보가 쌓이면 다시 판단해 관찰이나 접수로 엽니다 (2-12~2-15와 비슷) | `backend/sql/13_observe_manual_notify.sql`, `backend/app/agents/notify.py` (`register`) |
| 정상 진행 확인 규칙 | 일시 실패 뒤 정상 진행됐다고 말하면 미해결 장애 누적에서 빼고 별도 관찰 건으로 등록하며 등급을 최대 P3로 낮춥니다 | `backend/app/agents/dedup.py` (`_recovered_words`), `backend/sql/10_impact_improvement.sql` (`RECOVERED_P3`) |
| 장애 감지 보강 | 팀이 확인한 유형 상담 38개와 P1 관계 지도를 AI에 함께 주고, 상담사가 통화 중 해결했는지와 AI가 인용한 말이 실제 대화에 있는지 확인해 장애 여부와 P1 가능성을 정합니다. 결과는 등급 상한·하한으로 반영되고 상담사 해결 건은 미해결 고객 집계에서 빠집니다. 자료 2개는 「초안 — 팀 확인 전」이고, 현업 확인 결과는 사람이 자료 파일을 고쳐 반영합니다(0-04, 0-12, 0-13, 4-08과 관련) | `backend/app/agents/p1_flow.py`, `backend/app/agents/detection.py`, `backend/app/agents/severity.py`, `backend/app/services/type_cases.py`, `backend/app/services/p1_graph.py`, `backend/app/data/` |
| 판별 결과 팝업 | 상담이력을 등록하거나 재실행한 실행이 끝나면 등급, 알림을 보냈는지와 이후 처리, 판단 근거, 등급별 처리 기준을 팝업으로 보여 줍니다(1-06과 관련) | `frontend/src/components/voc/RunResultModal.vue`, `frontend/src/views/ConsultRegisterView.vue` |
| 목록 정렬·페이징 | 상담현황 목록은 열 머리글로 정렬하고, 목록 화면들은 15건씩 나눠 보여 줍니다(1-01, 2-23과 관련) | `frontend/src/views/ConsultStatusView.vue`, `frontend/src/composables/usePager.js`, `frontend/src/components/voc/ListPager.vue` |
| 홈 링크 | 상단 로고·제목을 누르면 처음 화면(상담현황, 권한이 없으면 볼 수 있는 첫 메뉴)으로 갑니다 | `frontend/src/App.vue` (`homePath`) |
| 초기 분석 | 오류 유형별 점검 가이드와 LLM이 쓰는 추정 원인·점검 포인트, 과거 해결 사례 인용(`ref_cases`)을 알림 본문과 상세에 넣습니다 (0-16과 일부 겹침) | `backend/app/agents/rules.py` (`CHECK_GUIDE`), `backend/app/agents/severity.py` |
| 재현 정보 추출 | 대화에서 OS, 기기, 앱 버전, 브라우저, 오류 코드, 오류 문구, 발생 시점을 정규식으로 뽑습니다 (0-05와 일부 겹침) | `backend/app/agents/rules.py` (`extract_env`) |
| LLM 공급자 선택과 대체 | `anthropic`, `ollama`, `none`을 설정으로 고르고, 호출이 실패하면 규칙 기반 결과로 이어 갑니다. 상담요약 초안도 같은 방식입니다 | `backend/app/agents/llm.py`, `backend/app/agents/summary.py` |
| 알림 방식 3종 | 시스템 안 기록(MOCK), 웹훅(JSON POST), 텔레그램을 설정으로 고릅니다 (0-27) | `backend/app/services/messenger.py` |
| 알림 본문 구성 | 장애 개요, 증상, 재현 정보, 최근 제보, 초기 분석, 과거 해결 사례, 수신자, 상세 링크를 담고 등급이 오르면 '[등급 상향 A→B]'와 변경 근거를 덧붙입니다 (0-16, 0-17) | `backend/app/agents/notify.py` (`compose`, `run`) |
| 모니터 부가 기능 | 조회 기간 날짜 선택, 자동 새로고침 켜고 끄기, 긴급 장애 박스 깜빡임, 선택한 등급 이름 표시 | `frontend/src/views/IncidentMonitorView.vue`, `backend/app/routers/voc_api.py` (`monitor_counts`) |
| 로그인 구현 | PBKDF2 해시 저장, 세션 토큰은 해시만 저장하고 사용할 때마다 만료 연장(기본 12시간), 5회 실패 잠금, 개발용 인증 끄기 설정(`AUTH_REQUIRED=false`) (0-01, 5-04와 일부 겹침) | `backend/app/services/auth.py`, `backend/app/database.py` |
| 시연 데이터 | 등급별 STT 원문 16건, 사전 제보 6건, 업로드용 엑셀 22개, 하루 20건 과거 상담 데이터(10/15~10/28)를 DB를 만들 때 넣습니다 (6-04, 6-05와 겹침) | `backend/scripts/demo_scripts.py`, `backend/sql/11_demo_scripts.sql`, `backend/demo/stt_excel/`, `backend/app/history_seed.py`, `backend/app/history_scenarios.py` |
| 배포용 DB 초기화 | 빈 DB면 테이블과 시드를 자동으로 만들고, 설정값 `DB_RESET_TOKEN`이 새 값이면 시작 때 한 번 초기화합니다 | `backend/app/db_init.py` (`init_if_empty`, `reset_once`), `backend/main.py` |
| 진행 중 통화에 대화 덧붙이기 API | 시스템관리자가 진행 중인 통화에 대화를 덧붙이는 `POST /api/stt/{call_id}/utterances`가 있으나 화면에서는 쓰지 않습니다(6-01의 '정한 것 1'은 넣지 않기로 함) | `backend/app/routers/voc_api.py` (`add_utterance`), `frontend/src/api/vocApi.js` (`addUtterance`) |
| 인사정보 부가 항목 | 사번, 센터관리자 그룹, 연결된 로그인 계정 표시, 고객 목록의 최근 상담 시각·상담 건수 | `frontend/src/views/EmployeeView.vue`, `frontend/src/views/CustomerView.vue` |
| 이전 방식 잔존 | 업무담당자(`biz_owner`) 테이블과 `GET /api/owners`, `POST /api/messenger/send`의 `owner_ids`가 남아 있습니다 | `backend/sql/01_schema.sql`, `backend/app/routers/voc_api.py` |
| 화면에 연결되지 않은 코드 | `SttListView.vue`는 어느 메뉴에도 연결돼 있지 않고, `ApiTestView.vue`는 숨은 주소(`#/api-test`)로만 열리며, `users_dao.py`와 `getRt.py`는 예제 API입니다 | `frontend/src/views/SttListView.vue`, `frontend/src/views/ApiTestView.vue`, `backend/app/routers/users_dao.py`, `backend/app/routers/getRt.py` |

## 7. 확인 못 한 것

- 실제 판단 결과: 시연 원문 22건이 요건대로 장애 여부, 등급, 같은 장애 묶기, 오탐 판별로 나오는지는 앱을 실행하고 LLM을 호출해야 알 수 있습니다. 판단 규칙과 흐름이 코드에 있는지만 확인했습니다.
- 0-22: 시연 원문이 실제 사례나 실제 상품 이름에서 왔는지는 코드로 판단할 수 없습니다.
- 6-05: 사전 제보 6건으로 P2에서 P1로 오르는 흐름이 실제로 그렇게 판정되는지는 확인하지 못했습니다.
- 제출 환경의 설정값: `ANTHROPIC_API_KEY`, `MESSENGER_PROVIDER`, `TELEGRAM_BOT_TOKEN`, `RAG_SEARCH`, `AGENT_STEP_DELAY_SEC`, `DB_RESET_TOKEN`이 배포에서 무엇으로 설정됐는지는 코드에 없습니다. 그래서 LLM이 실제로 쓰이는지, 알림이 어디로 가는지, 시드와 과거 상담이 DB에 들어 있는지 알 수 없습니다.
- 텔레그램과 임베딩의 실제 동작: 봇 토큰, 로컬 임베딩 서버(Ollama), pgvector가 필요해 전송과 검색이 실제로 되는지는 확인하지 못했습니다.
- 화면 모양: 레이아웃과 반응형은 CSS와 템플릿을 읽고 판단했을 뿐 화면으로 본 것이 아닙니다. 0-26의 '세 칸'이 없다는 판단은 템플릿 구조를 근거로 했습니다.
- 5-07의 같은 chat_id 중복: 시드 데이터에 같은 ID를 여러 담당자가 쓰는 것은 SQL로 확인했지만, 제출 DB의 현재 값은 확인하지 못했습니다.
