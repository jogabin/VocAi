# VOC 기반 자율형 장애 알림 AI Agent - 실행 가이드

```
backend/     FastAPI (Cloud Run 배포 대상, 배포 시 frontend 빌드 결과가 backend/static 으로 복사됨)
frontend/    Vue 3 + Vite
deploy.ps1   Vue 빌드 → backend/static 복사 → Cloud Run 배포
```

## 0. 구성 요약
- **에이전트 오케스트레이션**: LangGraph `StateGraph` (`app/agents/graph.py`)
  - 노드: 장애감지 → 중복제보 통합 → 심각도 판별 → (분기) 담당자식별·알림 / 장애이력 등록
  - 조건 분기: 장애감지 후 `장애 아님 → END`, 심각도 판별 후 `알림 대상 → 알림`, `관찰·오탐 → 이력 등록`
- **LLM**: Claude API (`claude-sonnet-5-5`) - 장애감지, 심각도 판별 노드에서 사용. 실패 시 규칙 기반으로 자동 대체
- **RAG**: 로컬 Ollama `bge-m3` 임베딩 + PostgreSQL **pgvector** 코사인 검색 (pgvector 미설치 시 `real[]` + 파이썬 계산으로 자동 대체, 임베딩 서버 미연결 시 문자열 유사도로 대체)

## 1. 추가된 파일

### 백엔드 (backend/)
| 파일 | 내용 |
|---|---|
| `sql/01_schema.sql` | 테이블 정의 (STT, 상담이력, 업무담당자, 장애알림, 제보연결, 메신저이력, 에이전트 실행로그) |
| `sql/02_seed.sql` | 시연용 데이터 (STT 통화 10건 = P1 발송 대상 3건 + 일반 상담 7건, 담당자 12명, 과거 장애/오탐 이력 5건) |
| `scripts/init_db.py` | 위 SQL 실행 스크립트 |
| `app/routers/voc_api.py` | API 5종 + 에이전트 실행/모니터 API |
| `app/services/repo.py` | DB 조회/등록 함수 (API와 에이전트가 공유) |
| `app/services/messenger.py` | 메신저 전송 (MOCK · 웹훅 · 텔레그램) |
| `app/agents/detection.py` | ① 장애감지 에이전트 |
| `app/agents/dedup.py` | ② 중복 제보 통합 에이전트 |
| `app/agents/severity.py` | ③ 장애 심각도 판별 에이전트 (규칙 + 과거이력 RAG) |
| `app/agents/notify.py` | ④ 담당자식별 및 알림 에이전트 |
| `app/agents/graph.py` | **LangGraph 그래프 정의** (노드/조건분기, mermaid 출력) |
| `app/agents/pipeline.py` | 그래프 실행 + 실행 결과 기록 |
| `app/services/rag.py` | 임베딩 생성(Ollama) + pgvector 유사사례 검색 + 지식베이스 갱신 |
| `app/agents/rules.py` | 키워드/심각도/알림 규칙 (여기서 규칙 조정) |
| `app/agents/llm.py` | Claude Messages API 호출 (JSON 출력, Ollama도 선택 가능) |

수정: `main.py` (라우터 등록, CORS에 POST/PATCH 허용), `app/database.py` (에이전트 설정 항목 추가)

### 프론트엔드 (frontend/)
| 파일 | 내용 |
|---|---|
| `src/views/SttListView.vue` | STT 대화목록 |
| `src/views/ConsultRegisterView.vue` | 상담이력 등록 (등록 시 에이전트 진행상황 실시간 표시) |
| `src/views/IncidentMonitorView.vue` | 장애 알림 모니터 (3초 자동 갱신) |
| `src/views/CriteriaView.vue` | 장애등급 판별기준 관리 (등급 정의 / 기본 등급 규칙 / 조정 규칙 조회·등록·수정) |
| `src/views/ApiTestView.vue` | 기존 FastAPI 연동 테스트 화면 |
| `src/components/voc/AgentGraph.vue` | **LangGraph 흐름도** (실행 경로 하이라이트) |
| `src/components/voc/*` | 대화 말풍선, 에이전트 타임라인, 심각도/상태 배지 |
| `src/api/vocApi.js` | API 호출 함수 |
| `src/composables/useHashRoute.js`, `usePolling.js` | 화면 전환(해시), 주기 갱신 |
| `src/assets/voc.css` | 공통 스타일 |

