// 로그인 토큰 보관 (새로고침해도 로그인 유지). 브라우저 저장소를 못 쓰는 환경이면 메모리에만 보관
const KEY = 'voc.auth.token'
let memory = null
let onUnauthorized = null

export function getToken() {
  try { return localStorage.getItem(KEY) || memory } catch { return memory }
}

export function setToken(token) {
  memory = token
  try { localStorage.setItem(KEY, token) } catch { /* 저장 불가 환경 */ }
}

export function clearToken() {
  memory = null
  try { localStorage.removeItem(KEY) } catch { /* 저장 불가 환경 */ }
}

// 세션 만료(401) 시 호출할 함수 등록 (useAuth 에서 등록)
export function setUnauthorizedHandler(fn) { onUnauthorized = fn }
export function notifyUnauthorized(message) { if (onUnauthorized) onUnauthorized(message) }
