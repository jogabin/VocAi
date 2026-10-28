import { computed, reactive } from 'vue'
import { fetchMe, login as apiLogin, logout as apiLogout } from '../api/authApi'
import { clearToken, getToken, setToken, setUnauthorizedHandler } from '../api/authToken'

// 앱 전체에서 공유하는 로그인 상태
const state = reactive({
  ready: false,      // 저장된 토큰 확인 완료 여부
  user: null,        // 로그인 사용자
  notice: '',        // 로그인 화면에 보여줄 안내 (세션 만료 등)
})

setUnauthorizedHandler((message) => {
  if (!state.user) return
  clearToken()
  state.user = null
  state.notice = message || '로그인 세션이 만료되었습니다. 다시 로그인하세요.'
})

async function restore() {
  if (state.ready) return
  if (getToken()) {
    try {
      const { user } = await fetchMe()
      state.user = user
    } catch {
      clearToken()
    }
  }
  state.ready = true
}

async function login(loginId, password) {
  const { token, user } = await apiLogin(loginId, password)
  setToken(token)
  state.user = user
  state.notice = ''
  return user
}

async function logout() {
  try { await apiLogout() } catch { /* 이미 만료된 세션 */ }
  clearToken()
  state.user = null
  state.notice = '로그아웃했습니다.'
}

/* 권한(auth_role) 4종 — 화면 설계서 SCR-01~10 기준
   IT담당자 = 장애 알림을 받아 장애를 처리하는 사용자 (장애 처리 등록은 IT담당자 권한만) */
export const ROLES = ['상담사', '센터관리자', 'IT담당자', '시스템관리자']
export const ROLE_ALL = ROLES
export const ROLE_CONSULT = ['상담사', '센터관리자', '시스템관리자']   // SCR-02, SCR-03
export const ROLE_CRITERIA = ['시스템관리자']                         // SCR-08 판별기준 관리
export const ROLE_SYS = ['시스템관리자']                              // SCR-06, 07, 09, 10

const role = computed(() => state.user?.auth_role || '')
const hasRole = (roles) => !roles || roles.includes(role.value)
const isSysAdmin = computed(() => role.value === '시스템관리자')
const isManager = computed(() => ['센터관리자', '시스템관리자'].includes(role.value))   // 관찰 장애 수동 알림 · 종결
const isItStaff = computed(() => role.value === 'IT담당자' || state.user?.user_id == null && state.user?.login_id === 'dev')

export function useAuth() {
  return { state, role, hasRole, isSysAdmin, isManager, isItStaff, restore, login, logout }
}
