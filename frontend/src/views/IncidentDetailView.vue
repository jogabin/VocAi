<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { fetchIncident, addIncidentAction, fetchManualNotify, sendManualNotify, closeIncident } from '../api/vocApi'
import { useHashRoute, navigate } from '../composables/useHashRoute'
import { useAuth } from '../composables/useAuth'
import { fmtDateTime, timeAgo, incidentNo, PROCESS_STATUSES, PROCESS_BADGE } from '../utils/format'
import SeverityBadge from '../components/voc/SeverityBadge.vue'

/* 장애 상세정보 (#/incident?id=N) - 메신저 알림의 '장애 상세 보기' 링크로도 열림
   - 장애 상세 · 제보 상담 · 메신저 전송 정보 · 처리 이력
   - IT담당자 권한(장애 알림 수신·처리자)만 처리 상태(대기중/진행중/오탐/처리완료)와 처리 내용을 등록
   - 관찰·미대상(알림 미대상) 장애: 센터관리자·시스템관리자가 IT담당자를 지정해 수동 알림 전송(→ 대기중)
     하거나 알림 없이 종결(미대상 / 오탐). 메시지는 자동 작성되고 수정할 수 있음 */

const { query } = useHashRoute()
const auth = useAuth()

const ENV_LABEL = { os: 'OS', device: '기기', app_version: '앱 버전', browser: '브라우저', error_code: '오류코드', error_message: '오류문구', occurred_at_text: '발생시점' }

const inc = ref(null)
const loading = ref(false)
const error = ref('')
const msgIdx = ref(0)
const form = reactive({ process_status: '진행중', content: '', saving: false, error: '', done: '' })

const canProcess = computed(() => auth.isItStaff.value)
const isObserving = computed(() => ['관찰', '미대상'].includes(inc.value?.status))

/* ---------- 관찰 장애: 수동 알림 전송 · 알림 없이 종결 ---------- */
const manual = reactive({
  mode: 'notify', loading: false, saving: false, error: '', done: '',
  grades: [], severity: '', staff: [], picks: {}, title: '', body: '', memo: '',
  closeType: '미대상', reason: '',
})

async function loadManual(severity) {
  if (!inc.value || !isObserving.value || !auth.isManager.value) return
  manual.loading = true
  manual.error = ''
  try {
    const d = await fetchManualNotify(inc.value.incident_id, severity)
    manual.grades = d.grades
    manual.severity = d.severity
    manual.staff = d.staff
    manual.picks = Object.fromEntries(d.recommended.map((r) => [r.emp_id, r.recipient_type]))
    manual.title = d.title
    manual.body = d.body
  } catch (e) {
    manual.error = e.message
  } finally {
    manual.loading = false
  }
}

function togglePick(empId, on) {
  const picks = { ...manual.picks }
  if (on) picks[empId] = picks[empId] || '1차'
  else delete picks[empId]
  manual.picks = picks
}

async function sendManual() {
  manual.error = ''
  manual.done = ''
  const recipients = Object.entries(manual.picks).map(([id, type]) => ({ emp_id: Number(id), recipient_type: type }))
  if (!recipients.length) { manual.error = '수신할 IT담당자를 1명 이상 선택하세요.'; return }
  if (!manual.title.trim() || !manual.body.trim()) { manual.error = '메시지 제목과 내용을 입력하세요.'; return }
  if (!window.confirm(`IT담당자 ${recipients.length}명에게 알림을 보내고 처리상태를 '대기중'으로 바꿀까요?`)) return
  manual.saving = true
  try {
    const r = await sendManualNotify(inc.value.incident_id, {
      severity: manual.severity, recipients, title: manual.title.trim(), body: manual.body, memo: manual.memo.trim() || null,
    })
    inc.value = r
    msgIdx.value = 0
    const sr = r.send_result || {}
    manual.done = `알림 ${sr.sent ?? recipients.length}건 전송 (${sr.transport || '-'})${sr.failed ? ` · 실패 ${sr.failed}건` : ''} → 처리상태 대기중`
  } catch (e) {
    manual.error = e.message
  } finally {
    manual.saving = false
  }
}

