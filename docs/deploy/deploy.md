# 배포와 운영

상태: 확인 대기  
근거: 구현된 코드(커밋 fba80ab)를 읽고 정리했습니다. 사람이 읽고 확인한 것은 아닙니다.

> 표기는 [아키텍처](../architecture/architecture.md)와 같습니다. 경로는 저장소 루트 기준이고, 「확인 못 함」은 코드만으로 확인하지 못했다는 뜻입니다. 환경변수는 이름과 뜻만 적고 값은 적지 않았습니다(전체 목록은 아키텍처 10장).

## 1. 배포 경로 두 가지

| | (a) axhub | (b) GCP Cloud Run |
|---|---|---|
| 쓰는 파일 | 루트 `Dockerfile`, `axhub.yaml` | `deploy.ps1`, `backend/Dockerfile` |
| 이미지 | Vue 빌드 결과를 FastAPI의 `static` 으로 묶은 단일 이미지 | `deploy.ps1` 이 Vue를 미리 빌드해 `backend/static` 으로 복사한 뒤, 백엔드 폴더를 `gcloud run deploy --source` 로 빌드 |
| 배포 방법 | `main` 에 push하면 웹훅으로 자동 배포 | `deploy.ps1` 실행 |
| DB | axhub의 PostgreSQL(`axhub.yaml` 의 `database.engine`) | Cloud SQL(`deploy.ps1` 의 `--add-cloudsql-instances`) |

근거: `Dockerfile` 첫 주석, `axhub.yaml`, `deploy.ps1`. Cloud Run 서비스가 지금 운영 중인지는 확인 못 함.

## 2. (a) axhub

**이미지** (`Dockerfile`)
1. Node 22 이미지에서 `frontend/` 를 `npm ci`, `npm run build` 로 빌드합니다. 이때 `frontend/.env.production` 의 `/api`(같은 출처)가 API 주소로 박힙니다.
2. Python 3.12 이미지에 `backend/requirements.txt` 를 설치하고 `backend/` 를 `/app` 에 복사한 뒤 빌드 결과를 `/app/static` 으로 복사합니다.
3. 시작 명령은 `uvicorn main:app --host 0.0.0.0 --port ${PORT:-기본값}` 입니다. FastAPI 한 프로세스가 `/api` 와 화면 파일(`/`)을 모두 서빙합니다(`backend/main.py`).

**`axhub.yaml`**
- 앱 이름 `vocai`, 포트 8080, 헬스체크 경로 `/`(화면 파일이 응답하는 경로), 프레임워크 `fastapi`, `deploy_method: docker`, DB 엔진 `postgres`.
- 환경변수 필수 선언은 `ANTHROPIC_API_KEY` 하나이고, 선택 선언은 `LLM_PROVIDER`, `LLM_MODEL`, `LLM_EFFORT`, `AGENT_STEP_DELAY_SEC`, `APP_BASE_URL`, `MESSENGER_PROVIDER`, `TELEGRAM_BOT_TOKEN`, `MESSENGER_WEBHOOK_URL`, `AUTH_REQUIRED`, `DB_RESET_TOKEN` 입니다.
- `DATABASE_URL` 은 선언돼 있지 않습니다. 코드가 `postgres://` 형식 주소를 드라이버 형식으로 바꿔 쓰므로(`backend/app/database.py`) axhub가 주입하는 것으로 보이지만 axhub 쪽 동작은 확인 못 함. 선언되지 않은 이름(예: `RAG_SEARCH`, `ENABLE_DOCS`)을 앱에 넣을 수 있는지도 확인 못 함.

**알려진 사실** (axhub 배포 기록에서 확인된 것이고 코드로는 확인할 수 없음)
- axhub 앱 이름은 `vocai` 입니다.
- `main` 에 push하면 axhub가 웹훅으로 자동 배포합니다(배포 기록에서 커밋마다 trigger가 webhook으로 나옴).
- `main` 이 아닌 브랜치를 push해도 배포가 일어나는지, 코드를 바꾸지 않은 push(문서만 바꾼 경우)에도 배포가 일어나는지는 확인 못 함.

**시작할 때 일어나는 일** (`backend/main.py` 의 `lifespan`, `backend/app/db_init.py`): ① `DB_RESET_TOKEN` 이 있으면 초기화 여부를 먼저 따집니다(5장). ② `voc_user` 테이블이 없으면(빈 DB) 테이블, 시드, 시연용 과거 상담 데이터를 자동으로 만듭니다.

## 3. (b) GCP Cloud Run

