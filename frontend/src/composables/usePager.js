import { computed, ref, unref, watch } from 'vue'

// 목록 화면 공통 페이징 (화면에서 받은 목록을 15건씩 나눠 보여줌)
export const PAGE_SIZE = 15

export function usePager(source, size = PAGE_SIZE) {
  const page = ref(1)
  const total = computed(() => (unref(source) || []).length)
  const pages = computed(() => Math.max(1, Math.ceil(total.value / size)))
  const pageRows = computed(() => (unref(source) || []).slice((page.value - 1) * size, page.value * size))
  // 자동 갱신으로 건수가 줄면 마지막 페이지로 맞춤 (목록을 아직 못 받은 0건일 때는 기억한 페이지를 그대로 둠)
  watch([pages, total], ([n, t]) => { if (t && page.value > n) page.value = n })
  return { page, pages, total, size, pageRows, reset: () => { page.value = 1 } }
}
