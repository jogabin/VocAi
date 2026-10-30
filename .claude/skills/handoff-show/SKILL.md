---
name: handoff-show
description: 세션을 시작할 때 HANDOFF.md를 읽고, 지금 상태와 다음 할 일을 보여 준 뒤 오늘 무엇을 할지 묻습니다.
disable-model-invocation: true
---

# handoff-show

세션을 시작할 때 씁니다.  
읽기만 하고, 파일은 고치지 않습니다.

## 순서

1. 저장소 맨 위의 `HANDOFF.md`를 읽습니다.
2. 아래 순서로 짧게 보여 줍니다.
   - 마지막으로 고친 날짜(`updated`)
   - 현재 상태 (중요한 것만 3줄 이내)
   - 다음 할 일 (번호 그대로)
   - 확인할 것 (있으면)
3. "오늘은 몇 번부터 할까요?"라고 묻습니다.
4. 사용자가 고르기 전에는 작업을 시작하지 않습니다.

`HANDOFF.md`가 없으면, 없다고 말하고 `/handoff-write`로 새로 만들 수 있다고 안내합니다.
