<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchUsers, createUser, updateUser, fetchEmployees } from '../api/adminApi'
import { useAuth, ROLES } from '../composables/useAuth'
import { fmtDateTime } from '../utils/format'

/* 사용자관리: VOC 장애 관리 시스템 로그인 사용자
   권한 4종 — 상담사 / 센터관리자 / IT담당자 / 시스템관리자 (화면 설계서 SCR-01~10) */
const ROLE_BADGE = { 상담사: 'badge-blue', 센터관리자: 'badge-green', IT담당자: 'badge-amber', 시스템관리자: 'badge-red' }
const ROLE_DESC = {
  상담사: '상담현황 · 상담이력등록 · 장애 모니터/상세',
  센터관리자: '상담현황 · 상담이력등록 · 장애 모니터/상세',
  IT담당자: '장애 모니터/상세(장애 처리 등록) · 판별기준 관리',
  시스템관리자: '전체 화면 (사용자·인사·고객·상담데이터 관리 포함)',
}

const auth = useAuth()
const users = ref([])
const employees = ref([])
const loading = ref(false)
const loadError = ref('')
const filter = reactive({ keyword: '', auth_role: '', use_yn: '' })

const editing = reactive({ mode: null, id: null })
const form = reactive({})
const current = ref(null)
const saving = ref(false)
const formError = ref('')
const toast = ref('')

const GROUPS = ['센터관리자', '상담사', 'IT담당자']
const empByGroup = computed(() => GROUPS.map((g) => ({
  group: g,
  list: employees.value.filter((e) => e.emp_group === g),
})))

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const params = {}
    if (filter.keyword.trim()) params.keyword = filter.keyword.trim()
    if (filter.auth_role) params.auth_role = filter.auth_role
    if (filter.use_yn !== '') params.use_yn = filter.use_yn
    users.value = await fetchUsers(params)
  } catch (e) {
    loadError.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadEmployees() {
  try {
    employees.value = await fetchEmployees({ use_yn: true })
  } catch {
    employees.value = []
  }
}

function flash(msg) {
  toast.value = msg
  setTimeout(() => { if (toast.value === msg) toast.value = '' }, 2500)
}

function fill(obj) {
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, obj)
  formError.value = ''
}

function openNew() {
  editing.mode = 'new'
  editing.id = null
  current.value = null
  fill({ login_id: '', user_name: '', auth_role: '상담사', emp_id: '', email: '', use_yn: true, password: '', password2: '', reset_pw: true })
}

function openEdit(u) {
  editing.mode = 'edit'
  editing.id = u.user_id
  current.value = u
  fill({
    login_id: u.login_id,
    user_name: u.user_name,
    auth_role: u.auth_role,
    emp_id: u.emp_id ?? '',
    email: u.email || '',
    use_yn: u.use_yn,
    password: '',
    password2: '',
    reset_pw: false,
  })
}

function closeForm() {
  editing.mode = null
  editing.id = null
  current.value = null
}

// 직원을 고르면 이름이 비어 있을 때 채워줌
function onPickEmployee() {
  const emp = employees.value.find((e) => e.emp_id === Number(form.emp_id))
  if (emp && !form.user_name.trim()) form.user_name = emp.emp_name
}

const isSelf = computed(() => editing.mode === 'edit' && editing.id === auth.state.user?.user_id)
const pwRule = (pw) => pw.length >= 8 && /\d/.test(pw) && /[A-Za-z]/.test(pw)

function validate() {
  if (editing.mode === 'new' && !/^[A-Za-z0-9_.-]{3,30}$/.test(form.login_id.trim())) return '아이디는 영문·숫자·_ . - 3~30자입니다.'
  if (!form.user_name.trim()) return '이름을 입력하세요.'
  if (form.reset_pw) {
    if (!pwRule(form.password)) return '비밀번호는 영문과 숫자를 포함해 8자 이상이어야 합니다.'
    if (form.password !== form.password2) return '비밀번호 확인이 일치하지 않습니다.'
  }
  return ''
}

