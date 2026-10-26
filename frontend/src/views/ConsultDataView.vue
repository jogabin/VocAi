<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchCustomers, fetchEmployees, createConsultData, readDialogExcel, downloadDialogTemplate } from '../api/adminApi'
import { fetchSttCall } from '../api/vocApi'
import { useHashRoute, navigate } from '../composables/useHashRoute'
import ChatTranscript from '../components/voc/ChatTranscript.vue'

/* 상담데이터 등록: 상담현황 목록에 표출될 기초 상담데이터(통화 정보 + 고객·상담사 대화) 등록
   등록하면 '진행' 상태의 상담이 생성되고, 이후 흐름(상담이력등록 → 에이전트)은 기존과 같습니다.
   상담이력등록 화면의 [원문대화 복사등록]으로 들어오면(#/consult-data?copy=CALL-xxxx) 그 통화의 고객·상담사·대화를 채워 둡니다. */

const { query } = useHashRoute()
const pad = (n) => String(n).padStart(2, '0')

const customers = ref([])
const agents = ref([])
const custKeyword = ref('')
const saving = ref(false)
const error = ref('')
const done = ref(null)          // 등록 결과 { call_id, ... }
const copyMsg = ref('')         // 원문대화 복사 안내

let lineId = 0
const newLine = (speaker, text = '') => ({ id: ++lineId, speaker, text })

