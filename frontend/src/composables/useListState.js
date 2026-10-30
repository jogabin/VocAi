import { watch } from 'vue'

// 목록 화면의 검색조건 · 정렬 · 페이지를 화면별로 기억 (상세로 들어갔다 뒤로 와도 그대로)
// 브라우저 탭을 닫으면 사라지고(sessionStorage), 로그아웃하면 clearListState 로 모두 지움
const KEY = 'voc_list_state'
let store = {}
try { store = JSON.parse(sessionStorage.getItem(KEY) || '{}') || {} } catch { store = {} }

function save() {
  try { sessionStorage.setItem(KEY, JSON.stringify(store)) } catch { /* 저장 불가(사생활 보호 모드 등) → 이번 방문 동안만 기억 */ }
}

export function listState(name) {
  return store[name] || {}
}

// refs: { 이름: ref } — 저장된 값으로 되돌린 뒤 바뀔 때마다 저장
// restoreKeys: 되돌릴 이름 (기본: 전부). 주소로 받은 값처럼 되돌리면 안 되는 값은 빼고 넘김
// 페이지를 처음으로 돌리는 watch 보다 먼저 불러야 되돌린 값 때문에 페이지가 1로 돌아가지 않음
export function keepListState(name, refs, restoreKeys = Object.keys(refs)) {
  const saved = store[name] || {}
  for (const k of restoreKeys) {
    if (k in saved && refs[k]) refs[k].value = saved[k]
  }
  const snapshot = () => Object.fromEntries(Object.entries(refs).map(([k, r]) => [k, r.value]))
  store[name] = snapshot()
  save()
  watch(Object.values(refs), () => { store[name] = snapshot(); save() }, { deep: true })
}

export function clearListState() {
  store = {}
  try { sessionStorage.removeItem(KEY) } catch { /* 없음 */ }
}
