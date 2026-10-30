# 콜록 홈즈 (VocAi)

상담 이력에서 웹·앱 장애를 찾아 IT 담당자에게 알리는 AI 에이전트입니다. 서버는 FastAPI + LangGraph, 화면은 Vue 3입니다.  
소개와 폴더 구조, 실행 방법은 [README.md](README.md)에 있습니다.

대화와 문서는 한국어로 씁니다.

## 지킬 것

@harness/ground-rules.md

## 어디에 무엇이 있나

- 코드: 서버 `backend/`, 화면 `frontend/`. 구조와 동작은 [아키텍처](docs/architecture/architecture.md)에 먼저 읽을 곳이 정리돼 있습니다.
- 개발 문서 전체와 읽는 순서: [docs/README.md](docs/README.md)
- 개발 흐름과 개발 에이전트 한눈에 보기: [docs/guide/sdd.md](docs/guide/sdd.md)  
  단계나 에이전트(스킬)에 관해 물으면 이 문서부터 읽고 답합니다.
- 대화형 개발 에이전트(인터뷰, 요건정리, 아키텍처, 디자인): `.claude/skills/`
- 에이전트 사이의 약속: [.claude/rules/sdd.md](.claude/rules/sdd.md)
- 결정 기록: `docs/adr/` (목록은 [docs/adr/README.md](docs/adr/README.md))
- 요건: `docs/requirements/`. 이 요건을 제출 코드가 얼마나 구현했는지는 [요건 대비 구현 현황](docs/requirements/vocai-status.md)에 있습니다.

## 코드를 고칠 때

- 코드를 읽지 않고 문서만 보고 답하지 않습니다. 문서와 코드가 다르면 코드가 맞고, 다른 곳을 알려 줍니다.
- `main`에 push하면 axhub가 자동으로 다시 배포합니다. 배포를 바꾸고 싶지 않은 변경(문서 등)이라도 push 전에 확인합니다.
- 구조나 방식을 새로 정하면 `docs/adr/`에 ADR을 하나 추가하고 목록도 같이 고칩니다.
