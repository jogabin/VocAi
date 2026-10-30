<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { fetchEmployees, fetchEmployee, createEmployee, updateEmployee } from '../api/adminApi'
import { fetchTelegramChats } from '../api/vocApi'
import { useAuth } from '../composables/useAuth'
import { usePager } from '../composables/usePager'
import ListPager from '../components/voc/ListPager.vue'

/* 인사정보 관리: 상담사 / 센터관리자 / IT담당자.
   IT담당자의 알림 역할·담당 오류유형은 장애 알림 수신자 식별에 사용됩니다. */

const auth = useAuth()
const GROUPS = ['상담사', '센터관리자', 'IT담당자']
const ERROR_TYPES = ['로그인', '인증', '조회', '이체', 'UI오류', '기타']
const DUTY_ROLES = ['담당', '부담당', '팀장']
const GROUP_BADGE = { 상담사: 'badge-blue', 센터관리자: 'badge-amber', IT담당자: 'badge-green' }

const all = ref([])
const loading = ref(false)
const loadError = ref('')
const group = ref('')
const keyword = ref('')
const showInactive = ref(false)

const editing = reactive({ mode: null, id: null })
const form = reactive({})
const linkedUsers = ref([])
const saving = ref(false)
const formError = ref('')
const toast = ref('')

const editable = computed(() => auth.isSysAdmin.value)

const rows = computed(() => {
  const kw = keyword.value.trim().toLowerCase()
  return all.value.filter((e) => {
    if (group.value && e.emp_group !== group.value) return false
    if (!showInactive.value && !e.use_yn) return false
    if (!kw) return true
    return [e.emp_name, e.emp_no, e.dept, e.duty_system, e.duty_detail, e.messenger_id]
      .some((v) => (v || '').toLowerCase().includes(kw))
  })
})

const counts = computed(() => {
  const list = all.value.filter((e) => showInactive.value || e.use_yn)
  const c = { '': list.length }
  GROUPS.forEach((g) => { c[g] = list.filter((e) => e.emp_group === g).length })
  return c
})