async function closeManual() {
  manual.error = ''
  manual.done = ''
  if (manual.reason.trim().length < 2) { manual.error = '종결 사유를 입력하세요.'; return }
  manual.saving = true
  try {
    inc.value = await closeIncident(inc.value.incident_id, { false_positive: manual.closeType === '오탐', content: manual.reason.trim() })
    manual.done = `알림 없이 '${manual.closeType}'(으)로 종결했습니다.`
    manual.reason = ''
    manual.mode = 'notify'
    manual.closeType = '오탐'                // 미대상 종결 후에는 오탐 재분류만 남음
  } catch (e) {
    manual.error = e.message
  } finally {
    manual.saving = false
  }
}
const envRows = computed(() => Object.entries(inc.value?.env_info || {}).filter(([, v]) => v))
const selectedMsg = computed(() => inc.value?.messages?.[msgIdx.value] || null)

async function load() {
  const id = Number(query.value.id)
  if (!id) { inc.value = null; error.value = '장애 번호가 없습니다.'; return }
  loading.value = true
  try {
    inc.value = await fetchIncident(id)
    error.value = ''
    msgIdx.value = 0
    form.process_status = ['대기중', '관찰', '미대상'].includes(inc.value.process_status) ? '진행중' : inc.value.process_status
    form.content = ''
    manual.done = ''
    manual.mode = 'notify'
    manual.closeType = inc.value.status === '미대상' ? '오탐' : '미대상'
    loadManual()
  } catch (e) {
    inc.value = null
    error.value = e.message
  } finally {
    loading.value = false
  }
}

watch(() => query.value.id, load, { immediate: true })