수정: `App.vue` (상단 메뉴), `main.js` (voc.css 사용), `index.html` (제목). 새 npm 패키지 설치는 필요 없습니다.

## 2. 사전 준비 (최초 1회)

```powershell
# 1) 가상환경 + 패키지
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env                 # 값 채우기

cd ..\frontend
npm install

# 2) 로컬 Ollama 설치 (https://ollama.com/download) 후 임베딩 모델 받기
ollama pull bge-m3
```

**pgvector (선택, 권장)**: 로컬 PostgreSQL에 pgvector가 없으면 자동으로 배열 방식으로 동작합니다.
pgvector로 시연하려면 아래 중 하나를 사용하세요.
- Docker: `docker run -d --name pgvector -p 5434:5432 -e POSTGRES_PASSWORD=비밀번호 pgvector/pgvector:pg16` 후 `.env`의 DATABASE_URL 포트 변경
- Windows 설치형 PostgreSQL: pgvector 공식 README의 Windows 빌드 안내(Visual Studio `nmake`) 참고
- Cloud SQL(배포 환경): 기본 지원 → `init_db.py`가 `CREATE EXTENSION vector` 자동 실행

pgvector를 나중에 설치했다면 `python scripts\init_db.py --reset`으로 다시 만들어야 vector 컬럼으로 바뀝니다.

## 3. 실행 순서

```powershell
cd backend
.\venv\Scripts\Activate.ps1
python scripts\init_db.py            # 테이블 + 시드 + 과거이력 임베딩 (DB 전체 초기화: --reset, 계정만 초기화: --reset-users)
uvicorn main:app --reload --port 8000

cd frontend
npm run dev                          # http://localhost:5173
```

`init_db.py` 출력에서 `incident_embedding 테이블 (pgvector)` 또는 `(array)`로 어떤 방식인지 확인할 수 있습니다.

## 3-1. .env 항목

```
ANTHROPIC_API_KEY=...                    # Claude API 키 (console.anthropic.com 에서 발급)
# 이하 선택 (기본값 있음)
LLM_PROVIDER=anthropic                   # anthropic / ollama / none(규칙 기반)
LLM_MODEL=claude-sonnet-5-5              # 비용을 줄이려면 claude-haiku-5-5
LLM_EFFORT=low                           # low / medium / high (생각 깊이)
OLLAMA_EMBED_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=bge-m3
RAG_MIN_SIMILARITY=0.45                  # 유사 사례로 표시할 최소 코사인 유사도
RAG_FP_SIMILARITY=0.60                   # 과거 오탐 사례와 같은 건으로 볼 유사도
MESSENGER_PROVIDER=telegram              # mock / webhook / telegram (비우면 웹훅 URL 유무로 자동)
TELEGRAM_BOT_TOKEN=...                   # 텔레그램 봇 토큰. 인사정보 메신저 ID = chat_id
MESSENGER_WEBHOOK_URL=                   # MESSENGER_PROVIDER=webhook 일 때
DEDUP_WINDOW_MIN=60
MASS_SIGNAL_THRESHOLD=3
AGENT_STEP_DELAY_SEC=1.0                 # 시연용 노드 간 지연(초)
```

모니터 화면 상단 배지에서 `LLM Claude · claude-sonnet-5-5`, `RAG pgvector · bge-m3` 상태를 확인할 수 있습니다.
RAG 유사도 기준값은 bge-m3 기준 추정값이므로 시연 데이터로 결과를 보고 조정하세요.

## 4. 시연 시나리오 (시드 데이터 기준)

장애 알림(메신저 발송)은 **P1 등급만** 대상입니다. P2~P4 장애는 장애알림 정보로만 등록(관찰)되고, 추가 제보로 P1이 되면 그때 알림이 나갑니다.
시드 통화 10건은 P1 발송 대상 3건 + 상담이력만 등록되는 일반 상담 7건입니다.

| 순서 | 통화 | 예상 결과 |
|---|---|---|
| 1 | CALL-0001 타행이체 출금 후 미입금 | 이체 P2 + 금전 피해 신호 → **P1**, 지급결제팀 알림 (2차: 과거 유사 장애 처리자) |
| 2 | CALL-0003 iOS 앱 로그인 불가(주변 사람들도 안 됨) | 로그인 P2 + 영향범위 확대 신호 → **P1**, 로그인 담당·부담당·팀장 알림 |
| 3 | CALL-0006 공동인증서 인증 모듈 오류(회사 직원 전부 안 됨) | 인증 P2 + 영향범위 확대 신호 → **P1**, 보안인증팀 알림 + 과거 유사사례 첨부 |
| 4 | CALL-0002·0004·0005·0007·0008·0009·0010 (카드 한도·주소 변경·예금 금리·카드 분실·자동이체·대출 납입일·영업점 시간) | 장애 미감지 → 상담이력만 등록, `장애 아님 → END` 분기 |

