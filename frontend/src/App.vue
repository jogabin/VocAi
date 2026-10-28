<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useHashRoute } from './composables/useHashRoute'
import { useAuth, ROLE_ALL, ROLE_CONSULT, ROLE_CRITERIA, ROLE_SYS } from './composables/useAuth'
import LoginView from './views/LoginView.vue'
import mascotIcon from './assets/mascot-icon.png'
import mascot from './assets/mascot.png'
import ConsultStatusView from './views/ConsultStatusView.vue'
import ConsultRegisterView from './views/ConsultRegisterView.vue'
import IncidentMonitorView from './views/IncidentMonitorView.vue'
import IncidentDetailView from './views/IncidentDetailView.vue'
import ImprovementView from './views/ImprovementView.vue'
import CriteriaView from './views/CriteriaView.vue'
import UserAdminView from './views/UserAdminView.vue'
import EmployeeView from './views/EmployeeView.vue'
import CustomerView from './views/CustomerView.vue'
import ConsultDataView from './views/ConsultDataView.vue'
import ApiTestView from './views/ApiTestView.vue'

// vue-router 없이 해시 기반 화면 전환 (#/stt, #/consult, #/monitor, #/incident, #/improvements, #/criteria, #/users, #/employees, #/customers, #/consult-data)
// 로그인 전에는 어느 주소로 들어와도 로그인 화면을 보여주고, 로그인하면 원래 주소의 화면을 엽니다.
const { path } = useHashRoute()
const auth = useAuth()

// 화면 권한 (화면 설계서 SCR-01~10): roles = 사용할 수 있는 권한(auth_role)
// group: 상단 메뉴에서 하나의 드롭다운으로 묶어 표시 (메뉴가 많아 잘리지 않도록)
const MENUS = [
  { id: 'SCR-02', path: '/stt', label: '상담현황', view: ConsultStatusView, roles: ROLE_CONSULT },
  // 상담이력등록: 상단 메뉴에서 숨김, 상담현황 목록에서 상담을 클릭해 진입 (#/consult?call=CALL-xxxx)
  { id: 'SCR-03', path: '/consult', label: '상담이력등록', view: ConsultRegisterView, roles: ROLE_CONSULT, hidden: true, parent: '/stt' },
  { id: 'SCR-04', path: '/monitor', label: '장애 알림 모니터', view: IncidentMonitorView, roles: ROLE_ALL },
  // 장애 상세정보: 모니터 목록 · 메신저 알림 링크(#/incident?id=N)로 진입
  { id: 'SCR-05', path: '/incident', label: '장애 상세정보', view: IncidentDetailView, roles: ROLE_ALL, hidden: true, parent: '/monitor' },
  { id: 'SCR-11', path: '/improvements', label: '개선의견 목록', view: ImprovementView, roles: ROLE_ALL },
  { id: 'SCR-08', path: '/criteria', label: '판별기준 관리', view: CriteriaView, roles: ROLE_CRITERIA },
  { id: 'SCR-06', path: '/users', label: '사용자관리', view: UserAdminView, roles: ROLE_SYS, group: '시스템관리' },
  { id: 'SCR-07', path: '/employees', label: '인사정보 관리', view: EmployeeView, roles: ROLE_SYS, group: '시스템관리' },
  { id: 'SCR-09', path: '/customers', label: '고객정보 관리', view: CustomerView, roles: ROLE_SYS, group: '시스템관리' },
  // 상담데이터 등록: 시연용 기초 상담데이터 생성 기능
  { id: 'SCR-10', path: '/consult-data', label: '상담데이터 등록', view: ConsultDataView, roles: ROLE_SYS, group: '시스템관리' },
  { path: '/api-test', label: 'API 테스트', view: ApiTestView, roles: ROLE_SYS, hidden: true },   // 메뉴에서 숨김 (주소로만 접근)
]
const allowedMenus = computed(() => MENUS.filter((m) => auth.hasRole(m.roles)))
const visibleMenus = computed(() => allowedMenus.value.filter((m) => !m.hidden))
// 상단 메뉴 항목: 일반 메뉴는 그대로, group 메뉴는 첫 위치에 드롭다운 하나로
const navItems = computed(() => {
  const items = []
  for (const m of visibleMenus.value) {
    if (!m.group) { items.push(m); continue }
    const g = items.find((i) => i.group === m.group && i.children)
    if (g) g.children.push(m)
    else items.push({ group: m.group, label: m.group, children: [m] })
  }
  return items
})
const openGroup = ref('')
function toggleGroup(name) { openGroup.value = openGroup.value === name ? '' : name }
function isOn(m) { return current.value.path === m.path || current.value.parent === m.path }
watch(path, () => { openGroup.value = '' })
function closeOnOutside(e) { if (!e.target.closest?.('.nav-group')) openGroup.value = '' }
// 주소가 없거나 모르는 주소면 권한 있는 첫 화면 (IT담당자 → 장애 알림 모니터)
const current = computed(() => MENUS.find((m) => m.path === path.value) || visibleMenus.value[0] || MENUS[0])
const denied = computed(() => !auth.hasRole(current.value.roles))

// 사용자 이름 아래: 아이디 · 권한명
const userLabel = computed(() => {
  const u = auth.state.user
  if (!u) return ''
  return [u.login_id, u.auth_role].filter(Boolean).join(' · ')
})

onMounted(() => {
  auth.restore()
  document.addEventListener('click', closeOnOutside)
})
</script>

