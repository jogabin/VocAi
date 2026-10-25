"""LangGraph 기반 장애 알림 에이전트 그래프

            ┌──────────┐  장애 아님   ┌─────┐
  START ──▶ │ 장애감지  │ ───────────▶ │ END │
            └────┬─────┘              └─────┘
                 │ 장애 감지                ▲
            ┌────▼─────┐                    │
            │ 중복통합  │                    │
            └────┬─────┘                    │
            ┌────▼─────┐  알림 대상  ┌──────┴──────┐
            │ 심각도판별 │ ─────────▶ │  메신저 전송   │
            └────┬─────┘            └─────────────┘
                 │ 미대상/오탐       ┌─────────────┐
                 └─────────────────▶ │  장애이력 등록  │ ──▶ END
                                     └─────────────┘

각 노드는 실행 시작/종료를 agent_step 테이블에 커밋하므로 모니터 화면에서 실시간으로 볼 수 있습니다.
"""
import time
from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import dedup, detection, notify, severity
from app.database import settings
from app.services import repo


class AgentState(TypedDict, total=False):
    consult: dict                 # 등록된 상담이력
    call: dict | None             # STT 원문
    customer_text: str            # 고객 발화 모음
    detection: dict               # ① 장애감지 결과
    dedup: dict                   # ② 중복통합 결과
    severity: dict                # ③ 심각도판별 결과
    notify: dict                  # ④ 등록/알림 결과
    incident_id: int | None
    llm_used: bool
    path: list[str]               # 실행된 노드 순서 (흐름도 하이라이트용)
    status: str                   # DONE / SKIPPED
    outcome: str                  # 마지막 단계 메시지


# 노드 ID → (에이전트 함수, 화면 표시명, 실행 중 메시지)
NODES: dict[str, tuple[Callable, str, str]] = {
    "detect":   (detection.run,   detection.NAME,   "STT 원문 분석 · 상담이력 분석 후 장애 여부 종합 판정 중"),
    "dedup":    (dedup.run,       dedup.NAME,       "최근 60분 동일 유형 장애와 유사도 비교 중"),
    "severity": (severity.run,    severity.NAME,    "1차 판별기준 알림 대상 판정 → 2차 과거 오탐 사례 대조 중"),
    "notify":   (notify.run,      notify.NAME,      "1차·2차 수신자 식별 · 알림 템플릿 작성 · 메신저 전송 중"),
    "record":   (notify.run_record, notify.RECORD_NAME, "장애알림 정보 등록 중 (메신저 미발송)"),
}


def _make_node(node_id: str, db, run_id: int) -> Callable[[AgentState], dict]:
    fn, name, running_msg = NODES[node_id]

    def node(state: AgentState) -> dict[str, Any]:
        path = list(state.get("path", [])) + [node_id]
        step_id = repo.start_step(db, run_id, len(path), name, running_msg)
        db.commit()
        if settings.agent_step_delay_sec > 0:
            time.sleep(settings.agent_step_delay_sec)

        ctx = dict(state)                       # 에이전트는 ctx 에 결과를 기록
        st, msg, out = fn(db, ctx)
        out = {**out, "node": node_id}
        repo.finish_step(db, step_id, st, msg, out)
        db.commit()

        update = {k: v for k, v in ctx.items() if k != "path"}
        update.update(path=path, outcome=msg, status="SKIPPED" if st == "SKIPPED" else "DONE")
        return update

    return node


# ---------- 조건 분기 ----------
def route_after_detect(state: AgentState) -> str:
    return "incident" if state["detection"]["is_incident"] else "normal"


def route_after_severity(state: AgentState) -> str:
    return "notify" if state["severity"]["notify"] else "record"


def build_graph(db=None, run_id: int = 0):
    g = StateGraph(AgentState)
    for node_id in NODES:
        g.add_node(node_id, _make_node(node_id, db, run_id))

    g.add_edge(START, "detect")
    g.add_conditional_edges("detect", route_after_detect, {"incident": "dedup", "normal": END})
    g.add_edge("dedup", "severity")
    g.add_conditional_edges("severity", route_after_severity, {"notify": "notify", "record": "record"})
    g.add_edge("notify", END)
    g.add_edge("record", END)
    return g.compile()


# 흐름도 정의 (프론트 화면/발표용). LangGraph 의 draw_mermaid() 결과도 함께 제공
GRAPH_SPEC = {
    "nodes": [{"id": k, "label": v[1]} for k, v in NODES.items()],
    "edges": [
        {"from": "__start__", "to": "detect"},
        {"from": "detect", "to": "dedup", "label": "장애 감지"},
        {"from": "detect", "to": "__end__", "label": "장애 아님"},
        {"from": "dedup", "to": "severity"},
        {"from": "severity", "to": "notify", "label": "알림 대상"},
        {"from": "severity", "to": "record", "label": "미대상·오탐"},
        {"from": "notify", "to": "__end__"},
        {"from": "record", "to": "__end__"},
    ],
}


def mermaid() -> str:
    try:
        return build_graph().get_graph().draw_mermaid()
    except Exception:
        lines = ["graph TD"]
        names = {"__start__": "START", "__end__": "END", **{n["id"]: n["label"] for n in GRAPH_SPEC["nodes"]}}
        for e in GRAPH_SPEC["edges"]:
            arrow = f"-- {e['label']} -->" if e.get("label") else "-->"
            lines.append(f"    {e['from']}[{names[e['from']]}] {arrow} {e['to']}[{names[e['to']]}]")
        return "\n".join(lines)
