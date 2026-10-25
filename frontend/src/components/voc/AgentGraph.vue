<script setup>
import { computed } from 'vue'

// LangGraph 그래프(app/agents/graph.py)와 같은 구조의 흐름도. run 을 넘기면 실행 경로를 하이라이트
const props = defineProps({ run: { type: Object, default: null } })

const NAME_TO_NODE = {
  '장애감지 에이전트': 'detect',
  '중복제보 통합 에이전트': 'dedup',
  '심각도 판별 에이전트': 'severity',
  '담당자식별·알림 에이전트': 'notify',
  '메신저 전송 에이전트': 'notify',
  '장애이력 등록': 'record',
}

const NODES = {
  start:    { x: 40,  y: 140, label: 'START', kind: 'terminal' },
  detect:   { x: 170, y: 140, label: '장애감지', sub: 'STT · 상담이력 분석' },
  dedup:    { x: 370, y: 140, label: '중복제보 통합', sub: '60분 · 유사도' },
  severity: { x: 570, y: 140, label: '심각도 판별', sub: '판별기준 → 오탐 대조' },
  notify:   { x: 780, y: 62,  label: '메신저 전송', sub: '1차 · 2차 수신자' },
  record:   { x: 780, y: 218, label: '장애이력 등록', sub: '메신저 미발송' },
  end:      { x: 930, y: 140, label: 'END', kind: 'terminal' },
}
const W = 128
const H = 54

const EDGES = [
  { from: 'start', to: 'detect' },
  { from: 'detect', to: 'dedup', label: '장애 감지' },
  { from: 'detect', to: 'end', label: '장애 아님', bottom: true },
  { from: 'dedup', to: 'severity' },
  { from: 'severity', to: 'notify', label: '알림 대상' },
  { from: 'severity', to: 'record', label: '미대상 · 오탐' },
  { from: 'notify', to: 'end' },
  { from: 'record', to: 'end' },
]

const steps = computed(() => (props.run?.steps || []).map((s) => ({
  ...s, node: s.output?.node || NAME_TO_NODE[s.agent_name],
})))
const finished = computed(() => props.run && props.run.status !== 'RUNNING')
const path = computed(() => {
  if (!props.run) return []
  const p = ['start', ...steps.value.map((s) => s.node)]
  if (finished.value && props.run.status !== 'FAILED') p.push('end')
  return p
})
const nodeState = (id) => {
  if (!props.run) return 'idle'
  if (id === 'start') return 'done'
  if (id === 'end') return path.value.includes('end') ? 'done' : 'idle'
  const s = steps.value.find((x) => x.node === id)
  if (!s) return 'idle'
  return { RUNNING: 'running', DONE: 'done', SKIPPED: 'done', FAILED: 'failed' }[s.status] || 'idle'
}
const edgeOn = (e) => {
  const i = path.value.indexOf(e.from)
  return i >= 0 && path.value[i + 1] === e.to
}

function anchor(id, side) {
  const n = NODES[id]
  const w = n.kind === 'terminal' ? 26 : W / 2
  if (side === 'right') return [n.x + w, n.y]
  if (side === 'left') return [n.x - w, n.y]
  if (side === 'bottom') return [n.x, n.y + (n.kind === 'terminal' ? 18 : H / 2)]
  return [n.x, n.y]
}
function edgePath(e) {
  if (e.bottom) {
    const [x1, y1] = anchor(e.from, 'bottom')
    const [x2, y2] = anchor(e.to, 'bottom')
    return { d: `M${x1},${y1} L${x1},282 L${x2},282 L${x2},${y2 + 2}`, lx: (x1 + x2) / 2, ly: 276 }
  }
  const [x1, y1] = anchor(e.from, 'right')
  const [x2, y2] = anchor(e.to, 'left')
  const mx = (x1 + x2) / 2
  const d = y1 === y2 ? `M${x1},${y1} L${x2 - 2},${y2}` : `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2 - 2},${y2}`
  return { d, lx: mx, ly: (y1 + y2) / 2 + (y2 < y1 ? -12 : y2 > y1 ? 20 : -8) }
}
const edges = computed(() => EDGES.map((e) => ({ ...e, ...edgePath(e), on: edgeOn(e) })))
</script>

<template>
  <svg class="agent-graph" viewBox="0 0 970 300" role="img" aria-label="LangGraph 에이전트 흐름도">
    <defs>
      <marker id="ag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" class="arrow-off" />
      </marker>
      <marker id="ag-arrow-on" viewBox="0 0 10 10" refX="9" refY="5" markerUnits="userSpaceOnUse" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" class="arrow-on" />
      </marker>
    </defs>

    <g v-for="(e, i) in edges" :key="'e' + i">
      <path :d="e.d" class="edge" :class="{ on: e.on }" :marker-end="e.on ? 'url(#ag-arrow-on)' : 'url(#ag-arrow)'" />
      <text v-if="e.label" :x="e.lx" :y="e.ly" class="edge-label" :class="{ on: e.on }" text-anchor="middle">{{ e.label }}</text>
    </g>

    <g v-for="(n, id) in NODES" :key="id" class="node" :class="['st-' + nodeState(id), n.kind]">
      <template v-if="n.kind === 'terminal'">
        <rect :x="n.x - 26" :y="n.y - 16" width="52" height="32" rx="16" />
        <text :x="n.x" :y="n.y + 4" text-anchor="middle" class="t-label">{{ n.label }}</text>
      </template>
      <template v-else>
        <rect :x="n.x - W / 2" :y="n.y - H / 2" :width="W" :height="H" rx="10" />
        <text :x="n.x" :y="n.y - 3" text-anchor="middle" class="label">{{ n.label }}</text>
        <text :x="n.x" :y="n.y + 14" text-anchor="middle" class="sub">{{ n.sub }}</text>
      </template>
    </g>
  </svg>
</template>

<style scoped>
.agent-graph { width: 100%; max-width: 980px; height: auto; display: block; margin: 0 auto; font-family: var(--font); }
.edge { fill: none; stroke: var(--line-strong); stroke-width: 1.6; }
.edge.on { stroke: var(--accent); stroke-width: 2.6; }
.arrow-off { fill: var(--line-strong); }
.arrow-on { fill: var(--accent); }
.edge-label { font-size: 11.5px; fill: var(--text-3); font-weight: 600; paint-order: stroke; stroke: var(--surface); stroke-width: 4px; }
.edge-label.on { fill: var(--accent); }
.node rect { fill: var(--surface); stroke: var(--line-strong); stroke-width: 1.5; stroke-dasharray: 4 3; transition: all .2s; }
.node .label { font-size: 13.5px; font-weight: 700; fill: var(--text-2); }
.node .sub { font-size: 11px; fill: var(--text-3); }
.node .t-label { font-size: 11px; font-weight: 700; fill: var(--text-3); letter-spacing: .04em; }
.st-done rect { fill: var(--ok-soft); stroke: var(--ok); stroke-dasharray: none; }
.st-done .label, .st-done .t-label { fill: var(--ok); }
.st-running rect { fill: var(--accent-soft); stroke: var(--accent); stroke-width: 2.4; stroke-dasharray: none; animation: glow 1s ease-in-out infinite; }
.st-running .label { fill: var(--accent); }
.st-failed rect { fill: var(--p1-soft); stroke: var(--p1); stroke-dasharray: none; }
.terminal.st-idle rect { fill: var(--surface-2); }
.st-idle:not(.terminal) rect { fill: var(--surface); }
@keyframes glow { 0%, 100% { stroke-opacity: 1; } 50% { stroke-opacity: .35; } }
</style>
