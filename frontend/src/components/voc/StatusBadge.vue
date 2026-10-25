<script setup>
import { computed } from 'vue'
const props = defineProps({ value: String })
const MAP = {
  관찰: 'badge-gray', 접수: 'badge-red', 확인중: 'badge-amber', 해결: 'badge-green', 오탐: 'badge-gray',
  RUNNING: 'badge-blue', DONE: 'badge-green', SKIPPED: 'badge-gray', FAILED: 'badge-red',
}
const LABEL = { RUNNING: '실행중', DONE: '완료', SKIPPED: '종료(미감지)', FAILED: '실패' }
const cls = computed(() => MAP[props.value] || 'badge-gray')
</script>

<template>
  <span class="badge" :class="cls">
    <span v-if="value === 'RUNNING'" class="dot pulse"></span>
    {{ LABEL[value] || value }}
  </span>
</template>