`deploy.ps1` 이 하는 일입니다. 프로젝트, 리전, Cloud SQL 인스턴스, 서비스 이름, 서비스 계정은 스크립트 위쪽 변수에 있고 여기에는 적지 않았습니다.

1. 이미 배포된 서비스의 주소를 읽어 `APP_BASE_URL` 로 넣습니다. 최초 배포라 주소가 없으면 경고만 하고 진행하므로, 배포 뒤 한 번 더 실행해야 메신저 링크가 맞습니다.
2. `frontend` 를 빌드하고, 결과에 로컬 개발 API 주소가 박혀 있으면 중단합니다.
3. 빌드 결과를 `backend/static` 으로 복사합니다(`.gitignore` 대상).
4. `gcloud run deploy --source` 로 Cloud SQL 연결, Secret Manager와 환경변수 주입, 메모리·최대 인스턴스 수, `--allow-unauthenticated`(공개 접근 허용, 접근 통제는 앱 로그인이 맡음), `--no-cpu-throttling`(응답 뒤 백그라운드로 도는 에이전트가 느려지지 않게 CPU를 계속 할당, 인스턴스가 떠 있는 동안 과금)을 지정합니다.

- 스크립트가 넣는 환경변수는 `LLM_PROVIDER`, `LLM_MODEL`, `AGENT_STEP_DELAY_SEC`, `APP_BASE_URL` 이고, Secret Manager에서 `DATABASE_URL`, `ANTHROPIC_API_KEY` 를 가져옵니다.
- 메신저 설정과 `DB_RESET_TOKEN` 은 스크립트에 없습니다. 추가 설정 없이 배포하면 메신저는 mock(DB 기록만)으로 동작합니다(`backend/app/services/messenger.py`).
- `backend/setup_secrets.ps1` 은 `.env` 의 Claude API 키를 Secret Manager에 등록하고 서비스 계정에 읽기 권한을 줍니다. `DATABASE_URL` 비밀값을 만드는 스크립트는 저장소에 없습니다(확인 못 함).
- `scripts/` 는 `backend/.gcloudignore`, `backend/.dockerignore` 에 들어 있어 이 경로의 이미지에는 `init_db.py` 가 없습니다. DB는 앱 첫 시작 때 자동으로 만들어집니다. 직접 초기화하려면 `.env` 의 `DATABASE_URL` 을 Cloud SQL로 지정해 실행하게 되는데 접속 방법은 확인 못 함(README 실행 가이드 6절은 「배포 전 Cloud SQL에도 `init_db.py` 실행이 필요」라고만 적음).

## 4. 환경변수와 비밀값 두는 곳

| 값 | 로컬 | axhub | Cloud Run |
|---|---|---|---|
| `DATABASE_URL`(비밀번호 포함) | `backend/.env` | axhub가 주입하는 것으로 보임(확인 못 함) | Secret Manager |
| `ANTHROPIC_API_KEY` | `backend/.env` | axhub 설정값(필수 선언) | Secret Manager |
| `TELEGRAM_BOT_TOKEN`, `MESSENGER_WEBHOOK_URL` | `backend/.env` | axhub 설정값 | 스크립트에 없음 |
| 그 밖의 설정 | `backend/.env` | axhub 설정값 | `deploy.ps1` 의 환경변수 문자열 |

- `.env` 는 `.gitignore` 에 들어 있어 커밋되지 않습니다. 견본 `backend/.env.example` 은 값이 비어 있습니다. 「설정값」은 README가 axhub 환경변수를 부르는 말이고(실행 가이드 9절) 입력하는 화면이나 명령은 확인 못 함.
- `APP_BASE_URL` 을 배포 주소로 바꾸지 않으면 메신저 알림의 상세 링크가 로컬 개발 주소로 나갑니다(`backend/app/database.py` 기본값).

## 5. DB 초기화

| 방법 | 하는 일 | 근거 |
|---|---|---|
| 자동(첫 시작) | `voc_user` 테이블이 없을 때 테이블, 시드, 시연용 과거 상담 데이터 생성 | `backend/app/db_init.py` 의 `init_if_empty` |
| `python scripts/init_db.py` (`backend/` 에서, `.env` 의 `DATABASE_URL` 대상) | 없는 테이블과 시드를 채움. 여러 번 실행해도 되고 과거 상담 데이터는 이미 있으면 건너뜀. 끝에 임베딩을 만들려 시도하고 실패해도 계속함 | `backend/scripts/init_db.py` |
| `... --reset` | VOC 테이블을 모두 지우고 다시 만듦(계정 포함). 연습용 `users` 테이블과 `app_meta` 는 그대로 | `backend/app/db_init.py` 의 `VOC_TABLES` |
| `... --reset-users` | 계정·세션을 지우고 초기 계정 3개로 다시 만듦. 다른 데이터는 유지 | `backend/app/db_init.py` 의 `reset_users` |
| `DB_RESET_TOKEN` | 배포 환경에서 `--reset` 과 같은 일(아래) | `backend/app/db_init.py` 의 `reset_once` |

