# ADR-007 기술 스택

- 상태: 검토 중 (팀 확인 전)
- 날짜: 2026-10-30
- 성격: 구현된 스택을 나중에 정리한 기록입니다. 고를 때 안을 비교한 기록은 남아 있지 않습니다. 이유 칸에는 코드, README, 커밋 메시지에 적힌 것만 옮겼고, 적힌 것이 없으면 「이유 기록 없음」이라고 썼습니다.
- 원본: 구조와 동작은 [architecture.md](../architecture/architecture.md)에 있습니다. 이 ADR은 고른 것과 이유만 옮겼습니다.

## 요약

장애 감지와 알림은 Python(FastAPI) 서버가 맡고, 에이전트의 단계는 LangGraph로 이어 붙입니다.  
LLM은 Claude API를 쓰고, 쓸 수 없으면 규칙으로 대신합니다. 화면은 Vue 3입니다.  
정보는 PostgreSQL 하나에 두고, axhub에는 화면과 서버를 묶은 컨테이너 하나로 올립니다.

| 무엇 | 고른 것 |
|---|---|
| 서버 | Python 3.12, FastAPI, SQLAlchemy 2 + psycopg 3 |
| 에이전트 흐름 | LangGraph `StateGraph` |
| LLM | Claude API(기본). Ollama도 고를 수 있고, `none`이면 규칙 기반 |
| 비슷한 과거 사례 찾기(RAG) | 기본은 문자열 유사도, 선택으로 임베딩(Ollama `bge-m3`) + pgvector |
| DB | PostgreSQL |
| 화면 | Vue 3 + Vite, Axios, 해시 주소로 화면 전환(vue-router 없음) |
| 알림 | 메신저 방식 `mock` / `webhook` / `telegram` |
| 배포 | axhub: 루트 `Dockerfile` 하나로 묶은 단일 이미지. 같은 코드를 GCP Cloud Run(`deploy.ps1`)으로도 올릴 수 있음 |

## 결정과 이유

| 무엇 | 이유(근거) | 고르지 않은 안 |
|---|---|---|
| FastAPI + SQLAlchemy + psycopg | 이유 기록 없음 (`backend/requirements.txt`) | 기록 없음 |
| LangGraph | 이유 기록 없음. 결과로 장애감지 → 중복 제보 통합 → 심각도 판별 → (분기) 담당자 식별·알림 또는 장애 이력 등록이 노드와 조건 분기로 그려져 있고, 화면에 흐름도(`frontend/src/components/voc/AgentGraph.vue`)가 있습니다(README 「구성 요약」). | 기록 없음 |
| Claude API가 기본, 쓸 수 없으면 규칙 | 커밋 7a33990에서 Ollama를 Claude API로 바꿨고, 기본 provider를 `anthropic`, 생각 깊이(effort)를 `low`로 두었습니다. LLM 호출이 실패하면 규칙 기반으로 자동 대체합니다(README 「구성 요약」). | Ollama(`LLM_PROVIDER=ollama`로 남아 있음) |
| RAG 기본은 문자열 유사도 | 배포 서버에서는 개발 PC의 로컬 Ollama에 닿지 않아서, 배포 환경 기본값을 `text`로 둡니다(`backend/app/database.py` 주석). 임베딩은 로컬에서 시연할 때 고르는 선택입니다. pgvector가 없으면 `real[]` 컬럼으로 대신합니다(README 「사전 준비」). | 임베딩을 기본으로 함 |
| PostgreSQL | 이유 기록 없음. `axhub.yaml`의 `database.engine`이 postgres이고, Cloud SQL도 같은 방식입니다. | 기록 없음 |
| Vue 3, 해시 주소 | 이유 기록 없음. `App.vue` 주석에 「vue-router 없이 해시 기반 화면 전환」이라고만 적혀 있습니다. | 기록 없음 |
| 메신저 `mock`/`webhook`/`telegram` | 이유 기록 없음. 웹훅 주소가 없으면 `mock`으로 보내 `messenger_log` 테이블에만 남깁니다(`database.py` 주석). | 기록 없음 |
| 단일 컨테이너 | 루트 `Dockerfile` 주석: 「axhub 배포용: Vue 빌드 결과를 FastAPI static으로 묶은 단일 이미지」. | 화면과 서버를 따로 배포 |

## 지킬 것

- API 키와 토큰은 `.env`(git에 올리지 않음)나 axhub 비밀값에만 둡니다. 설정값 이름은 [architecture.md](../architecture/architecture.md)의 설정값 표에 있습니다.
- 시연 데이터는 가상 데이터만 씁니다([지킬 것](../../harness/ground-rules.md)).

## 아직 확인할 것

- 「이유 기록 없음」으로 남긴 항목은 개발 담당이 알려 주면 이 ADR에 채웁니다.

## 참고

- [ADR-006 아키텍처 에이전트](ADR-006-architect-agent.md)
- [ADR-010 제출 구현](ADR-010-submission-implementation.md)
- [architecture.md](../architecture/architecture.md)
