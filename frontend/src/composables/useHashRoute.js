import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

// vue-router 없이 해시(#/stt?call=...) 기반으로 화면 전환
function parse() {
  const raw = window.location.hash.replace(/^#/, '')     // 주소가 없으면 '' → 권한 있는 첫 화면 (App.vue)
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

// 주소의 화면 부분을 지움 (로그아웃 시: 다시 로그인하면 첫 화면부터). 뒤로가기 기록은 남기지 않음
export function clearRoute() {
  history.replaceState(null, '', window.location.pathname + window.location.search)
  onChange()
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