const { page, pages, total, size, pageRows, reset } = usePager(rows)
watch([keyword, showInactive], reset)
async function load() {
  loading.value = true
  loadError.value = ''
  try {
    all.value = await fetchEmployees()
  } catch (e) {
    loadError.value = e.message
  } finally {
    loading.value = false
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
  linkedUsers.value = []
  fill({
    emp_no: '', emp_name: '', emp_group: group.value || '상담사', dept: '', position: '',
    duty_role: '담당', duty_error_types: [], duty_system: '', duty_detail: '',
    messenger_id: '', phone: '', email: '', on_duty: true, use_yn: true,
  })
}

async function openEdit(e) {
  editing.mode = 'edit'
  editing.id = e.emp_id
  fill({
    emp_no: e.emp_no,
    emp_name: e.emp_name,
    emp_group: e.emp_group,
    dept: e.dept || '',
    position: e.position || '',
    duty_role: e.duty_role || '담당',
    duty_error_types: [...(e.duty_error_types || [])],
    duty_system: e.duty_system || '',
    duty_detail: e.duty_detail || '',
    messenger_id: e.messenger_id || '',
    phone: e.phone || '',
    email: e.email || '',
    on_duty: e.on_duty,
    use_yn: e.use_yn,
  })
  linkedUsers.value = []
  try {
    const d = await fetchEmployee(e.emp_id)
    if (editing.id === e.emp_id) linkedUsers.value = d.users || []
  } catch { /* 상세 조회 실패 시 연결 계정만 생략 */ }
}

function closeForm() {
  editing.mode = null
  editing.id = null
}

const isIT = computed(() => form.emp_group === 'IT담당자')

/* 텔레그램 chat_id 찾기: 수신자가 봇에게 메시지를 보내면 최근 대화 목록에 나타남 → 선택해서 메신저 ID 에 입력 */
const tgChats = ref(null)
const tgLoading = ref(false)
const tgError = ref('')

async function findTelegramChats() {
  tgLoading.value = true
  tgError.value = ''
  try {
    tgChats.value = await fetchTelegramChats()
  } catch (e) {
    tgError.value = e.message
    tgChats.value = null
  } finally {
    tgLoading.value = false
  }
}

watch(() => [editing.mode, editing.id], () => {
  tgChats.value = null
  tgError.value = ''
})

function validate() {
  if (editing.mode === 'new' && !/^[A-Za-z0-9-]{2,20}$/.test(form.emp_no.trim())) return '사번은 영문·숫자·- 2~20자입니다.'
  if (!form.emp_name.trim()) return '이름을 입력하세요.'
  if (isIT.value) {
    if (!form.duty_error_types.length) return 'IT담당자는 담당 오류유형을 1개 이상 선택하세요.'
    if (!form.messenger_id.trim()) return 'IT담당자는 장애 알림을 받을 메신저 ID가 필요합니다.'
  }
  return ''
}

async function save() {
  formError.value = validate()
  if (formError.value) return
  const t = (v) => (v || '').trim() || null
  const p = {
    emp_name: form.emp_name.trim(),
    emp_group: form.emp_group,
    dept: t(form.dept),
    position: t(form.position),
    duty_role: isIT.value ? form.duty_role : null,
    duty_error_types: isIT.value ? ERROR_TYPES.filter((x) => form.duty_error_types.includes(x)) : [],
    duty_system: t(form.duty_system),
    duty_detail: t(form.duty_detail),
    messenger_id: t(form.messenger_id),
    phone: t(form.phone),
    email: t(form.email),
    on_duty: form.on_duty,
    use_yn: form.use_yn,
  }
  saving.value = true
  try {
    let row
    if (editing.mode === 'new') {
      row = await createEmployee({ ...p, emp_no: form.emp_no.trim().toUpperCase() })
      flash(`${row.emp_name} 직원을 등록했습니다.`)
    } else {
      row = await updateEmployee(editing.id, p)
      flash('저장했습니다.')
    }
    await load()
    openEdit(all.value.find((x) => x.emp_id === row.emp_id) || row)
  } catch (e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

function dutyText(e) {
  if (e.emp_group === 'IT담당자') return e.duty_system || ''
  return e.duty_detail || ''
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>인사정보 관리</h2>
        <p>상담사·센터관리자·IT담당자 정보를 관리합니다. IT담당자의 알림 역할과 담당 오류유형으로 장애 알림 수신자를 찾습니다.</p>
      </div>
      <button v-if="editable" class="btn btn-primary" @click="openNew">+ 직원 등록</button>
    </div>

    <div class="seg">
      <button :class="{ on: group === '' }" @click="group = ''">전체 <span class="cnt">{{ counts[''] }}</span></button>
      <button v-for="g in GROUPS" :key="g" :class="{ on: group === g }" @click="group = g">{{ g }} <span class="cnt">{{ counts[g] }}</span></button>
      <div class="seg-right">
        <input v-model="keyword" placeholder="이름·사번·부서·업무" style="width: 180px; padding: 6px 10px">
        <label class="chk"><input v-model="showInactive" type="checkbox"> 미사용 포함</label>
      </div>
    </div>

    <div class="split" :class="{ 'with-form': editing.mode }">
      <div class="card">
        <p v-if="loadError" class="err card-body">{{ loadError }}</p>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead>
              <tr><th>사번</th><th>이름</th><th>그룹</th><th>부서 · 직급</th><th>업무담당</th><th>메신저 ID</th><th>근무</th></tr>
            </thead>
            <tbody>
              <tr v-for="e in pageRows" :key="e.emp_id" :class="{ selected: editing.id === e.emp_id, off: !e.use_yn }" @click="openEdit(e)">
                <td class="mono">{{ e.emp_no }}</td>
                <td class="nowrap"><strong>{{ e.emp_name }}</strong></td>
                <td><span class="badge" :class="GROUP_BADGE[e.emp_group]">{{ e.emp_group }}</span></td>
                <td class="nowrap">{{ e.dept || '-' }}<span v-if="e.position" class="muted"> · {{ e.position }}</span></td>
                <td class="wrap">
                  <template v-if="e.emp_group === 'IT담당자'">
                    <span class="badge badge-gray role">{{ e.duty_role }}</span>
                    <span v-for="t in e.duty_error_types" :key="t" class="chip">{{ t }}</span>
                  </template>
                  <span class="muted duty">{{ dutyText(e) }}</span>
                </td>
                <td class="mono muted">{{ e.messenger_id || '-' }}</td>
                <td class="nowrap">
                  <span v-if="!e.use_yn" class="badge badge-gray">미사용</span>
                  <span v-else class="badge" :class="e.on_duty ? 'badge-green' : 'badge-gray'">{{ e.on_duty ? '근무' : '부재' }}</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!rows.length && !loading" class="empty">조회된 직원이 없습니다.</div>
        </div>
        <ListPager v-model:page="page" :pages="pages" :total="total" :size="size" />
      </div>

      <div v-if="editing.mode" class="card form-card">
        <div class="card-head">
          <h3>{{ editing.mode === 'new' ? '직원 등록' : `직원 상세 · ${form.emp_name}` }}</h3>
          <button class="btn btn-sm btn-ghost" @click="closeForm">닫기</button>
        </div>
        <fieldset class="card-body" :disabled="!editable || saving">
          <div class="field-row">
            <div class="field">
              <label>사번 <span v-if="editing.mode === 'new'" class="req">*</span></label>
              <input v-model="form.emp_no" class="mono" :readonly="editing.mode === 'edit'" maxlength="20" placeholder="IT0013">
            </div>
            <div class="field">
              <label>이름 <span class="req">*</span></label>
              <input v-model="form.emp_name" maxlength="50">
            </div>
          </div>
          <div class="field">
            <label>그룹</label>
            <div class="inline">
              <label v-for="g in GROUPS" :key="g" class="chk"><input v-model="form.emp_group" type="radio" :value="g"> {{ g }}</label>
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label>부서</label>
              <input v-model="form.dept" maxlength="50">
            </div>
            <div class="field">
              <label>직급 · 직책</label>
              <input v-model="form.position" maxlength="30">
            </div>
          </div>

          <div v-if="isIT" class="it-box">
            <div class="it-title">장애 알림 담당 <span class="hint">수신자 식별에 사용</span></div>
            <div class="field-row">
              <div class="field">
                <label>알림 역할</label>
                <select v-model="form.duty_role">
                  <option v-for="r in DUTY_ROLES" :key="r">{{ r }}</option>
                </select>
              </div>
              <div class="field">
                <label>담당 시스템</label>
                <input v-model="form.duty_system" maxlength="100" placeholder="예) 이체/송금 시스템">
              </div>
            </div>
            <div class="field">
              <label>담당 오류유형 <span class="req">*</span></label>
              <div class="inline">
                <label v-for="t in ERROR_TYPES" :key="t" class="chk"><input v-model="form.duty_error_types" type="checkbox" :value="t"> {{ t }}</label>
              </div>
            </div>
          </div>

          <div class="field">
            <label>업무담당 상세</label>
            <textarea v-model="form.duty_detail" rows="3" placeholder="담당 업무를 구체적으로 입력 (예: 이체 배치·대외기관 연계 장애 1차 대응)" />
          </div>
          <div class="field-row">
            <div class="field">
              <label>메신저 ID <span class="hint">텔레그램 chat_id</span> <span v-if="isIT" class="req">*</span></label>
              <div class="tg-input">
                <input v-model="form.messenger_id" class="mono" maxlength="50" placeholder="예: 123456789">
                <button type="button" class="btn btn-sm" :disabled="tgLoading" @click="findTelegramChats">
                  {{ tgLoading ? '찾는 중…' : 'chat_id 찾기' }}
                </button>
              </div>
              <p v-if="tgError" class="tg-msg error">{{ tgError }}</p>
              <template v-else-if="tgChats">
                <p v-if="!tgChats.length" class="tg-msg">최근 대화가 없습니다. 수신자가 텔레그램에서 봇에게 아무 메시지나 보낸 뒤 다시 찾아보세요.</p>
                <div v-else class="tg-chats">
                  <button v-for="c in tgChats" :key="c.chat_id" type="button" class="btn btn-sm"
                          :class="{ 'btn-primary': form.messenger_id === c.chat_id }"
                          @click="form.messenger_id = c.chat_id">
                    {{ c.name || c.username || c.chat_id }} <span class="mono">{{ c.chat_id }}</span>
                  </button>
                </div>
              </template>
            </div>
            <div class="field">
              <label>전화</label>
              <input v-model="form.phone" maxlength="20">
            </div>
          </div>
          <div class="field">
            <label>이메일</label>
            <input v-model="form.email" type="email" maxlength="100">
          </div>
          <div class="field">
            <label>상태</label>
            <div class="inline">
              <label class="chk"><input v-model="form.on_duty" type="checkbox"> 근무 중{{ isIT ? ' (알림 수신)' : '' }}</label>
              <label class="chk"><input v-model="form.use_yn" type="checkbox"> 사용 (재직)</label>
            </div>
          </div>

          <div v-if="editing.mode === 'edit'" class="field">
            <label>연결된 로그인 계정</label>
            <div class="inline">
              <span v-if="!linkedUsers.length" class="muted">없음</span>
              <span v-for="u in linkedUsers" :key="u.user_id" class="chip mono">{{ u.login_id }} · {{ u.auth_role }}{{ u.use_yn ? '' : ' · 중지' }}</span>
            </div>
          </div>

          <div v-if="editable" class="form-section">
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
.chip { display: inline-block; padding: 1px 7px; margin: 0 4px 2px 0; border-radius: 6px; background: var(--surface-2); border: 1px solid var(--line); font-size: 12px; }
.role { margin-right: 6px; }
.duty { display: block; font-size: 12.5px; margin-top: 2px; }
.it-box { background: var(--ok-soft); border: 1px solid #bfe5d0; border-radius: var(--radius); padding: 12px 12px 0; margin-bottom: 12px; }
.it-title { font-size: 12.5px; font-weight: 700; color: var(--ok); margin-bottom: 8px; }
.it-title .hint { font-weight: 500; color: var(--text-3); margin-left: 6px; }
.tg-input { display: flex; gap: 6px; }
.tg-input input { flex: 1; min-width: 0; }
.tg-chats { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.tg-msg { margin: 6px 0 0; font-size: 12px; color: var(--text-3); }
.tg-msg.error { color: var(--p1); }
.err { margin: 0 0 10px; }
</style>
