<script setup>
import { computed } from 'vue'
import { fmtOffset } from '../../utils/format'
// 화자 표시: 상담사는 'OOO 상담사', 고객은 이름 없이 '고객' (customerName 은 예전 호출 호환용으로 받기만 함)
const props = defineProps({ utterances: { type: Array, default: () => [] }, customerName: String, agentName: String })
const agentLabel = computed(() => {
  const name = (props.agentName || '').replace(/^상담사\s*|\s*상담사$/g, '').trim()
  return name ? `${name} 상담사` : '상담사'
})
</script>

<template>
  <div class="chat">
    <div v-for="u in utterances" :key="u.seq" class="msg" :class="u.speaker === 'AGENT' ? 'agent' : 'customer'">
      <div class="meta">
        <strong>{{ u.speaker === 'AGENT' ? agentLabel : '고객' }}</strong>
        <span>{{ fmtOffset(u.offset_sec) }}</span>
        <span v-if="u.added_by" class="added" :title="'관리자 추가: ' + u.added_by">추가</span>
      </div>
      <div class="bubble">{{ u.text }}</div>
    </div>
    <div v-if="!utterances.length" class="empty">STT 원문이 없습니다.</div>
  </div>
</template>

<style scoped>
.chat { display: flex; flex-direction: column; gap: 10px; }
.msg { display: flex; flex-direction: column; max-width: 82%; }
.msg.agent { align-self: flex-start; }
.msg.customer { align-self: flex-end; align-items: flex-end; }
.meta { display: flex; gap: 6px; font-size: 11.5px; color: var(--text-3); margin-bottom: 3px; }
.meta strong { color: var(--text-2); font-weight: 600; }
.meta .added { font-size: 10.5px; font-weight: 700; color: var(--warn); background: var(--warn-soft); border-radius: 4px; padding: 0 5px; }
.bubble { padding: 9px 12px; border-radius: var(--radius); font-size: 13.5px; line-height: 1.55; }
.agent .bubble { background: var(--surface-2); border: 1px solid var(--line); border-top-left-radius: 4px; }
.customer .bubble { background: var(--accent-soft); color: var(--navy); border-top-right-radius: 4px; }
</style>
