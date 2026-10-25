<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { fetchSttCalls, fetchSttCall, addUtterance, createConsult, fetchAgentRun, rerunAgent, draftConsultSummary } from '../api/vocApi'
import { useHashRoute, navigate } from '../composables/useHashRoute'
import { useAuth } from '../composables/useAuth'
import { fmtDateTime, fmtDuration } from '../utils/format'
import ChatTranscript from '../components/voc/ChatTranscript.vue'
import AgentTimeline from '../components/voc/AgentTimeline.vue'
import AgentGraph from '../components/voc/AgentGraph.vue'
import StatusBadge from '../components/voc/StatusBadge.vue'

/* 상담이력등록
   - STT 원문 대화 확인, 시스템관리자는 상담 진행 중인 통화에 고객/상담사 대화 추가
   - 상담이력(고객번호·고객명 고정, 상담유형·접촉채널·접촉결과·상담요약 입력) 등록 → 상담완료 처리
   - 상담요약은 STT 원문 전체를 상담사 관점([문의]/[확인]/[처리])으로 요약한 초안을 자동으로 채움 (API: summary-draft)
   - 등록 즉시 장애 알림 에이전트(LangGraph) 실행 과정을 하단 그래프로 표시
   - 상담완료 건은 등록된 정보와 마지막 에이전트 실행 결과만 확인 */

const { query } = useHashRoute()
const auth = useAuth()

const CONSULT_TYPES = ['전산오류문의', '일반문의', '불만', '기타']
const CHANNELS = ['앱', '웹', 'ARS', '기타']
const RESULTS = ['완료', '이관', '보류']

const activeCalls = ref([])
const call = ref(null)
const loading = ref(false)
const callError = ref('')

const form = reactive({ consult_type: '전산오류문의', channel: '앱', result_status: '완료', summary: '' })
const isDone = computed(() => call.value?.consult_status === '상담완료')
const consult = computed(() => call.value?.consult || null)

/* ---------- 통화 불러오기 ---------- */
function guessChannel(text) {
  if (/홈페이지|인터넷뱅킹|PC|크롬|엣지|브라우저|웹/i.test(text)) return '웹'
  if (/앱|모바일|아이폰|갤럭시|안드로이드/i.test(text)) return '앱'
  if (/ARS|자동응답/i.test(text)) return 'ARS'
  return '기타'
}

function customerText() {
  return (call.value?.utterances || []).filter((u) => u.speaker === 'CUSTOMER').map((u) => u.text).join(' ')
}

/* 상담요약 초안: 고객 발화를 잘라 붙이지 않고, 대화 전체를 상담사 입장에서 요약 (서버: LLM → 규칙 기반) */
const drafting = ref(false)
const draftInfo = ref('')
let draftSeq = 0                                         // 통화를 바꾸면 이전 요청 결과는 버림

async function draftSummary() {
  if (!call.value || isDone.value) return
  const seq = ++draftSeq
  drafting.value = true
  draftInfo.value = ''
  try {
    const res = await draftConsultSummary(call.value.call_id)
    if (seq !== draftSeq) return
    form.summary = res.summary || ''
    draftInfo.value = res.source === 'LLM' ? 'AI가 대화 전체를 요약한 초안입니다. 확인 후 수정하세요.'
                                           : '대화 내용을 규칙 기반으로 정리한 초안입니다. 확인 후 수정하세요.'
  } catch (e) {
    if (seq === draftSeq) draftInfo.value = '초안을 만들지 못했습니다: ' + e.message
  } finally {
    if (seq === draftSeq) drafting.value = false
  }
}

function fillFromConsult(c) {
  form.consult_type = c.consult_type
  form.channel = c.channel || '기타'
  form.result_status = c.result_status
  form.summary = c.summary
  draftSeq++
  drafting.value = false
  draftInfo.value = ''
}

async function loadActive() {
  try { activeCalls.value = await fetchSttCalls({ consultStatus: '진행', limit: 200 }) } catch { activeCalls.value = [] }
}

