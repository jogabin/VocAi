<script setup>
import { SEVERITY_LABEL } from '../../utils/format'
defineProps({ value: { type: String, default: 'P3' }, short: Boolean })
</script>

<template>
  <span class="sev" :class="'sev-' + (value || 'P4').toLowerCase()">
    {{ value }}<template v-if="!short"> {{ SEVERITY_LABEL[value] }}</template>
  </span>
</template>

<style scoped>
.sev { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 6px; font-size: 11.5px; font-weight: 700; white-space: nowrap; letter-spacing: .01em; }
.sev-p1 { background: var(--p1); color: #fff; }
.sev-p2 { background: var(--p2-soft); color: var(--p2); }
.sev-p3 { background: var(--p3-soft); color: var(--p3); }
.sev-p4 { background: var(--p4-soft); color: var(--p4); }
</style>