`DB_RESET_TOKEN` 은 비워 두면 아무 일도 하지 않습니다. 서버가 시작할 때 마지막으로 적용한 값(`app_meta` 테이블에 기록)과 다르면 VOC 테이블을 모두 지우고 시드로 다시 만든 뒤 새 값을 기록하고, 같은 값이면 지우지 않습니다. `app_meta` 에 기록이 없는 DB에 처음 값을 넣는 배포도 「다른 값」이라 초기화됩니다. 인스턴스 여러 개가 동시에 시작해도 DB 잠금으로 한 곳만 초기화합니다. 초기화되면 로그인 계정도 초기 계정으로 돌아갑니다.

주의: 이미 DB가 있는 환경에는 새 SQL(예: 09~13)이 자동으로 적용되지 않습니다(자동 초기화는 `voc_user` 가 없을 때만). 스키마가 바뀐 버전을 올릴 때는 `init_db.py`(데이터 유지)를 실행하거나 `DB_RESET_TOKEN`(데이터 삭제)을 써야 합니다. axhub 안에서 `init_db.py` 를 실행하는 방법은 확인 못 함.

## 6. 로컬에서 돌리는 순서

README의 「실행 가이드」 2절(사전 준비)과 3절(실행 순서)이 원본입니다. 요약하면 `backend/` 에서 가상환경과 `requirements.txt`, `.env.example` → `.env` 복사(`DATABASE_URL` 필수), `frontend/` 에서 `npm install`, `backend/` 에서 `python scripts/init_db.py` 와 `uvicorn main:app --reload`(README의 포트는 8000, `frontend/.env.development` 의 개발용 API 주소와 같아야 함), `frontend/` 에서 `npm run dev` 입니다. Ollama와 pgvector는 `RAG_SEARCH=embedding` 일 때만 필요합니다. 로컬 Python 버전 표기(`backend/.python-version`)와 Docker 이미지의 Python 버전은 다릅니다.

## 7. 배포 뒤 확인할 것

- [ ] 헬스체크 경로 `/` 가 응답한다. 첫 배포라면 로그에 「VOC 테이블이 없어 초기화합니다」가 한 번 나온다.
- [ ] 로그인 없이 `GET /api/monitor/summary` 를 부르면 401이고, `/docs` 는 열리지 않는다(`ENABLE_DOCS` 꺼짐).
- [ ] 시드 계정(README 실행 가이드 8절)으로 로그인한 뒤 사용자관리에서 비밀번호를 초기화한다(시드 계정이 고정돼 있고 첫 로그인 때 변경을 강제하지 않음).
- [ ] 장애 알림 모니터 상단 배지가 의도한 값이다: LLM(키를 인식하면 「LLM Claude · 모델」, 못 하면 「규칙 기반 모드」), RAG 방식, 메신저 방식(mock / telegram / webhook).
- [ ] `APP_BASE_URL` 이 배포 주소다(장애 상세정보 「메신저 전송 정보」의 상세 링크로 확인).
- [ ] `AGENT_STEP_DELAY_SEC` 이 의도한 값이다(시연 중이면 켜 두고 운영이면 0). Cloud Run이면 `--no-cpu-throttling` 도 확인한다.
- [ ] 시연 흐름을 한 번 돌린다: 상담현황에서 「진행」 통화 열기 → 상담요약 초안 작성 → 상담이력 등록 → 흐름도가 끝까지 진행 → 장애 상세정보 → (P1이면) 메신저 전송 정보 → 관찰 장애는 센터관리자 계정으로 수동 알림 → IT담당자 계정으로 처리 등록. P1 대규모 신호 시연은 사전 제보 통화를 시간창 안에 먼저 등록해야 한다(`backend/scripts/demo_scripts.py` 맨 위 주석).
- [ ] 텔레그램을 쓰면 수신자 직원의 메신저 ID가 chat_id이고 수신자가 봇에게 먼저 메시지를 보낸 상태인지 확인한다(인사정보 관리 화면의 chat_id 찾기).
- [ ] `DB_RESET_TOKEN` 이 의도하지 않게 바뀌지 않았다(바뀐 채 배포하면 시작할 때 데이터가 삭제된다).