async function loadCall(id) {
  clearTimeout(pollTimer)
  run.value = null
  submitError.value = ''
  callError.value = ''
  if (!id) { call.value = null; return }
  loading.value = true
  try {
    call.value = await fetchSttCall(id)
    if (isDone.value && consult.value) {
      fillFromConsult(consult.value)
      if (consult.value.run_id) pollRun(consult.value.run_id)
    } else {
      form.consult_type = '전산오류문의'
      form.channel = guessChannel(customerText())
      form.result_status = '완료'
      form.summary = ''
      draftSummary()
    }
    scrollChat()
  } catch (e) {
    call.value = null
    callError.value = e.message
  } finally {
    loading.value = false
  }
}

watch(() => query.value.call, (id) => loadCall(id))

function pickCall(e) {
  if (e.target.value) navigate('/consult', { call: e.target.value })
}

/* ---------- 관리자 대화 추가 ---------- */
const canAddUtterance = computed(() => auth.isSysAdmin.value && call.value && !isDone.value)   // 시스템관리자
const utt = reactive({ speaker: 'CUSTOMER', text: '', saving: false, error: '' })
const chatBox = ref(null)

function scrollChat() {
  nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight })
}

async function submitUtterance() {
  const text = utt.text.trim()
  if (!text || utt.saving) return
  utt.saving = true
  utt.error = ''
  try {
    const row = await addUtterance(call.value.call_id, { speaker: utt.speaker, text })
    call.value.utterances.push(row)
    utt.text = ''
    utt.speaker = utt.speaker === 'CUSTOMER' ? 'AGENT' : 'CUSTOMER'   // 대화 순서대로 번갈아 입력
    scrollChat()
  } catch (e) {
    utt.error = e.message
  } finally {
    utt.saving = false
  }
}

function onUttKey(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submitUtterance()
  }
}

/* ---------- 상담이력 등록 + 에이전트 진행 ---------- */
const submitting = ref(false)
const submitError = ref('')
const run = ref(null)
const graphCard = ref(null)
let pollTimer = null

const canSubmit = computed(() => !!call.value && !isDone.value && form.summary.trim().length >= 2 && !submitting.value && !drafting.value)

async function pollRun(runId) {
  clearTimeout(pollTimer)
  try {
    const r = await fetchAgentRun(runId)
    run.value = r
    if (r.status === 'RUNNING') pollTimer = setTimeout(() => pollRun(runId), 1000)
  } catch {
    pollTimer = setTimeout(() => pollRun(runId), 2000)
  }
}

