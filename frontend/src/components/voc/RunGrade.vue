<script setup>
import SeverityBadge from './SeverityBadge.vue'

/* 에이전트 실행이 정한 등급 (상담현황 SCR-02 · 장애 알림 모니터 SCR-04 목록)
   등급이 있으면 등급 배지, 없으면 장애가 아닌 이유(개선의견 · 정상)나 진행 상태를 표시 */
defineProps({
  severity: { type: String, default: null },
  category: { type: String, default: null },
  status: { type: String, default: null },        // 실행 상태 (RUNNING · DONE · SKIPPED · FAILED), 실행이 없으면 null
})
</script>

<template>
  <SeverityBadge v-if="severity" :value="severity" />
  <span v-else-if="status === 'RUNNING'" class="badge badge-blue">판별 중</span>
  <span v-else-if="status === 'FAILED'" class="badge badge-red">실패</span>
  <span v-else-if="category === '개선의견'" class="badge badge-green">개선의견</span>
  <span v-else-if="status" class="badge badge-gray">정상</span>
  <span v-else class="muted">-</span>
</template>
