# .claude

Claude Code가 이 저장소에서 쓰는 설정입니다. 서비스 코드(`backend/`, `frontend/`)와는 상관없고, 요건과 설계 문서를 만들 때 쓴 개발 에이전트와 그 약속을 담고 있습니다.
흐름과 이유는 [SDD 한눈에 보기](../docs/guide/sdd.md)에 있습니다. 서비스 안에서 장애를 찾는 AI 에이전트와는 다른 것입니다.

## skills/ — 개발 에이전트

사람이 `/이름`으로 부릅니다. 폴더마다 `SKILL.md`가 설명서이고, `template*.md`가 문서 틀입니다.

| 폴더 | 부르는 법 | 하는 일 | 남기는 문서 |
|---|---|---|---|
| `sdd-interviewer` | `/sdd-interviewer` | 만들려는 것과 참고 자료를 질문으로 확인해 범위를 정합니다 | `docs/requirements/scope.md` |
| `sdd-analyst` | `/sdd-analyst` | 확정된 범위를 읽고 화면 탭별 요건을 업무 말로 씁니다 | `docs/requirements/requirements.md`, `tabs/` |
| `sdd-architect` | `/sdd-architect` | 요건을 읽고 여러 탭이 같이 쓰는 것(구조, AI 판단 흐름, 큰 기술 선택)을 정합니다 | `docs/architecture/architecture.md` |
| `sdd-designer` | `/sdd-designer` | 요건과 참고 디자인을 읽고 화면 규칙과 시안을 정합니다 | `docs/design/style-guide.md` |
| `handoff-write` | `/handoff-write` | 세션을 끝낼 때 한 일과 다음 할 일을 `HANDOFF.md`에 반영합니다 | `HANDOFF.md` |
| `handoff-show` | `/handoff-show` | 세션을 시작할 때 `HANDOFF.md`를 읽고 지금 상태를 보여 줍니다 | - |

`handoff-*` 두 개는 작업 상태를 다음 세션에 넘기는 보조 스킬이며, 이 저장소에는 아직 `HANDOFF.md`가 없습니다.
정했지만 만들지 않은 개발 에이전트 6개(스펙, 구현 계획, 백엔드·프론트 구현, 코드 리뷰, QA)의 이유는 [ADR-009](../docs/adr/ADR-009-build-without-spec-agents.md)에 있습니다.

## rules/

| 파일 | 내용 |
|---|---|
| `sdd.md` | 개발 에이전트가 묻는 방식과 문서를 잇는 약속. 선택지로 묻기, 문서 맨 위의 상태(작성 중 → 확인 대기 → 확정), 확정은 사람이 말할 때만 하기, 앞 단계 문서가 바뀌었을 때의 처리 |
