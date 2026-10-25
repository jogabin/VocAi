<script setup>
import { computed, onMounted } from 'vue'
import { useHashRoute } from './composables/useHashRoute'
import { useAuth, ROLE_ALL, ROLE_CONSULT, ROLE_CRITERIA, ROLE_SYS } from './composables/useAuth'
import LoginView from './views/LoginView.vue'
import ConsultStatusView from './views/ConsultStatusView.vue'
import ConsultRegisterView from './views/ConsultRegisterView.vue'
import IncidentMonitorView from './views/IncidentMonitorView.vue'
import IncidentDetailView from './views/IncidentDetailView.vue'
import CriteriaView from './views/CriteriaView.vue'
import UserAdminView from './views/UserAdminView.vue'
import EmployeeView from './views/EmployeeView.vue'
import CustomerView from './views/CustomerView.vue'
import ConsultDataView from './views/ConsultDataView.vue'
import ApiTestView from './views/ApiTestView.vue'

// vue-router 없이 해시 기반 화면 전환 (#/stt, #/consult, #/monitor, #/incident, #/criteria, #/users, #/employees, #/customers, #/consult-data)
// 로그인 전에는 어느 주소로 들어와도 로그인 화면을 보여주고, 로그인하면 원래 주소의 화면을 엽니다.
const { path } = useHashRoute()
const auth = useAuth()

// 화면 권한 (화면 설계서 SCR-01~10): roles = 사용할 수 있는 권한(auth_role)
const MENUS = [
  { id: 'SCR-02', path: '/stt', label: '상담현황', view: ConsultStatusView, roles: ROLE_CONSULT },
  // 상담이력등록: 상단 메뉴에서 숨김, 상담현황 목록에서 상담을 클릭해 진입 (#/consult?call=CALL-xxxx)
  { id: 'SCR-03', path: '/consult', label: '상담이력등록', view: ConsultRegisterView, roles: ROLE_CONSULT, hidden: true, parent: '/stt' },
  { id: 'SCR-04', path: '/monitor', label: '장애 알림 모니터', view: IncidentMonitorView, roles: ROLE_ALL },
  // 장애 상세정보: 모니터 목록 · 메신저 알림 링크(#/incident?id=N)로 진입
  { id: 'SCR-05', path: '/incident', label: '장애 상세정보', view: IncidentDetailView, roles: ROLE_ALL, hidden: true, parent: '/monitor' },
  { id: 'SCR-06', path: '/users', label: '사용자관리', view: UserAdminView, roles: ROLE_SYS },
  { id: 'SCR-07', path: '/employees', label: '인사정보 관리', view: EmployeeView, roles: ROLE_SYS },
  { id: 'SCR-08', path: '/criteria', label: '판별기준 관리', view: CriteriaView, roles: ROLE_CRITERIA },
  { id: 'SCR-09', path: '/customers', label: '고객정보 관리', view: CustomerView, roles: ROLE_SYS },
  { id: 'SCR-10', path: '/consult-data', label: '상담데이터 등록', view: ConsultDataView, roles: ROLE_SYS },
  { path: '/api-test', label: 'API 테스트', view: ApiTestView, roles: ROLE_SYS, hidden: true },   // 메뉴에서 숨김 (주소로만 접근)
]
const allowedMenus = computed(() => MENUS.filter((m) => auth.hasRole(m.roles)))
const visibleMenus = computed(() => allowedMenus.value.filter((m) => !m.hidden))
// 주소가 없거나 모르는 주소면 권한 있는 첫 화면 (IT담당자 → 장애 알림 모니터)
const current = computed(() => MENUS.find((m) => m.path === path.value) || visibleMenus.value[0] || MENUS[0])
const denied = computed(() => !auth.hasRole(current.value.roles))

const userLabel = computed(() => {
  const u = auth.state.user
  if (!u) return ''
  return [u.auth_role, u.emp_group && u.emp_group !== u.auth_role ? u.emp_group : null].filter(Boolean).join(' · ')
})

onMounted(auth.restore)
</script>

<template>
  <div v-if="!auth.state.ready" class="boot">불러오는 중…</div>

  <LoginView v-else-if="!auth.state.user" />

  <template v-else>
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <span class="logo">V</span>
          <div>
            <strong>VOC 장애 알림 AI Agent</strong>
            <small>상담이력 기반 자율형 장애 감지 · 알림</small>
          </div>
        </div>
        <nav>
          <a v-for="m in visibleMenus" :key="m.path" :href="'#' + m.path"
             :class="{ on: current.path === m.path || current.parent === m.path }">{{ m.label }}</a>
        </nav>
        <div class="user">
          <div class="who">
            <strong>{{ auth.state.user.user_name }}</strong>
            <small>{{ userLabel || auth.state.user.login_id }}</small>
          </div>
          <button class="logout" title="로그아웃" @click="auth.logout">로그아웃</button>
        </div>
      </div>
    </header>

    <div v-if="denied" class="page">
      <div class="card"><div class="empty">
        {{ current.label }} 화면은 {{ current.roles.join(' · ') }} 권한만 사용할 수 있습니다.
        <span v-if="visibleMenus.length"><br><a :href="'#' + visibleMenus[0].path">{{ visibleMenus[0].label }}(으)로 이동</a></span>
      </div></div>
    </div>
    <component :is="current.view" v-else :key="current.path" />
  </template>
</template>

<style>
.boot { min-height: 100vh; display: grid; place-items: center; color: var(--text-3); font-size: 13px; }
.topbar { background: #111827; color: #fff; position: sticky; top: 0; z-index: 20; }
.topbar-inner { max-width: 1440px; margin: 0 auto; padding: 0 24px; height: 56px; display: flex; align-items: center; gap: 28px; }
.brand { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.brand .logo { width: 30px; height: 30px; border-radius: 8px; background: linear-gradient(135deg, #3b6cff, #7c4dff); display: grid; place-items: center; font-weight: 800; }
.brand strong { display: block; font-size: 14px; letter-spacing: -0.01em; }
.brand small { display: block; font-size: 11px; color: #9ca3af; }
.topbar nav { display: flex; gap: 2px; height: 100%; overflow-x: auto; scrollbar-width: none; }
.topbar nav a { color: #cbd5e1; display: flex; align-items: center; padding: 0 12px; font-weight: 600; font-size: 13.5px; border-bottom: 2px solid transparent; text-decoration: none; white-space: nowrap; }
.topbar nav a:hover { color: #fff; background: rgba(255, 255, 255, .04); }
.topbar nav a.on { color: #fff; border-bottom-color: #5b8cff; }
.topbar .user { margin-left: auto; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.topbar .who { text-align: right; line-height: 1.25; }
.topbar .who strong { display: block; font-size: 13px; }
.topbar .who small { display: block; font-size: 11px; color: #9ca3af; }
.topbar .logout { font: inherit; font-size: 12px; font-weight: 600; color: #cbd5e1; background: transparent; border: 1px solid #374151; border-radius: 7px; padding: 5px 10px; cursor: pointer; }
.topbar .logout:hover { color: #fff; border-color: #6b7280; }
@media (max-width: 1100px) { .brand small, .topbar .who small { display: none; } .topbar-inner { gap: 14px; } }
@media (max-width: 760px) { .brand div { display: none; } .topbar .who { display: none; } .topbar-inner { padding: 0 12px; gap: 8px; } .topbar nav a { padding: 0 8px; font-size: 12.5px; } }
</style>