모니터 화면에서 장애를 선택해 "해결" 처리하고 원인/조치를 입력하면 즉시 임베딩되어(pgvector) 이후 유사 사례 검색에 사용됩니다.

## 5. API 목록 (/api 하위)

- STT원문조회: `GET /stt`, `GET /stt/{call_id}`
- 상담이력조회: `GET /consults`, `GET /consults/{id}` / 등록: `POST /consults`
- 업무담당자조회: `GET /owners?error_type=로그인`
- 장애알림정보등록: `POST /incidents` / 조회 `GET /incidents`, `GET /incidents/{id}` / 상태변경 `PATCH /incidents/{id}`
- 메신저전송: `POST /messenger/send` / 이력 `GET /messenger/logs`
- 에이전트 실행이력: `GET /agent-runs`, `GET /agent-runs/{id}`, 재실행 `POST /agent-runs`
- 모니터 요약: `GET /monitor/summary`
- LangGraph 구조: `GET /agent-graph` (발표 자료용 mermaid 텍스트 포함)

`.env`에 `ENABLE_DOCS=true`이면 http://127.0.0.1:8000/docs 에서 바로 테스트할 수 있습니다.

## 6. Cloud Run 배포 시 참고

에이전트는 상담이력 등록 응답 후 백그라운드에서 실행됩니다. Cloud Run 기본 설정(요청 처리 중에만 CPU 할당)에서는
백그라운드 처리가 느려질 수 있으므로, 시연 시 `deploy.ps1`의 `gcloud run deploy`에 `--no-cpu-throttling` 추가를 권장합니다(과금 방식 변경됨).
배포 전 Cloud SQL에도 `python scripts\init_db.py` 실행이 필요합니다.
Cloud Run에서는 PC의 로컬 Ollama(임베딩)에 접근할 수 없으므로, 배포 환경에서는 RAG가 문자열 유사도로 대체됩니다. (임베딩 서버를 별도로 두면 `OLLAMA_EMBED_BASE_URL`로 지정)

## 7. 장애등급 판별기준 관리 (DB)

심각도 판별 에이전트는 등급 기준을 DB 테이블 3개에서 읽습니다. 테이블이 없거나 비어 있으면 `app/agents/rules.py`의 코드 기본값으로 동작합니다.

| 테이블 | 내용 |
|---|---|
| `severity_grade` | 등급 정의(P1~P4), 알림 최소 제보 건수, 수신 역할, 목표 시간, 메시지 머리말. 정의·판단 예시는 LLM 프롬프트에도 사용 |
| `severity_base_rule` | 오류유형·채널별 기본 등급 (채널 일치 규칙 우선) |
| `severity_adjust_rule` | 조정 규칙: KEYWORD(키워드 상향), REPORT_COUNT(제보 건수), MASS_SIGNAL(대규모 신호, 기준 건수는 중복통합에도 사용), FALSE_POSITIVE(오탐). `apply_order` 순서로 적용 |

- 생성: 로컬은 `python scripts\init_db.py`, Cloud SQL은 `sql/04_severity_criteria.sql` 실행 (기존 데이터 유지, 여러 번 실행 가능)
- 초기 데이터: 기존 `rules.py` 기준을 그대로 옮김 (등급 4, 기본 등급 6, 조정 규칙 4)
- 판정 결과: 장애(`incident_alert`)에 `criteria_version`(기준 최종 수정 시각)과 `applied_rules`(적용 규칙코드)를 기록. 모니터 장애 상세에 표시
- 수정: `GET /api/severity-criteria`로 조회, `POST/PATCH /api/severity-criteria/grades|base-rules|adjust-rules`로 등록·수정 (수정자·변경 사유 기록, `use_yn=false`로 끄기). 재배포 없이 5초 안에 반영
- 관리 화면: 상단 메뉴 **판별기준 관리**(`#/criteria`). 행을 클릭해 수정, `+ 추가`로 등록, 조정 규칙은 표의 스위치로 바로 켜고 끔. 수정 시 변경 사유 필수. 테이블이 없으면 코드 기본값을 조회만 할 수 있음