async function submit() {
  form.error = ''
  form.done = ''
  const content = form.content.trim()
  if (['처리완료', '오탐'].includes(form.process_status) && !content) {
    form.error = `'${form.process_status}'은(는) 처리 내용을 입력해야 합니다. (유사 장애 분석에 사용됩니다)`
    return
  }
  form.saving = true
  try {
    inc.value = await addIncidentAction(inc.value.incident_id, { process_status: form.process_status, content: content || null })
    form.content = ''
    form.done = `처리 상태를 '${inc.value.process_status}'(으)로 등록했습니다.`
  } catch (e) {
    form.error = e.message
  } finally {
    form.saving = false
  }
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <a href="#" class="back" @click.prevent="navigate('/monitor')">← 장애 알림 모니터</a>
        <h2 v-if="inc">
          <span class="mono muted">{{ incidentNo(inc.incident_id) }}</span> {{ inc.title }}
        </h2>
        <h2 v-else>장애 상세정보</h2>
        <div v-if="inc" class="head-badges">
          <SeverityBadge :value="inc.severity" />
          <span class="badge" :class="PROCESS_BADGE[inc.process_status]">{{ inc.process_status }}</span>
          <span v-if="inc.mass_signal" class="badge badge-red">동일유형 다발 · 대규모 신호</span>
          <span class="muted small">최초 제보 {{ fmtDateTime(inc.first_reported_at) }} · 최근 {{ timeAgo(inc.last_reported_at) }}</span>
        </div>
      </div>
      <button class="btn btn-sm" :disabled="loading" @click="load">새로고침</button>
    </div>

    <div v-if="!inc" class="card"><div class="empty">{{ loading ? '불러오는 중…' : error }}</div></div>

    <template v-if="inc">
      <div class="grid-detail">
        <!-- ============ 장애 정보 ============ -->
        <div class="col">
          <section class="card">
            <div class="card-head"><h3>장애 정보</h3></div>
            <div class="card-body">
              <dl class="kv wide">
                <dt>오류유형</dt><dd>{{ inc.error_type }}</dd>
                <dt>접촉채널</dt><dd>{{ inc.channel || '-' }}</dd>
                <dt>등급</dt><dd><SeverityBadge :value="inc.severity" /><span v-if="inc.notified_severity" class="muted small"> · 알림 발송 등급 {{ inc.notified_severity }}</span></dd>
                <dt>누적 제보</dt><dd>{{ inc.report_count }}건</dd>
                <dt>담당자</dt><dd>{{ inc.owner_name || '-' }}<span v-if="inc.dept" class="muted"> · {{ inc.dept }}</span><span v-if="inc.system_name" class="muted"> · {{ inc.system_name }}</span></dd>
                <dt>처리자</dt><dd>{{ inc.resolver_name || '-' }}<span v-if="inc.resolved_at" class="muted"> · {{ fmtDateTime(inc.resolved_at) }}</span></dd>
                <dt>증상</dt><dd>{{ inc.symptoms || '-' }}</dd>
                <dt>재현 정보</dt>
                <dd>
                  <span v-if="!envRows.length" class="muted">-</span>
                  <span v-for="[k, v] in envRows" :key="k" class="chip">{{ ENV_LABEL[k] || k }}: {{ v }}</span>
                </dd>
                <dt>판정 근거</dt>
                <dd>
                  <span class="muted small">판별기준 {{ inc.criteria_version || '-' }}</span>
                  <div><span v-for="r in (inc.applied_rules || [])" :key="r" class="chip mono">{{ r }}</span></div>
                </dd>
              </dl>
              <div class="block-title">초기 분석</div>
              <pre class="block">{{ inc.analysis || '-' }}</pre>
              <template v-if="(inc.similar_cases || []).length">
                <div class="block-title">과거 유사 사례</div>
                <ul class="cases">
                  <li v-for="c in inc.similar_cases" :key="c.incident_id">
                    <a href="#" @click.prevent="navigate('/incident', { id: c.incident_id })">{{ incidentNo(c.incident_id) }} {{ c.title }}</a>
                    <span class="badge badge-gray">{{ c.status }}</span>
                    <span class="muted small">유사도 {{ c.similarity }}</span>
                    <div v-if="c.resolution" class="muted small">{{ c.resolution }}</div>
                  </li>
                </ul>
              </template>
            </div>
          </section>

          <section class="card">
            <div class="card-head"><h3>제보 상담 <span class="sub">{{ (inc.reports || []).length }}건</span></h3></div>
            <div class="tbl-wrap">
              <table class="tbl">
                <thead><tr><th>상담</th><th>등록</th><th>고객</th><th>상담사</th><th>상담요약</th><th>유사도</th></tr></thead>
                <tbody>
                  <tr v-for="r in inc.reports" :key="r.report_id" @click="r.call_id && navigate('/consult', { call: r.call_id })">
                    <td class="mono">#{{ r.consult_id }}</td>
                    <td class="nowrap muted">{{ fmtDateTime(r.created_at) }}</td>
                    <td class="nowrap">{{ r.customer_name }}</td>
                    <td class="nowrap">{{ (r.agent_name || '').replace(/^상담사\s*/, '') }}</td>
                    <td><div class="ellipsis">{{ r.summary }}</div></td>
                    <td class="mono muted">{{ r.similarity ?? '-' }}</td>
                  </tr>
                </tbody>
              </table>
              <div v-if="!(inc.reports || []).length" class="empty">연결된 상담이 없습니다.</div>
            </div>
          </section>
        </div>

        <!-- ============ 처리 등록 / 이력 ============ -->
        <div class="col">
          <section class="card process-card">
            <div class="card-head">
              <h3>장애 처리</h3>
              <span class="badge" :class="PROCESS_BADGE[inc.process_status]">현재 {{ inc.process_status }}</span>
            </div>
            <!-- 관찰 · 미대상: 센터관리자 수동 알림 / 종결 -->
            <div v-if="isObserving && !auth.isManager.value" class="card-body">
              <p class="muted small note">
                알림 미대상 장애입니다. 센터관리자가 내용을 확인해 IT담당자에게 알림을 보내면 '대기중'이 되고,
                이후 IT담당자가 처리 내용을 등록합니다.
              </p>
            </div>
            <div v-else-if="isObserving" class="card-body manual">
              <p class="muted small hint">
                <template v-if="inc.status === '관찰'">알림 미대상(관찰) 장애입니다. 내용을 확인해 IT담당자에게 알림을 보내거나 알림 없이 종결하세요.</template>
                <template v-else>미대상으로 종결된 장애입니다. 필요하면 IT담당자에게 알림을 보내거나 오탐으로 다시 분류할 수 있습니다.</template>
              </p>
              <div class="mode-tabs">
                <button type="button" :class="{ on: manual.mode === 'notify' }" @click="manual.mode = 'notify'">IT담당자 알림 전송</button>
                <button type="button" :class="{ on: manual.mode === 'close' }" @click="manual.mode = 'close'">알림 없이 종결</button>
              </div>
              <fieldset :disabled="manual.saving || manual.loading">
                <template v-if="manual.mode === 'notify'">
                  <div class="field">
                    <label>알림 등급</label>
                    <select v-model="manual.severity" @change="loadManual(manual.severity)">
                      <option v-for="g in manual.grades" :key="g.code" :value="g.code">{{ g.code }} {{ g.label }}{{ g.code === inc.severity ? ' (현재)' : '' }}</option>
                    </select>
                    <span v-if="manual.severity && manual.severity !== inc.severity" class="muted small">등급을 {{ inc.severity }} → {{ manual.severity }}(으)로 바꿔 전송합니다.</span>
                  </div>
                  <div class="field">
                    <label>수신 IT담당자 <span class="muted small">추천 수신자(1차 담당 · 2차 유사 장애 처리자)가 미리 선택됩니다</span></label>
                    <ul class="staff">
                      <li v-for="e in manual.staff" :key="e.emp_id" :class="{ on: manual.picks[e.emp_id] }">
                        <label class="chk">
                          <input type="checkbox" :checked="!!manual.picks[e.emp_id]" @change="togglePick(e.emp_id, $event.target.checked)">
                          <strong>{{ e.emp_name }}</strong>
                          <span class="muted small">{{ e.duty_role || '-' }} · {{ e.dept }} · {{ (e.duty_error_types || []).join(', ') }}</span>
                          <span v-if="!e.on_duty" class="badge badge-gray">근무 외</span>
                        </label>
                        <select v-if="manual.picks[e.emp_id]" v-model="manual.picks[e.emp_id]" class="type-sel">
                          <option value="1차">1차</option>
                          <option value="2차">2차</option>
                        </select>
                      </li>
                    </ul>
                  </div>
                  <div class="field">
                    <label>메시지 <span class="muted small">자동 작성된 내용을 수정할 수 있습니다</span></label>
                    <input v-model="manual.title" type="text" maxlength="200">
                    <textarea v-model="manual.body" rows="14" class="mono-text" />
                  </div>
                  <div class="field">
                    <label>메모 <span class="muted small">(선택) 처리 이력에 함께 남깁니다</span></label>
                    <input v-model="manual.memo" type="text" maxlength="1000" placeholder="예: 업무 차단 지속, 금전 영향 확인 필요">
                  </div>
                  <div class="form-actions">
                    <button class="btn btn-primary" type="button" @click="sendManual">{{ manual.saving ? '전송 중…' : '알림 전송 → 대기중' }}</button>
                  </div>
                </template>
                <template v-else>
                  <div class="field">
                    <label>종결 구분</label>
                    <div class="close-pick">
                      <label v-if="inc.status === '관찰'" class="chk"><input v-model="manual.closeType" type="radio" value="미대상"> 미대상 <span class="muted small">(알림 필요 없음)</span></label>
                      <label class="chk"><input v-model="manual.closeType" type="radio" value="오탐"> 오탐 <span class="muted small">(고객 실수·정상 동작, 이후 오탐 대조에 사용)</span></label>
                    </div>
                  </div>
                  <div class="field">
                    <label>종결 사유 <span class="req">*</span></label>
                    <textarea v-model="manual.reason" rows="4" placeholder="예: 단일 고객 일시 현상으로 재현되지 않음, 고객 안내로 종결" />
                  </div>
                  <div class="form-actions">
                    <button class="btn" type="button" @click="closeManual">{{ manual.saving ? '처리 중…' : '알림 없이 종결' }}</button>
                  </div>
                </template>
              </fieldset>
              <p v-if="manual.loading" class="muted small">추천 수신자·메시지 작성 중…</p>
              <p v-if="manual.error" class="err">{{ manual.error }}</p>
              <p v-if="manual.done" class="ok small">{{ manual.done }}</p>
            </div>

            <fieldset v-else class="card-body" :disabled="!canProcess || form.saving">
              <div class="field">
                <label>처리 상태</label>
                <div class="status-pick">
                  <label v-for="s in PROCESS_STATUSES" :key="s" :class="['pick-' + s, { on: form.process_status === s }]">
                    <input v-model="form.process_status" type="radio" :value="s"> {{ s }}
                  </label>
                </div>
              </div>
              <div class="field">
                <label>처리 내용 <span v-if="['처리완료', '오탐'].includes(form.process_status)" class="req">*</span></label>
                <textarea v-model="form.content" rows="5" placeholder="원인과 조치 내용을 입력하세요. 처리완료 내용은 이후 유사 장애 분석과 메신저 알림의 과거 해결 사례로 사용됩니다." />
              </div>
              <p v-if="form.error" class="err">{{ form.error }}</p>
              <p v-if="form.done" class="ok small">{{ form.done }}</p>
              <div class="form-actions">
                <button class="btn btn-primary" type="button" @click="submit">{{ form.saving ? '등록 중…' : '처리 등록' }}</button>
              </div>
              <p v-if="!canProcess" class="muted small note">장애 처리 등록은 IT담당자만 할 수 있습니다.</p>
            </fieldset>
          </section>

          <section class="card">
            <div class="card-head"><h3>처리 이력 <span class="sub">{{ (inc.actions || []).length }}건</span></h3></div>
            <div class="card-body">
              <ol v-if="(inc.actions || []).length" class="actions">
                <li v-for="a in inc.actions" :key="a.action_id">
                  <div class="a-head">
                    <span class="badge" :class="PROCESS_BADGE[a.process_status]">{{ a.process_status }}</span>
                    <strong>{{ a.actor_name || a.actor_login }}</strong>
                    <span v-if="a.dept" class="muted small">{{ a.dept }}</span>
                    <span class="muted small">{{ fmtDateTime(a.created_at) }}</span>
                  </div>
                  <p v-if="a.content" class="a-body">{{ a.content }}</p>
                </li>
              </ol>
              <div v-else class="empty">아직 처리 이력이 없습니다.</div>
            </div>
          </section>
        </div>
      </div>

      <!-- ============ 메신저 전송 정보 ============ -->
      <section v-if="(inc.messages || []).length" class="card msg-card">
        <div class="card-head"><h3>메신저 전송 정보 <span class="sub">{{ inc.messages.length }}건</span></h3></div>
        <div class="msg-grid">
          <div class="tbl-wrap">
            <table class="tbl">
              <thead><tr><th>전송 시각</th><th>구분</th><th>수신자</th><th>방식 · 결과</th></tr></thead>
              <tbody>
                <tr v-for="(m, idx) in inc.messages" :key="m.msg_id" :class="{ selected: idx === msgIdx }" @click="msgIdx = idx">
                  <td class="nowrap muted">{{ fmtDateTime(m.sent_at) }}</td>
                  <td><span class="badge" :class="m.recipient_type === '2차' ? 'badge-amber' : 'badge-blue'">{{ m.recipient_type || '-' }}</span></td>
                  <td class="nowrap"><strong>{{ m.receiver_name || m.receiver }}</strong><span class="muted small"> {{ m.role || '' }} · {{ m.dept || '' }}</span></td>
                  <td class="nowrap"><span class="mono small">{{ m.transport }}</span> <span class="badge" :class="m.status === 'SENT' ? 'badge-green' : 'badge-red'">{{ m.status === 'SENT' ? '전송' : '실패' }}</span></td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="selectedMsg" class="msg-view">
            <div class="msg-title">{{ selectedMsg.title }}</div>
            <pre class="block">{{ selectedMsg.body }}</pre>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.back { font-size: 12.5px; font-weight: 600; display: inline-block; margin-bottom: 4px; }
.head-badges { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
.small { font-size: 12px; }
.grid-detail { display: grid; grid-template-columns: minmax(0, 7fr) minmax(340px, 5fr); gap: 10px; align-items: start; }
@media (max-width: 1080px) { .grid-detail { grid-template-columns: 1fr; } }
.col { display: flex; flex-direction: column; gap: 10px; min-width: 0; }
.col > .card + .card { margin-top: 0; }
.kv.wide { grid-template-columns: 90px 1fr; margin-bottom: 14px; }
.chip { display: inline-block; padding: 1px 7px; margin: 0 4px 3px 0; border-radius: 6px; background: var(--surface-2); border: 0; font-size: 12px; }
.block-title { font-size: 12px; font-weight: 700; color: var(--text-2); margin: 12px 0 6px; }
.cases { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.cases .badge { margin: 0 4px; }
.process-card fieldset { border: none; margin: 0; min-width: 0; }
.process-card textarea { width: 100%; }
.status-pick { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.status-pick label { display: flex; align-items: center; justify-content: center; gap: 4px; border: 1px solid var(--line-strong); border-radius: var(--radius); padding: 8px 4px; font-size: 13px; font-weight: 600; color: var(--text-2); cursor: pointer; }
.status-pick input { display: none; }
.status-pick label.on { color: #fff; }
.status-pick .pick-대기중.on { background: var(--p1); border-color: var(--p1); }
.status-pick .pick-진행중.on { background: var(--warn); border-color: var(--warn); }
.status-pick .pick-오탐.on { background: var(--p4); border-color: var(--p4); }
.manual .hint { margin: 0 0 10px; }
.mode-tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; margin-bottom: 12px; }
.mode-tabs button { font: inherit; font-size: 13px; font-weight: 700; padding: 8px; border: 1px solid var(--line-strong); border-radius: var(--radius); background: #fff; color: var(--text-2); cursor: pointer; }
.mode-tabs button.on { background: var(--accent); border-color: var(--accent); color: #fff; }
.manual fieldset { border: none; margin: 0; padding: 0; min-width: 0; }
.manual select, .manual input[type=text], .manual textarea { width: 100%; }
.manual input + textarea { margin-top: 6px; }
.mono-text { font-family: var(--mono); font-size: 12px; line-height: 1.5; }
.staff { list-style: none; margin: 0; padding: 0; max-height: 220px; overflow: auto; border: 1px solid var(--line); border-radius: var(--radius); }
.staff li { display: flex; align-items: center; justify-content: space-between; gap: 8px; padding: 6px 10px; border-bottom: 1px solid var(--line); }
.staff li:last-child { border-bottom: none; }
.staff li.on { background: var(--accent-soft); }
.staff .chk { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; cursor: pointer; }
.manual .staff .type-sel { width: 70px; flex-shrink: 0; }
.close-pick { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.close-pick .chk { display: flex; align-items: center; gap: 6px; cursor: pointer; }
.status-pick .pick-처리완료.on { background: var(--ok); border-color: var(--ok); }
fieldset:disabled .status-pick label { cursor: not-allowed; opacity: .6; }
.note { margin: 8px 0 0; }
.err { margin: 0 0 10px; }
.ok { margin: 0 0 10px; }
.actions { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.actions li { border-left: 3px solid var(--line-strong); padding-left: 10px; }
.a-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.a-body { margin: 4px 0 0; font-size: 12.5px; color: var(--text-2); white-space: pre-wrap; }
.msg-card { margin-top: 10px; }
.msg-grid { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 0; }
@media (max-width: 1080px) { .msg-grid { grid-template-columns: 1fr; } }
.msg-view { border-left: 1px solid var(--line); padding: 12px 16px; min-width: 0; }
.msg-title { font-weight: 700; font-size: 13px; margin-bottom: 8px; }
.msg-view pre.block { max-height: 520px; overflow: auto; }
</style>