async function save() {
  formError.value = validate()
  if (formError.value) return
  const p = {
    user_name: form.user_name.trim(),
    auth_role: form.auth_role,
    emp_id: form.emp_id === '' ? null : Number(form.emp_id),
    email: form.email.trim() || null,
    use_yn: form.use_yn,
  }
  saving.value = true
  try {
    let row
    if (editing.mode === 'new') {
      row = await createUser({ ...p, login_id: form.login_id.trim(), password: form.password })
      flash(`${row.login_id} 사용자를 등록했습니다.`)
    } else {
      if (form.reset_pw) p.new_password = form.password
      row = await updateUser(editing.id, p)
      flash(form.reset_pw ? '저장했습니다. 비밀번호가 초기화되어 기존 로그인은 종료됩니다.' : '저장했습니다.')
    }
    await load()
    openEdit(users.value.find((u) => u.user_id === row.user_id) || row)
  } catch (e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

async function unlock() {
  saving.value = true
  try {
    const row = await updateUser(editing.id, { unlock: true })
    await load()
    openEdit(users.value.find((u) => u.user_id === row.user_id) || row)
    flash('로그인 잠금을 해제했습니다.')
  } catch (e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

function empLabel(u) {
  if (!u.emp_id) return ''
  return [u.emp_name, u.emp_group, u.dept].filter(Boolean).join(' · ')
}

onMounted(() => { load(); loadEmployees() })
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>사용자관리</h2>
        <p>VOC 장애 알림 시스템에 로그인하는 사용자를 관리합니다. 권한은 상담사 · 센터관리자 · IT담당자 · 시스템관리자 4종이며, 장애 처리 등록은 IT담당자 권한만 할 수 있습니다.</p>
      </div>
      <button class="btn btn-primary" @click="openNew">+ 사용자 등록</button>
    </div>

    <div class="split" :class="{ 'with-form': editing.mode }">
      <div class="card">
        <div class="card-head">
          <h3>사용자 목록<span class="sub">{{ users.length }}명</span></h3>
          <form class="toolbar" @submit.prevent="load">
            <input v-model="filter.keyword" placeholder="아이디·이름·부서" style="width: 160px">
            <select v-model="filter.auth_role" @change="load">
              <option value="">권한 전체</option>
              <option v-for="r in ROLES" :key="r">{{ r }}</option>
            </select>
            <select v-model="filter.use_yn" @change="load">
              <option value="">상태 전체</option>
              <option :value="true">사용</option>
              <option :value="false">중지</option>
            </select>
            <button class="btn btn-sm" type="submit" :disabled="loading">조회</button>
          </form>
        </div>
        <p v-if="loadError" class="err card-body">{{ loadError }}</p>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr><th>아이디</th><th>이름</th><th>권한</th><th>연결 직원</th><th>상태</th><th>최근 로그인</th></tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.user_id" :class="{ selected: editing.id === u.user_id, off: !u.use_yn }" @click="openEdit(u)">
                <td class="mono">{{ u.login_id }}</td>
                <td class="nowrap"><strong>{{ u.user_name }}</strong><span v-if="u.user_id === auth.state.user?.user_id" class="badge badge-blue me">나</span></td>
                <td><span class="badge" :class="ROLE_BADGE[u.auth_role] || 'badge-gray'">{{ u.auth_role }}</span></td>
                <td :class="{ muted: !u.emp_id }">{{ empLabel(u) || '-' }}</td>
                <td class="nowrap">
                  <span class="badge" :class="u.use_yn ? 'badge-green' : 'badge-gray'">{{ u.use_yn ? '사용' : '중지' }}</span>
                  <span v-if="u.fail_count > 0" class="badge badge-red">실패 {{ u.fail_count }}회</span>
                </td>
                <td class="muted nowrap">{{ u.last_login_at ? fmtDateTime(u.last_login_at) : '-' }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="!users.length && !loading" class="empty">조회된 사용자가 없습니다.</div>
        </div>
      </div>

      <div v-if="editing.mode" class="card form-card">
        <div class="card-head">
          <h3>{{ editing.mode === 'new' ? '사용자 등록' : `사용자 상세 · ${form.login_id}` }}</h3>
          <button class="btn btn-sm btn-ghost" @click="closeForm">닫기</button>
        </div>
        <fieldset class="card-body" :disabled="saving">
          <p v-if="current" class="meta">
            최근 로그인 {{ current.last_login_at ? fmtDateTime(current.last_login_at) : '없음' }} ·
            비밀번호 변경 {{ fmtDateTime(current.pw_changed_at) }} ·
            등록 {{ fmtDateTime(current.created_at) }}
          </p>

          <div v-if="current && current.fail_count > 0" class="lock-box">
            로그인 {{ current.fail_count }}회 연속 실패. 잠긴 계정이면 해제해야 로그인할 수 있습니다.
            <button class="btn btn-sm" type="button" @click="unlock">잠금 해제</button>
          </div>

          <div class="field-row">
            <div class="field">
              <label>아이디 <span v-if="editing.mode === 'new'" class="req">*</span></label>
              <input v-model="form.login_id" class="mono" :readonly="editing.mode === 'edit'" maxlength="30" autocomplete="off">
            </div>
            <div class="field">
              <label>이름 <span class="req">*</span></label>
              <input v-model="form.user_name" maxlength="50">
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label>권한</label>
              <select v-model="form.auth_role" :disabled="isSelf">
                <option v-for="r in ROLES" :key="r">{{ r }}</option>
              </select>
              <span v-if="isSelf" class="hint">본인 권한은 바꿀 수 없습니다.</span>
              <span v-else class="hint">{{ ROLE_DESC[form.auth_role] }}</span>
            </div>
            <div class="field">
              <label>연결 직원 (인사정보)</label>
              <select v-model="form.emp_id" @change="onPickEmployee">
                <option value="">연결 안 함</option>
                <optgroup v-for="g in empByGroup" :key="g.group" :label="g.group">
                  <option v-for="e in g.list" :key="e.emp_id" :value="e.emp_id">{{ e.emp_name }} ({{ e.emp_no }}{{ e.dept ? ' · ' + e.dept : '' }})</option>
                </optgroup>
              </select>
            </div>
          </div>
          <div class="field">
            <label>이메일</label>
            <input v-model="form.email" type="email" maxlength="100">
          </div>
          <div class="field">
            <label>사용 여부</label>
            <label class="chk"><input v-model="form.use_yn" type="checkbox" :disabled="isSelf"> 사용</label>
          </div>

          <div class="form-section">
            <label v-if="editing.mode === 'edit'" class="chk pw-toggle"><input v-model="form.reset_pw" type="checkbox"> 비밀번호 초기화</label>
            <div v-if="form.reset_pw" class="field-row">
              <div class="field">
                <label>{{ editing.mode === 'new' ? '비밀번호' : '새 비밀번호' }} <span class="req">*</span></label>
                <input v-model="form.password" type="password" autocomplete="new-password" maxlength="100">
                <span class="hint">영문·숫자 포함 8자 이상</span>
              </div>
              <div class="field">
                <label>비밀번호 확인 <span class="req">*</span></label>
                <input v-model="form.password2" type="password" autocomplete="new-password" maxlength="100">
              </div>
            </div>
            <p v-if="formError" class="err">{{ formError }}</p>
            <div class="form-actions">
              <button class="btn" type="button" @click="closeForm">취소</button>
              <button class="btn btn-primary" type="button" @click="save">{{ saving ? '저장 중…' : (editing.mode === 'new' ? '등록' : '저장') }}</button>
            </div>
          </div>
        </fieldset>
      </div>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.me { margin-left: 6px; }
.lock-box { display: flex; align-items: center; justify-content: space-between; gap: 10px; background: var(--p1-soft); color: var(--p1); border-radius: 8px; padding: 8px 12px; font-size: 12.5px; margin-bottom: 12px; }
.pw-toggle { margin-bottom: 12px; }
.err { margin: 0 0 10px; }
</style>
