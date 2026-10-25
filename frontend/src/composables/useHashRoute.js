import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

// vue-router 없이 해시(#/stt?call=...) 기반으로 화면 전환
function parse() {
  const raw = window.location.hash.replace(/^#/, '') || '/stt'
  const [path, qs = ''] = raw.split('?')
  return { path, query: Object.fromEntries(new URLSearchParams(qs)) }
}

const route = ref(parse())
let listeners = 0
const onChange = () => { route.value = parse() }

export function navigate(path, query = {}) {
  const qs = new URLSearchParams(Object.entries(query).filter(([, v]) => v != null && v !== '')).toString()
  window.location.hash = qs ? `${path}?${qs}` : path
}

export function useHashRoute() {
  onMounted(() => { if (listeners++ === 0) window.addEventListener('hashchange', onChange) })
  onBeforeUnmount(() => { if (--listeners === 0) window.removeEventListener('hashchange', onChange) })
  return {
    route,
    path: computed(() => route.value.path),
    query: computed(() => route.value.query),
    navigate,
  }
}
