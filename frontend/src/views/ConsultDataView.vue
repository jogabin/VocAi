<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchCustomers, fetchEmployees, createConsultData } from '../api/adminApi'
import { useHashRoute, navigate } from '../composables/useHashRoute'
import ChatTranscript from '../components/voc/ChatTranscript.vue'

/* 상담데이터 등록: 상담현황 목록에 표출될 기초 상담데이터(통화 정보 + 고객·상담사 대화) 등록
   등록하면 '진행' 상태의 상담이 생성되고, 이후 흐름(상담이력등록 → 에이전트)은 기존과 같습니다. */

const { query } = useHashRoute()
const pad = (n) => String(n).padStart(2, '0')

const customers = ref([])
const agents = ref([])
const custKeyword = ref('')
const saving = ref(false)
const error = ref('')
const done = ref(null)          // 등록 결과 { call_id, ... }

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
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>상담데이터 등록</h2>
        <p>상담현황 목록에 표출될 기초 상담데이터(통화 정보 + 고객·상담사 대화)를 등록합니다. 등록하면 '진행' 상태의 상담이 생성됩니다.</p>
      </div>
    </div>

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
.done-box { display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap; background: var(--ok-soft); border: 1px solid #bfe5d0; color: #0d5c37; border-radius: var(--radius); padding: 12px 16px; margin-bottom: 16px; font-size: 13px; }
.err { margin: 0 0 10px; }
@media (max-width: 560px) { .form .field-row { grid-template-columns: 1fr; } .cd-line { grid-template-columns: 56px 1fr; } .cd-line .off, .cd-line .ops { display: none; } }
</style>