async function submit() {
  if (!canSubmit.value) return
  submitting.value = true
  submitError.value = ''
  try {
    const res = await createConsult({
      call_id: call.value.call_id,
      consult_type: form.consult_type,
      channel: form.channel || null,
      summary: form.summary.trim(),
      result_status: form.result_status,
      run_agent: true,
    })
    call.value.consult = { ...res.consult, run_id: res.run_id }
    call.value.consult_status = '상담완료'
    run.value = { run_id: res.run_id, status: 'RUNNING', steps: [] }
    loadActive()
    if (res.run_id) pollRun(res.run_id)
    nextTick(() => graphCard.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  } catch (e) {
    submitError.value = e.message
  } finally {
    submitting.value = false
  }
}

async function rerun() {
  if (!consult.value) return
  const { run_id } = await rerunAgent(consult.value.consult_id)
  run.value = { run_id, status: 'RUNNING', steps: [] }
  pollRun(run_id)
}

const agentName = (n) => (n || '').replace(/^상담사\s*/, '')

onMounted(() => {
  loadActive()
  if (query.value.call) loadCall(query.value.call)
})
onBeforeUnmount(() => clearTimeout(pollTimer))
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <a href="#/stt" class="back">← 상담현황</a>
        <h2>상담이력등록</h2>
        <p>상담이력을 등록하면 상담완료로 바뀌고 <strong>장애 알림 에이전트</strong>가 바로 실행됩니다. 실행 과정은 하단 그래프에서 확인할 수 있습니다.</p>
      </div>
      <div class="toolbar">
        <label class="muted" style="font-size: 12px">진행 중인 상담</label>
        <select :value="call && !isDone ? call.call_id : ''" style="min-width: 280px" @change="pickCall">
          <option value="">{{ activeCalls.length ? '통화 선택' : '진행 중인 상담 없음' }}</option>
          <option v-for="c in activeCalls" :key="c.call_id" :value="c.call_id">
            {{ c.call_id }} · {{ c.customer_name }} · {{ (c.preview || '').slice(0, 20) }}
          </option>
        </select>
      </div>
    </div>

    <div v-if="!call && !loading" class="card">
      <div class="empty">
        <p>{{ callError || '상담현황에서 통화를 선택하세요.' }}</p>
        <button class="btn btn-sm" @click="navigate('/stt')">상담현황으로 이동</button>
      </div>
    </div>

    <template v-if="call">
      <div class="grid-2">
        <!-- ============ STT 원문 ============ -->
        <section class="card">
          <div class="card-head">
            <h3>STT 원문 대화
              <span class="sub">{{ call.call_id }} · {{ fmtDateTime(call.started_at) }} · {{ fmtDuration(call.duration_sec) }}</span>
            </h3>
            <span v-if="isDone" class="badge badge-gray">상담완료</span>
            <span v-else class="badge badge-blue"><span class="dot pulse" /> 상담 진행</span>
          </div>
          <div ref="chatBox" class="card-body scroll chat-box">
            <ChatTranscript :utterances="call.utterances" :customer-name="call.customer_name" :agent-name="agentName(call.agent_name)" />
          </div>
          <div v-if="canAddUtterance" class="add-utt">
            <div class="who">
              <button :class="{ on: utt.speaker === 'CUSTOMER' }" type="button" @click="utt.speaker = 'CUSTOMER'">고객</button>
              <button :class="{ on: utt.speaker === 'AGENT' }" type="button" @click="utt.speaker = 'AGENT'">상담사</button>
            </div>
            <textarea v-model="utt.text" rows="2" :placeholder="(utt.speaker === 'CUSTOMER' ? '고객' : '상담사') + ' 대화 입력 (Enter 추가 · Shift+Enter 줄바꿈)'" @keydown="onUttKey" />
            <button class="btn btn-sm btn-primary" type="button" :disabled="!utt.text.trim() || utt.saving" @click="submitUtterance">추가</button>
            <p v-if="utt.error" class="err">{{ utt.error }}</p>
          </div>
          <div v-else-if="auth.isSysAdmin.value && isDone" class="add-utt-note">상담완료된 통화는 대화를 추가할 수 없습니다.</div>
        </section>

        <!-- ============ 상담이력 ============ -->
        <section class="card">
          <div class="card-head">
            <h3>상담이력 <span v-if="isDone && consult" class="sub">#{{ consult.consult_id }} 등록 완료</span></h3>
            <span v-if="isDone" class="badge badge-green">조회 전용</span>
          </div>
          <fieldset class="card-body form" :disabled="isDone || submitting">
            <p v-if="isDone && consult" class="meta">
              등록 {{ fmtDateTime(consult.created_at) }} · 등록자 {{ consult.registered_by || '-' }} · 상담사 {{ agentName(consult.agent_name) }}
            </p>
            <div class="field-row">
              <div class="field"><label>고객번호</label><input :value="call.customer_id" readonly class="mono"></div>
              <div class="field"><label>고객명</label><input :value="call.customer_name" readonly></div>
            </div>
            <div class="field-row">
              <div class="field">
                <label>상담유형</label>
                <select v-model="form.consult_type">
                  <option v-for="t in CONSULT_TYPES" :key="t">{{ t }}</option>
                </select>
              </div>
              <div class="field">
                <label>접촉채널</label>
                <select v-model="form.channel">
                  <option v-for="c in CHANNELS" :key="c">{{ c }}</option>
                </select>
              </div>
            </div>
            <div class="field">
              <label>접촉결과</label>
              <div class="inline">
                <label v-for="r in RESULTS" :key="r" class="chk"><input v-model="form.result_status" type="radio" :value="r"> {{ r }}</label>
              </div>
            </div>
            <div class="field">
              <label class="sum-label">
                <span>상담요약 <span class="req">*</span></span>
                <a v-if="!isDone" href="#" :class="{ busy: drafting }" @click.prevent="draftSummary">{{ drafting ? '초안 작성 중…' : 'STT에서 초안 만들기' }}</a>
              </label>
              <textarea v-model="form.summary" rows="6" :disabled="drafting"
                        :placeholder="drafting ? '상담 대화 전체를 상담사 관점으로 요약하고 있습니다…' : '[문의] 고객 문의 내용\n[확인] 상담 중 확인한 사항\n[처리] 조치 및 결과'" />
              <p v-if="draftInfo && !isDone" class="draft-info">{{ draftInfo }}</p>
            </div>
            <p v-if="submitError" class="err">{{ submitError }}</p>
            <div v-if="!isDone" class="form-actions">
              <button class="btn btn-primary btn-lg" type="button" :disabled="!canSubmit" @click="submit">
                {{ submitting ? '등록 중…' : '상담이력 등록' }}
              </button>
            </div>
          </fieldset>
        </section>
      </div>

      <!-- ============ 에이전트 실행 (LangGraph) ============ -->
      <section ref="graphCard" class="card graph-card">
        <div class="card-head">
          <h3>장애 알림 에이전트 실행 과정 <span class="sub">LangGraph{{ run ? ' · run #' + run.run_id : '' }}</span></h3>
          <div class="toolbar">
            <StatusBadge v-if="run" :value="run.status" />
            <button v-if="isDone && consult && auth.isSysAdmin.value && (!run || run.status !== 'RUNNING')" class="btn btn-sm btn-ghost" @click="rerun">재실행</button>
          </div>
        </div>
        <div class="card-body">
          <div class="graph-box"><AgentGraph :run="run" /></div>
          <div v-if="run" class="run-detail">
            <AgentTimeline :run="run" />
            <div v-if="run.status !== 'RUNNING'" class="run-foot">
              <span class="muted">{{ run.llm_used ? 'LLM(Ollama) 분석 사용' : '규칙 기반 분석 (LLM 미사용/실패)' }}</span>
              <button v-if="run.incident_id" class="btn btn-sm" @click="navigate('/incident', { id: run.incident_id })">
                장애 #{{ run.incident_id }} 상세 보기 →
              </button>
            </div>
          </div>
          <p v-else class="muted hint-run">상담이력을 등록하면 장애감지 → 중복제보 통합 → 심각도 판별 → 메신저 전송 순서로 실행되며, 실행 중인 단계가 그래프에 표시됩니다.</p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.back { font-size: 12.5px; font-weight: 600; display: inline-block; margin-bottom: 4px; }
.chat-box { height: 460px; }
.add-utt { display: grid; grid-template-columns: auto 1fr auto; gap: 8px; align-items: end; padding: 12px 16px; border-top: 1px solid var(--line); background: var(--surface-2); border-radius: 0 0 var(--radius) var(--radius); }
.add-utt textarea { min-height: 0; resize: none; }
.add-utt .err { grid-column: 1 / -1; margin: 0; }
.who { display: flex; flex-direction: column; gap: 4px; }
.who button { font: inherit; font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: 6px; border: 1px solid var(--line-strong); background: var(--surface); color: var(--text-2); cursor: pointer; }
.who button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.add-utt-note { padding: 10px 16px; border-top: 1px solid var(--line); font-size: 12px; color: var(--text-3); }
.form { border: none; margin: 0; min-width: 0; }
.form .field > input, .form .field > select, .form .field > textarea { width: 100%; }
.form textarea { min-height: 130px; }
.form:disabled select, .form:disabled textarea { background: var(--surface-2); color: var(--text); opacity: 1; }
.sum-label { display: flex; justify-content: space-between; }
.sum-label a { font-weight: 500; }
.sum-label a.busy { pointer-events: none; color: var(--text-3); }
.draft-info { margin: 6px 0 0; font-size: 12px; color: var(--text-3); }
.meta { font-size: 12px; color: var(--text-3); margin: 0 0 12px; }
.graph-card { margin-top: 16px; }
.graph-box { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px 4px; background: var(--surface-2); }
.run-detail { margin-top: 16px; }
.run-foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 12px; margin-top: 4px; flex-wrap: wrap; }
.hint-run { margin: 12px 0 0; font-size: 12.5px; }
.empty p { margin: 0 0 12px; }
.err { margin: 0 0 10px; }
</style>
