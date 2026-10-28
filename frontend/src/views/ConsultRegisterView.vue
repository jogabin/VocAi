<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { fetchSttCall, createConsult, fetchAgentRun, rerunAgent, draftConsultSummary } from '../api/vocApi'
import { useHashRoute, navigate } from '../composables/useHashRoute'
import { useAuth } from '../composables/useAuth'
import { downloadDialogExcel } from '../api/adminApi'
import { fmtDateTime, fmtDuration, incidentNo } from '../utils/format'
import ChatTranscript from '../components/voc/ChatTranscript.vue'
import AgentTimeline from '../components/voc/AgentTimeline.vue'
import AgentGraph from '../components/voc/AgentGraph.vue'
import StatusBadge from '../components/voc/StatusBadge.vue'

/* 상담이력등록
   - STT 원문 대화 확인, 시스템관리자는 [원문대화 복사등록]으로 같은 대화를 상담데이터 등록(SCR-10) 화면에 채워 새 상담으로 등록
   - 상담이력(고객번호·고객명 고정, 상담유형·접촉채널·접촉결과·상담요약 입력) 등록 → 상담완료 처리
   - 상담요약은 STT 원문 전체를 상담사 관점([문의]/[확인]/[처리])으로 요약한 초안을 자동으로 채움 (API: summary-draft)
   - 등록 즉시 장애 알림 에이전트(LangGraph) 실행 과정을 하단 그래프로 표시
   - 상담완료 건은 등록된 정보와 마지막 에이전트 실행 결과만 확인 */

const { query } = useHashRoute()
const auth = useAuth()

const CONSULT_TYPES = ['전산오류문의', '일반문의', '불만', '기타']
const CHANNELS = ['앱', '웹', 'ARS', '기타']
const RESULTS = ['완료', '이관', '보류']

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

const chatBox = ref(null)
function scrollChat() {
  nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight })
}

/* ---------- 원문대화 복사등록: 상담데이터 등록(SCR-10, 시스템관리자) 화면을 이 통화의 고객·상담사·대화로 채워 열기 ---------- */
const canCopyDialog = computed(() => auth.isSysAdmin.value && !!call.value?.utterances?.length)   // 상담완료 건도 가능

function copyDialog() {
  navigate('/consult-data', { copy: call.value.call_id })
}

/* ---------- 원문대화 엑셀추출: 상담데이터 등록의 엑셀 업로드 양식(화자 | 대화내용)으로 내려받기 ---------- */
const exporting = ref(false)
const exportError = ref('')

async function exportDialog() {
  exporting.value = true
  exportError.value = ''
  try {
    await downloadDialogExcel(call.value.call_id)
  } catch (e) {
    exportError.value = e.message
  } finally {
    exporting.value = false
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
        <!-- 통화 선택 기능은 사용하지 않음 (상담현황에서 통화를 눌러 진입). 현재 통화만 표시 -->
        <label class="muted" style="font-size: 12px">진행 중인 상담</label>
        <select disabled style="min-width: 280px" title="상담현황에서 통화를 선택하세요">
          <option>{{ call ? `${call.call_id} · ${call.customer_name}` : '상담현황에서 통화 선택' }}</option>
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
          <div v-if="canCopyDialog" class="copy-bar">
            <span class="muted">이 원문 대화를 그대로 복사해 상담데이터 등록 화면에서 새 상담으로 등록하거나, 업로드 양식 엑셀로 내려받습니다.</span>
            <div class="copy-actions">
              <button class="btn btn-sm" type="button" @click="copyDialog">원문대화 복사등록</button>
              <button class="btn btn-sm" type="button" :disabled="exporting" @click="exportDialog">
                {{ exporting ? '추출 중…' : '원문대화 엑셀추출' }}
              </button>
            </div>
            <span v-if="exportError" class="export-error">{{ exportError }}</span>
          </div>
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
                <button v-if="!isDone" class="btn btn-sm" type="button" :disabled="drafting" @click="draftSummary">{{ drafting ? '초안 작성 중…' : '상담요약 초안 작성' }}</button>
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
              <span class="muted">{{ run.llm_used ? 'LLM(Claude) 분석 사용' : '규칙 기반 분석 (LLM 미사용/실패)' }}</span>
              <button v-if="run.incident_id" class="btn btn-sm" @click="navigate('/incident', { id: run.incident_id })">
                장애 {{ incidentNo(run.incident_id) }} 상세 보기 →
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
.copy-bar { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px 16px; border-top: 1px solid var(--line); background: var(--surface-2); border-radius: 0 0 var(--radius) var(--radius); font-size: 12px; flex-wrap: wrap; }
.copy-actions { display: flex; gap: 6px; flex-shrink: 0; }
.export-error { flex-basis: 100%; color: var(--p1); }
.form { border: none; margin: 0; min-width: 0; }
.form .field > input, .form .field > select, .form .field > textarea { width: 100%; }
.form textarea { min-height: 130px; }
.form:disabled select, .form:disabled textarea { background: var(--surface-2); color: var(--text); opacity: 1; }
.sum-label { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
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
