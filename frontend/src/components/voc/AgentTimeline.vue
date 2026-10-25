<script setup>
import StatusBadge from './StatusBadge.vue'

const props = defineProps({ run: { type: Object, required: true }, compact: Boolean })

// LangGraph 실행 경로에 따라 실제 실행된 노드만 표시 (실행 중이면 다음 단계 대기 행 추가)
function stepsWithPending() {
  const steps = [...(props.run.steps || [])]
  if (props.run.status === 'RUNNING' && !steps.some((s) => s.status === 'RUNNING')) {
    steps.push({ seq: steps.length + 1, agent_name: '다음 노드', status: 'WAIT', message: '그래프 분기 결정 후 실행' })
  }
  if (!steps.length) steps.push({ seq: 1, agent_name: '장애감지 에이전트', status: 'WAIT', message: '대기' })
  return steps
}
</script>

<template>
  <ol class="timeline" :class="{ compact }">
    <li v-for="s in stepsWithPending()" :key="s.seq" :class="'st-' + s.status.toLowerCase()">
      <span class="node">
        <span v-if="s.status === 'DONE'">✓</span>
        <span v-else-if="s.status === 'RUNNING'" class="spin"></span>
        <span v-else-if="s.status === 'FAILED'">!</span>
        <span v-else-if="s.status === 'SKIPPED'">–</span>
        <span v-else>{{ s.seq }}</span>
      </span>
      <div class="content">
        <div class="title">
          <strong>{{ s.agent_name }}</strong>
          <StatusBadge v-if="['RUNNING', 'DONE', 'SKIPPED', 'FAILED'].includes(s.status)" :value="s.status" />
          <span v-if="s.elapsed_ms != null && s.status !== 'RUNNING'" class="ms">{{ (s.elapsed_ms / 1000).toFixed(1) }}s</span>
        </div>
        <p class="msg">{{ s.message }}</p>
        <div v-if="!compact && s.output && s.output.stt_analysis" class="sub-analysis">
          <span :class="s.output.stt_analysis.is_incident ? 'hit' : 'miss'">STT 원문 · {{ s.output.stt_analysis.is_incident ? '장애' : '정상' }}</span>
          <em>{{ s.output.stt_analysis.reason }}</em>
          <span :class="s.output.consult_analysis.is_incident ? 'hit' : 'miss'">상담이력 · {{ s.output.consult_analysis.is_incident ? '장애' : '정상' }}</span>
          <em>{{ s.output.consult_analysis.reason }}</em>
        </div>
      </div>
    </li>
  </ol>
</template>

<style scoped>
.timeline { list-style: none; margin: 0; padding: 0; position: relative; }
.timeline li { display: grid; grid-template-columns: 28px 1fr; gap: 10px; position: relative; padding-bottom: 14px; }
.timeline li:not(:last-child)::before { content: ''; position: absolute; left: 13px; top: 28px; bottom: 0; width: 2px; background: var(--line); }
.timeline li.st-done:not(:last-child)::before { background: #b9dcc9; }
.node { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-size: 12px; font-weight: 700; background: var(--surface-2); border: 2px solid var(--line-strong); color: var(--text-3); }
.st-done .node { background: var(--ok); border-color: var(--ok); color: #fff; }
.st-running .node { border-color: var(--accent); background: var(--accent-soft); }
.st-failed .node { background: var(--p1); border-color: var(--p1); color: #fff; }
.st-skipped .node { background: var(--p4-soft); border-color: var(--p4); color: var(--p4); }
.st-na .node, .st-wait .node { border-style: dashed; }
.content { padding-top: 3px; min-width: 0; }
.title { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.ms { font-size: 11px; color: var(--text-3); font-family: var(--mono); }
.msg { margin: 3px 0 0; font-size: 12.5px; color: var(--text-2); word-break: keep-all; }
.st-na .msg, .st-wait .msg { color: var(--text-3); }
.sub-analysis { display: grid; grid-template-columns: auto 1fr; gap: 4px 8px; align-items: baseline; margin-top: 6px; font-size: 12px; }
.sub-analysis span { font-weight: 700; padding: 1px 7px; border-radius: 6px; white-space: nowrap; }
.sub-analysis .hit { background: var(--p2-soft); color: var(--p2); }
.sub-analysis .miss { background: var(--p4-soft); color: var(--p4); }
.sub-analysis em { font-style: normal; color: var(--text-3); word-break: keep-all; }
.compact li { padding-bottom: 8px; }
.compact .msg { font-size: 12px; }
.spin { width: 12px; height: 12px; border: 2px solid var(--accent); border-right-color: transparent; border-radius: 50%; animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