function nowParts() {
  const d = new Date()
  return { date: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`, time: `${pad(d.getHours())}:${pad(d.getMinutes())}` }
}
const form = reactive({ customer_id: '', agent_emp_id: '', consult_date: '', start_time: '', lines: [] })

function reset(keepPeople = true) {
  const n = nowParts()
  form.consult_date = n.date
  form.start_time = n.time
  form.lines = [newLine('AGENT', ''), newLine('CUSTOMER', '')]
  if (!keepPeople) { form.customer_id = ''; form.agent_emp_id = '' }
  error.value = ''
}

const filteredCustomers = computed(() => {
  const kw = custKeyword.value.trim().replace(/-/g, '')
  if (!kw) return customers.value
  return customers.value.filter((c) => [c.customer_name, c.customer_id, (c.phone || '').replace(/-/g, '')].some((v) => (v || '').includes(kw)))
})
const selectedCustomer = computed(() => customers.value.find((c) => c.customer_id === form.customer_id))
const selectedAgent = computed(() => agents.value.find((a) => a.emp_id === Number(form.agent_emp_id)))

// 경과시간 자동 계산 (서버와 같은 규칙: 이전 발화 길이 / 초당 6자, 최소 4초)
const offsets = computed(() => {
  let cur = 0
  let prev = 0
  return form.lines.map((l, i) => {
    if (i > 0) cur += Math.max(4, Math.round(prev / 6))
    prev = l.text.trim().length
    return cur
  })
})
const fmtOff = (s) => `${pad(Math.floor(s / 60))}:${pad(s % 60)}`

const preview = computed(() => form.lines
  .map((l, i) => ({ seq: i + 1, speaker: l.speaker, offset_sec: offsets.value[i], text: l.text.trim() }))
  .filter((u) => u.text))

function addLine(speaker) {
  form.lines.push(newLine(speaker))
}
function toggleSpeaker(l) {
  l.speaker = l.speaker === 'AGENT' ? 'CUSTOMER' : 'AGENT'
}
function move(i, d) {
  const j = i + d
  if (j < 0 || j >= form.lines.length) return
  const arr = form.lines
  ;[arr[i], arr[j]] = [arr[j], arr[i]]
}
function remove(i) {
  form.lines.splice(i, 1)
  if (!form.lines.length) addLine('CUSTOMER')
}

// 엑셀 업로드: 서버에서 읽은 대화로 입력 목록을 채움 (등록은 기존처럼 [등록] 버튼으로)
const excelInput = ref(null)
const excelBusy = ref(false)
const excelMsg = ref('')
const excelErr = ref('')

async function onExcelFile(ev) {
  const file = ev.target.files?.[0]
  ev.target.value = ''            // 같은 파일을 다시 골라도 change 이벤트가 나도록
  if (!file) return
  excelMsg.value = ''
  excelErr.value = ''
  excelBusy.value = true
  try {
    const { lines } = await readDialogExcel(file)
    if (form.lines.some((l) => l.text.trim()) && !window.confirm(`입력 중인 대화를 엑셀 대화 ${lines.length}건으로 바꿀까요?`)) return
    form.lines = lines.map((l) => newLine(l.speaker, l.text))
    excelMsg.value = `${file.name}에서 대화 ${lines.length}건을 불러왔습니다. 미리보기를 확인한 뒤 등록하세요.`
  } catch (e) {
    excelErr.value = e.message
  } finally {
    excelBusy.value = false
  }
}

async function onTemplate() {
  excelErr.value = ''
  try {
    await downloadDialogTemplate()
  } catch (e) {
    excelErr.value = e.message
  }
}

function validate() {
  if (!form.customer_id) return '고객을 선택하세요.'
  if (!form.agent_emp_id) return '상담사를 선택하세요.'
  if (!form.consult_date || !form.start_time) return '상담일자와 상담최초시간을 입력하세요.'
  if (!preview.value.length) return '대화내용을 입력하세요.'
  if (!preview.value.some((u) => u.speaker === 'CUSTOMER')) return '고객 대화가 1개 이상 필요합니다.'
  return ''
}

async function submit() {
  error.value = validate()
  if (error.value) return
  saving.value = true
  try {
    copyMsg.value = ''
    done.value = await createConsultData({
      customer_id: form.customer_id,
      agent_emp_id: Number(form.agent_emp_id),
      consult_date: form.consult_date,
      start_time: form.start_time,
      utterances: preview.value.map((u) => ({ speaker: u.speaker, text: u.text })),
    })
    reset(true)
  } catch (e) {
    error.value = e.message
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  reset(false)
  try {
    const [c, a] = await Promise.all([fetchCustomers(), fetchEmployees({ group: '상담사', use_yn: true })])
    customers.value = c
    agents.value = a
    if (query.value.customer && c.some((x) => x.customer_id === query.value.customer)) form.customer_id = query.value.customer
    if (query.value.copy) await copyFromCall(query.value.copy)
  } catch (e) {
    error.value = e.message
  }
})

// 원문대화 복사: 원본 통화의 고객·상담사·대화를 그대로 채움 (상담일자·시간은 지금, 등록은 [등록] 버튼으로)
async function copyFromCall(callId) {
  const src = await fetchSttCall(callId)
  if (customers.value.some((x) => x.customer_id === src.customer_id)) form.customer_id = src.customer_id
  if (agents.value.some((a) => a.emp_id === src.agent_emp_id)) form.agent_emp_id = src.agent_emp_id
  form.lines = src.utterances.map((u) => newLine(u.speaker, u.text))
  copyMsg.value = `${src.call_id} 원문 대화 ${src.utterances.length}건을 복사했습니다. 내용을 확인·수정한 뒤 등록하세요.`
  navigate('/consult-data')       // 새로고침 시 다시 덮어쓰지 않도록 주소에서 copy 제거
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>상담데이터 등록</h2>
        <p>상담현황 목록에 표출될 기초 상담데이터(통화 정보 + 고객·상담사 대화)를 등록합니다. 등록하면 '진행' 상태의 상담이 생성됩니다.</p>
      </div>
    </div>

    <div v-if="copyMsg && !done" class="copy-box">{{ copyMsg }}</div>

    <div v-if="done" class="done-box">
      <div>
        <strong>{{ done.call_id }}</strong> 상담데이터를 등록했습니다. 상담현황에 '진행' 상태로 표시됩니다. (대화 {{ done.utterance_count }}건)
      </div>
      <div class="toolbar">
        <button class="btn btn-sm" @click="navigate('/stt')">상담현황 보기</button>
        <button class="btn btn-sm btn-primary" @click="navigate('/consult', { call: done.call_id })">상담이력등록으로 이동 →</button>
        <button class="btn btn-sm btn-ghost" @click="done = null">닫기</button>
      </div>
    </div>

    <div class="grid-2">
      <!-- ============ 입력 ============ -->
      <section class="card">
        <div class="card-head"><h3>상담 기본 정보</h3></div>
        <fieldset class="card-body form" :disabled="saving">
          <div class="field-row">
            <div class="field">
              <label>고객 <span class="req">*</span></label>
              <input v-model="custKeyword" class="cust-search" placeholder="고객명 · 고객번호 · 핸드폰번호 검색">
              <select v-model="form.customer_id">
                <option value="">{{ filteredCustomers.length ? '고객 선택' : '검색 결과 없음' }}</option>
                <option v-for="c in filteredCustomers" :key="c.customer_id" :value="c.customer_id">
                  {{ c.customer_id }} · {{ c.customer_name }}{{ c.phone ? ' (' + c.phone + ')' : '' }}
                </option>
              </select>
              <span class="hint">고객정보 관리에 등록된 고객에서 선택 · <a href="#/customers">고객 등록</a></span>
            </div>
            <div class="field">
              <label>상담사 <span class="req">*</span></label>
              <select v-model="form.agent_emp_id" class="agent-select">
                <option value="">상담사 선택</option>
                <option v-for="a in agents" :key="a.emp_id" :value="a.emp_id">{{ a.emp_name }} ({{ a.emp_no }}{{ a.dept ? ' · ' + a.dept : '' }})</option>
              </select>
              <span class="hint">인사정보 관리의 상담사 그룹</span>
            </div>
          </div>
          <div class="field-row">
            <div class="field">
              <label>상담일자 <span class="req">*</span></label>
              <input v-model="form.consult_date" type="date">
            </div>
            <div class="field">
              <label>상담최초시간 <span class="req">*</span></label>
              <input v-model="form.start_time" type="time">
            </div>
          </div>

          <div class="field">
            <label>대화내용 <span class="req">*</span> <span class="hint">순서대로 입력 · 화자 배지를 누르면 고객/상담사 전환</span></label>
            <div class="inline excel-bar">
              <button class="btn btn-sm" type="button" :disabled="excelBusy" @click="excelInput.click()">
                {{ excelBusy ? '읽는 중…' : '엑셀로 불러오기' }}
              </button>
              <button class="btn btn-sm btn-ghost" type="button" @click="onTemplate">양식 내려받기</button>
              <span class="hint">A열 화자(고객/상담사) · B열 대화내용, 1행은 머리글</span>
              <input ref="excelInput" type="file" accept=".xlsx,.xlsm" hidden @change="onExcelFile">
            </div>
            <p v-if="excelErr" class="err">{{ excelErr }}</p>
            <p v-else-if="excelMsg" class="ok excel-msg">{{ excelMsg }}</p>
            <div v-for="(l, i) in form.lines" :key="l.id" class="cd-line">
              <button type="button" class="who" :class="l.speaker === 'AGENT' ? 'agent' : 'customer'" :title="'클릭하면 ' + (l.speaker === 'AGENT' ? '고객' : '상담사') + '으로 전환'" @click="toggleSpeaker(l)">
                {{ l.speaker === 'AGENT' ? '상담사' : '고객' }}
              </button>
              <input v-model="l.text" :placeholder="l.speaker === 'AGENT' ? '상담사 대화' : '고객 대화'" maxlength="1000">
              <span class="mono muted off">{{ fmtOff(offsets[i]) }}</span>
              <span class="ops">
                <button type="button" title="위로" :disabled="i === 0" @click="move(i, -1)">▲</button>
                <button type="button" title="아래로" :disabled="i === form.lines.length - 1" @click="move(i, 1)">▼</button>
                <button type="button" title="삭제" @click="remove(i)">✕</button>
              </span>
            </div>
            <div class="inline">
              <button class="btn btn-sm" type="button" @click="addLine('CUSTOMER')">+ 고객 대화</button>
              <button class="btn btn-sm" type="button" @click="addLine('AGENT')">+ 상담사 대화</button>
              <span class="hint">경과시간은 대화 길이로 자동 계산</span>
            </div>
          </div>

          <div class="form-section">
            <p v-if="error" class="err">{{ error }}</p>
            <div class="form-actions">
              <button class="btn" type="button" @click="reset(false)">초기화</button>
              <button class="btn btn-primary btn-lg" type="button" @click="submit">{{ saving ? '등록 중…' : '상담데이터 등록' }}</button>
            </div>
          </div>
        </fieldset>
      </section>

      <!-- ============ 미리보기 ============ -->
      <section class="card">
        <div class="card-head">
          <h3>대화 미리보기 <span class="sub">상담현황 · 상담이력등록 화면에 표시되는 형태</span></h3>
          <span class="badge badge-blue"><span class="dot pulse" /> 등록 시 '진행'</span>
        </div>
        <div class="card-body">
          <p class="meta">
            {{ selectedCustomer ? selectedCustomer.customer_name + ' (' + selectedCustomer.customer_id + ')' : '고객 미선택' }}
            · {{ selectedAgent ? '상담사 ' + selectedAgent.emp_name : '상담사 미선택' }}
            · {{ form.consult_date }} {{ form.start_time }}
          </p>
          <ChatTranscript :utterances="preview" :customer-name="selectedCustomer?.customer_name || '고객'" :agent-name="selectedAgent?.emp_name || '상담사'" />
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.form { border: none; margin: 0; min-width: 0; }
.form .field > input, .form .field > select { width: 100%; }
.form .field-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.cust-search { margin-bottom: 6px; }
.cd-line { display: grid; grid-template-columns: 64px 1fr 44px auto; gap: 8px; align-items: center; margin-bottom: 6px; }
.cd-line input { width: 100%; min-width: 0; }
.who { font: inherit; font-size: 12px; font-weight: 700; border: none; border-radius: 999px; padding: 4px 0; cursor: pointer; }
.who.agent { background: var(--p4-soft); color: var(--p4); }
.who.customer { background: var(--accent-soft); color: var(--accent); }
.off { font-size: 11.5px; text-align: right; }
.ops { display: inline-flex; gap: 2px; }
.ops button { font: inherit; font-size: 11px; width: 24px; height: 26px; border: 1px solid var(--line); background: var(--surface); border-radius: 6px; color: var(--text-2); cursor: pointer; }
.ops button:disabled { opacity: .35; cursor: default; }
.ops button:hover:not(:disabled) { background: var(--surface-2); }
.copy-box { background: var(--accent-soft); border: 1px solid var(--line); color: var(--text); border-radius: var(--radius); padding: 12px 16px; margin-bottom: 16px; font-size: 13px; }
.done-box { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; background: var(--ok-soft); border: 1px solid #bfe5d0; color: #0d5c37; border-radius: var(--radius); padding: 12px 16px; margin-bottom: 16px; font-size: 13px; }
.err { margin: 0 0 10px; }
.excel-bar { margin-bottom: 8px; }
.excel-msg { margin: 0 0 10px; font-size: 13px; }
@media (max-width: 560px) { .form .field-row { grid-template-columns: 1fr; } .cd-line { grid-template-columns: 56px 1fr; } .cd-line .off, .cd-line .ops { display: none; } }
</style>
