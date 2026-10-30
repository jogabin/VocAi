<script setup>
import { computed } from 'vue'

// 목록 아래 페이지 이동 (usePager 와 함께 사용: <ListPager v-model:page="page" :pages="pages" :total="total" :size="size" />)
const props = defineProps({
  page: { type: Number, required: true },
  pages: { type: Number, required: true },
  total: { type: Number, required: true },
  size: { type: Number, default: 15 },
})
const emit = defineEmits(['update:page'])

// 현재 페이지 앞뒤로 최대 10개 번호
const numbers = computed(() => {
  const start = Math.max(1, Math.min(props.page - 4, props.pages - 9))
  const end = Math.min(props.pages, start + 9)
  return Array.from({ length: end - start + 1 }, (_, i) => start + i)
})
const from = computed(() => (props.page - 1) * props.size + 1)
const to = computed(() => Math.min(props.total, props.page * props.size))

function go(n) {
  if (n >= 1 && n <= props.pages && n !== props.page) emit('update:page', n)
}
</script>

<template>
  <div v-if="total" class="pager">
    <span class="info">총 {{ total }}건 · {{ from }}-{{ to }}</span>
    <div v-if="pages > 1" class="nums">
      <button type="button" :disabled="page === 1" title="처음" @click="go(1)">«</button>
      <button type="button" :disabled="page === 1" title="이전" @click="go(page - 1)">‹</button>
      <button v-for="n in numbers" :key="n" type="button" :class="{ on: n === page }" @click="go(n)">{{ n }}</button>
      <button type="button" :disabled="page === pages" title="다음" @click="go(page + 1)">›</button>
      <button type="button" :disabled="page === pages" title="마지막" @click="go(pages)">»</button>
    </div>
  </div>
</template>

<style scoped>
.pager { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px 22px; border-top: 1px solid var(--line); flex-wrap: wrap; }
.info { font-size: 12px; color: var(--text-3); }
.nums { display: flex; gap: 4px; }
.nums button { font: inherit; font-size: 12.5px; min-width: 30px; height: 30px; padding: 0 8px; border: 0; border-radius: var(--radius-badge); background: none; color: var(--text-2); cursor: pointer; }
.nums button:hover:not(:disabled) { background: var(--line); color: var(--text); }
.nums button.on { background: var(--accent-soft); color: var(--accent); font-weight: 700; }
.nums button:disabled { color: var(--line-strong); cursor: default; }
</style>