## 8. 로그인 · 사용자관리 · 인사정보 (1단계 개선)

- 테이블: `employee`(인사정보: 상담사/센터관리자/IT담당자), `voc_user`(로그인 사용자), `voc_session`(로그인 세션). `sql/05_users_hr.sql`
  - 생성: 로컬은 `python scripts\init_db.py`, Cloud SQL은 `sql/05_users_hr.sql` 실행 (여러 번 실행 가능)
  - 초기 데이터: 기존 업무담당자(biz_owner) 12명을 IT담당자로 이관 + 상담사 3명 + 센터관리자 2명
  - 초기 계정: `admin / admin`(시스템관리자), `user01 / user01`(상담사), `user02 / user02`(IT담당자) → 운영 시 사용자관리에서 비밀번호 변경
  - 계정만 초기 계정으로 되돌리기: `python scripts\init_db.py --reset-users` (다른 데이터 유지) / DB 정보 전체 초기화: `python scripts\init_db.py --reset`
- 로그인: 비밀번호는 PBKDF2 해시로 저장, 로그인 시 발급한 토큰으로 세션 유지(마지막 사용 후 `SESSION_HOURS`시간, 기본 12). 5회 연속 실패 시 잠금 → 사용자관리에서 해제
- 권한: 관리자만 판별기준 관리·사용자관리·인사정보 관리 메뉴 사용. 일반 사용자는 상담·모니터 메뉴만 보임
- `/api` 의 VOC·관리 API는 로그인 토큰(`Authorization: Bearer`)이 필요. 개발 중 잠시 끄려면 `.env`에 `AUTH_REQUIRED=false`
- API
  - 로그인: `POST /auth/login`, `GET /auth/me`, `POST /auth/logout`, `POST /auth/password`
  - 사용자관리(관리자): `GET/POST /voc-users`, `GET/PATCH /voc-users/{id}` (비밀번호 초기화 `new_password`, 잠금 해제 `unlock`)
  - 인사정보 조회: `GET /employees?group=IT담당자&error_type=로그인` / 등록·수정(관리자): `POST /employees`, `PATCH /employees/{id}`
- `.env` 추가 항목(선택): `AUTH_REQUIRED=true`, `SESSION_HOURS=12`, `LOGIN_MAX_FAIL=5`, `APP_BASE_URL=http://localhost:5173`(메신저 알림 링크용, 2단계에서 사용)

## 9. 상담현황 · 상담이력등록 · 에이전트 개선 (2단계)

- DB: `sql/06_consult_agent.sql` (로컬은 `python scripts\init_db.py`, Cloud SQL은 05 다음에 06 실행)
  - `stt_call.consult_status`(진행/상담완료), `stt_utterance.added_by`(관리자 추가 대화), `consult_history.registered_by`
  - `incident_alert.owner_emp_id`(담당), `resolved_by_emp_id`(처리자), `messenger_log.emp_id / recipient_type(1차·2차) / link_url`
  - 시연용 과거 해결 건 처리자 2명(정다은·김태호) 추가 → 메신저 2차 수신자로 나타남
- 화면
  - 상담현황(`#/stt`): 조회 기간(통화일, 기본 최근 7일) · 진행/상담완료 목록, 5초 자동 갱신, 행 클릭 → 상담이력등록, 등록된 통화는 [등록완료] 버튼 → 등록된 상담이력
  - 상담이력등록(`#/consult?call=...`): STT 원문 + [원문대화 복사등록](시스템관리자, 상담완료 건 포함 → 상담데이터 등록 화면에 대화 자동 입력) + [상담요약 초안 작성] 버튼, 통화 선택 셀렉트박스는 비활성(현재 통화만 표시), 고객번호·고객명 고정,
    상담유형·접촉채널·접촉결과·상담요약 입력 → 등록 시 상담완료 + 에이전트 실행, 하단 LangGraph 그래프로 진행 표시.
    상담완료 건은 등록 정보와 마지막 실행 결과만 조회
- 에이전트
  - 장애감지: STT 원문 분석과 상담이력 분석을 각각 수행 → 하나라도 장애면 장애 대상
  - 중복제보 통합: 60분 내 동일 유형 유사 장애 통합, 3건 이상이면 대규모 신호(모니터 '동일유형 장애' 건수)
  - 심각도 판별: 1차 판별기준으로 알림 대상 판정 → 대상일 때만 2차 과거 오탐 사례 대조
  - 메신저 전송: 1차 인사정보 담당 IT담당자(등급별 수신 역할) + 2차 과거 유사 장애 처리자, 과거 해결 사례·상세 링크 포함 템플릿