<template>
  <div v-if="!auth.state.ready" class="boot">불러오는 중…</div>

  <LoginView v-else-if="!auth.state.user" />

  <template v-else>
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <img class="logo" :src="mascotIcon" alt="" width="40" height="40">
          <div>
            <strong>VOC 장애 알림 AI Agent</strong>
            <small>상담이력 기반 자율형 장애 감지 · 알림</small>
          </div>
        </div>
        <nav>
          <template v-for="m in navItems" :key="m.path || m.group">
            <div v-if="m.children" class="nav-group" :class="{ open: openGroup === m.group }">
              <button type="button" :class="{ on: m.children.some(isOn) }" :aria-expanded="openGroup === m.group"
                      @click="toggleGroup(m.group)">{{ m.label }} <span class="caret">▾</span></button>
              <div v-if="openGroup === m.group" class="nav-menu">
                <a v-for="c in m.children" :key="c.path" :href="'#' + c.path" :class="{ on: isOn(c) }">{{ c.label }}</a>
              </div>
            </div>
            <a v-else :href="'#' + m.path" :class="{ on: isOn(m) }">{{ m.label }}</a>
          </template>
        </nav>
        <div class="user">
          <div class="who">
            <strong>{{ auth.state.user.user_name }}</strong>
            <small>{{ userLabel }}</small>
          </div>
          <button class="logout" title="로그아웃" @click="auth.logout">로그아웃</button>
        </div>
      </div>
    </header>

    <div v-if="denied" class="page">
      <div class="card"><div class="empty">
        <img class="empty-mascot" :src="mascot" alt="" width="96" height="96"><br>
        {{ current.label }} 화면은 {{ current.roles.join(' · ') }} 권한만 사용할 수 있습니다.
        <span v-if="visibleMenus.length"><br><a :href="'#' + visibleMenus[0].path">{{ visibleMenus[0].label }}(으)로 이동</a></span>
      </div></div>
    </div>
    <component :is="current.view" v-else :key="current.path" />
  </template>
</template>

<style>
.boot { min-height: 100vh; display: grid; place-items: center; color: var(--text-3); font-size: 13px; }
.topbar { background: #fff; color: var(--text); position: sticky; top: 0; z-index: 20; border-bottom: 1px solid var(--line); box-shadow: 0 2px 6px rgba(0, 0, 0, .04); }
.topbar-inner { max-width: 1440px; margin: 0 auto; padding: 0 24px; height: 68px; display: flex; align-items: center; gap: 36px; }
.brand { display: flex; align-items: center; gap: 10px; flex-shrink: 0; }
.brand .logo { width: 40px; height: 40px; object-fit: contain; flex-shrink: 0; }
.empty-mascot { width: 96px; height: 96px; object-fit: contain; margin-bottom: 6px; }   /* 빈 화면 · 권한 없음 안내 */
.brand strong { display: block; font-size: 16px; color: var(--navy); letter-spacing: -0.03em; }
.brand small { display: block; font-size: 11px; color: var(--text-3); }
.topbar nav { display: flex; gap: 4px; height: 100%; min-width: 0; }
.topbar nav > a, .nav-group > button { color: #333; font: inherit; background: none; cursor: pointer; height: 100%; display: flex; align-items: center; padding: 0 14px; font-weight: 700; font-size: 15px; letter-spacing: -0.02em; border-bottom: 3px solid transparent; border-top: 3px solid transparent; text-decoration: none; white-space: nowrap; }
.topbar nav > a:hover, .nav-group > button:hover { color: var(--accent); }
.topbar nav > a.on, .nav-group > button.on { color: var(--accent); border-bottom-color: var(--accent); }
.topbar nav > a, .nav-group > button { border-left: 0; border-right: 0; }
.nav-group { position: relative; height: 100%; }
.nav-group .caret { font-size: 10px; margin-left: 4px; }
.nav-menu { position: absolute; top: 100%; left: 0; min-width: 160px; background: #fff; border: 1px solid var(--line); border-radius: 4px; box-shadow: 0 6px 16px rgba(0, 0, 0, .08); padding: 4px 0; z-index: 30; }
.nav-menu a { display: block; padding: 9px 16px; font-size: 14px; font-weight: 600; color: #333; text-decoration: none; white-space: nowrap; }
.nav-menu a:hover { background: var(--surface-2); color: var(--accent); }
.nav-menu a.on { color: var(--accent); }
.topbar .user { margin-left: auto; display: flex; align-items: center; gap: 12px; flex-shrink: 0; }
.topbar .who { text-align: right; line-height: 1.3; }
.topbar .who strong { display: block; font-size: 13px; color: #222; }
.topbar .who small { display: block; font-size: 11px; color: var(--text-3); }
.topbar .logout { font: inherit; font-size: 12px; font-weight: 600; color: var(--text-2); background: #fff; border: 1px solid var(--line-strong); border-radius: 3px; padding: 4px 9px; cursor: pointer; }
.topbar .logout:hover { color: var(--accent); border-color: var(--accent); }
@media (max-width: 1400px) { .brand small { display: none; } .topbar-inner { gap: 16px; } .topbar nav > a, .nav-group > button { padding: 0 10px; font-size: 14px; } }
@media (max-width: 1100px) { .brand div { display: none; } }
@media (max-width: 900px) { .topbar-inner { gap: 8px; } .topbar nav > a, .nav-group > button { padding: 0 8px; font-size: 13px; } }
@media (max-width: 760px) { .brand div { display: none; } .topbar .who { display: none; } .topbar-inner { padding: 0 12px; gap: 8px; height: 56px; } .topbar nav { overflow-x: auto; scrollbar-width: none; } .topbar nav > a, .nav-group > button { padding: 0 8px; font-size: 13px; } .nav-menu { position: fixed; top: 56px; left: auto; right: 12px; } }
</style>