- 상세 링크: `APP_BASE_URL/#/incident?id=N` (2단계에서는 장애 알림 모니터로 이동, 3단계에서 장애 상세정보 화면으로 연결)
- API 추가: `GET /stt?consult_status=진행`, `POST /stt/{call_id}/utterances`(관리자), `POST /messenger/send`에 `emp_ids`
- 시연을 처음부터 다시 하려면 `python scripts\init_db.py --reset` (모든 통화가 다시 '진행' 상태가 됨)
- 배포 환경(axhub)의 DB 초기화: 설정값 `DB_RESET_TOKEN` 에 이전과 다른 값(예: `2026-10-26`)을 넣고 재배포하면
  서버 시작 시 한 번만 `--reset` 과 같은 초기화를 합니다. 같은 값으로 재시작·재배포하면 다시 지우지 않습니다.

## 10. 장애 알림 모니터 · 장애 상세정보 · 판별기준 정리 (3단계)

- DB: `sql/07_incident_process.sql` — `incident_action`(장애 처리 이력). 로컬은 `python scripts\init_db.py`, Cloud SQL은 06 다음에 07 실행
- 처리상태(화면) ↔ 내부 상태: 대기중=관찰·접수 / 진행중=확인중 / 미대상=오탐 / 처리완료=해결
- 장애 알림 모니터(`#/monitor`)
  - 건수 박스 5개: 장애 정보 등록 · 긴급 장애(최상위 등급, 미처리) · 메신저 알림 전송 · 동일유형 장애(대규모 신호) · 장애 처리 완료
  - 조회 기간(장애 등록일, 기본 최근 7일) 날짜 선택, 긴급 장애가 있으면 박스 깜빡임, 박스 클릭 → 아래 목록, 목록 클릭 → 장애 상세정보
- 장애 상세정보(`#/incident?id=N`, 메신저 알림 링크로도 진입)
  - 장애 정보 · 초기 분석 · 판정 근거 · 과거 유사 사례 · 제보 상담 · 메신저 전송 정보(1차/2차, 메시지 내용) · 처리 이력
  - IT담당자(인사정보 그룹 IT담당자) 또는 관리자가 처리 상태 + 처리 내용 등록. 처리완료·미대상은 처리 내용 필수,
    처리완료 시 처리자로 기록되고 RAG 지식베이스에 반영 → 이후 유사 장애의 메신저 2차 수신자·과거 해결 사례로 사용
- 판별기준 관리: 용어를 요건정의에 맞춤(접촉채널, 적용조건), 화면 조회·등록·수정 모두 시스템관리자만, 수정자는 로그인 아이디로 기록
- API 추가: `GET /monitor/counts?period=today|7d|all`, `GET /incidents?box=urgent&period=today`, `POST /incidents/{id}/actions`

## 11. 고객정보 관리 · 상담데이터 등록 (신규 화면)

- DB: `sql/08_customer_consult_data.sql` — `customer`(고객정보, 고객번호 `CUST-9xxxx` 자동 채번), `stt_call.agent_emp_id`(상담사 연결),
  통화 → 고객 FK, 통화 ID 채번 시퀀스. 기존 시연 고객 10명은 연락처·성별·나이와 함께 고객정보로 이관.
  로컬은 `python scripts\init_db.py`, Cloud SQL은 07 다음에 08 실행
- 고객정보 관리(`#/customers`, 관리자): 목록(고객번호·고객명·핸드폰번호·성별·나이·최근 상담), 검색, 등록·수정.
  핸드폰번호는 숫자만 입력해도 `010-0000-0000` 형식으로 맞추고 중복을 막음. 이름을 바꾸면 진행 중인 상담에도 반영
- 상담데이터 등록(`#/consult-data`, 관리자): 고객(고객정보) · 상담사(인사정보 상담사) · 상담일자 · 상담최초시간 · 대화 행(화자 전환, 순서 변경, 삭제)
  입력 → 미리보기 확인 → 등록하면 `CALL-00nn` 통화가 '진행' 상태로 생성되어 상담현황에 표시. 경과시간은 대화 길이로 자동 계산
- API: `GET/POST /customers`, `GET/PATCH /customers/{id}`, `POST /stt`(상담데이터 등록)
