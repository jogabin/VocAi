<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { fetchIncident, addIncidentAction } from '../api/vocApi'
import { useHashRoute, navigate } from '../composables/useHashRoute'
import { useAuth } from '../composables/useAuth'
import { fmtDateTime, timeAgo, PROCESS_STATUSES, PROCESS_BADGE } from '../utils/format'
import SeverityBadge from '../components/voc/SeverityBadge.vue'

/* 장애 상세정보 (#/incident?id=N) - 메신저 알림의 '장애 상세 보기' 링크로도 열림
   - 장애 상세 · 제보 상담 · 메신저 전송 정보 · 처리 이력
   - IT담당자 권한(장애 알림 수신·처리자)만 처리 상태(대기중/진행중/미대상/처리완료)와 처리 내용을 등록 */

const { query } = useHashRoute()
const auth = useAuth()

const ENV_LABEL = { os: 'OS', device: '기기', app_version: '앱 버전', browser: '브라우저', error_code: '오류코드', error_message: '오류문구', occurred_at_text: '발생시점' }

const inc = ref(null)
const loading = ref(false)
const error = ref('')
const msgIdx = ref(0)
const form = reactive({ process_status: '진행중', content: '', saving: false, error: '', done: '' })

const canProcess = computed(() => auth.isItStaff.value)
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
    form.process_status = inc.value.process_status === '대기중' ? '진행중' : inc.value.process_status
    form.content = ''
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
  if (['처리완료', '미대상'].includes(form.process_status) && !content) {
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
          <span class="mono muted">#{{ inc.incident_id }}</span> {{ inc.title }}
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
                    <a href="#" @click.prevent="navigate('/incident', { id: c.incident_id })">#{{ c.incident_id }} {{ c.title }}</a>
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
            <fieldset class="card-body" :disabled="!canProcess || form.saving">
              <div class="field">
                <label>처리 상태</label>
                <div class="status-pick">
                  <label v-for="s in PROCESS_STATUSES" :key="s" :class="['pick-' + s, { on: form.process_status === s }]">
                    <input v-model="form.process_status" type="radio" :value="s"> {{ s }}
                  </label>
                </div>
              </div>
              <div class="field">
                <label>처리 내용 <span v-if="['처리완료', '미대상'].includes(form.process_status)" class="req">*</span></label>
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
.grid-detail { display: grid; grid-template-columns: minmax(0, 7fr) minmax(340px, 5fr); gap: 16px; align-items: start; }
@media (max-width: 1080px) { .grid-detail { grid-template-columns: 1fr; } }
.col { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.col > .card + .card { margin-top: 0; }
.kv.wide { grid-template-columns: 90px 1fr; margin-bottom: 14px; }
.chip { display: inline-block; padding: 1px 7px; margin: 0 4px 3px 0; border-radius: 6px; background: var(--surface-2); border: 1px solid var(--line); font-size: 12px; }
.block-title { font-size: 12px; font-weight: 700; color: var(--text-2); margin: 12px 0 6px; }
.cases { margin: 0; padding-left: 18px; display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.cases .badge { margin: 0 4px; }
.process-card fieldset { border: none; margin: 0; min-width: 0; }
.process-card textarea { width: 100%; }
.status-pick { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; }
.status-pick label { display: flex; align-items: center; justify-content: center; gap: 4px; border: 1px solid var(--line-strong); border-radius: 8px; padding: 8px 4px; font-size: 13px; font-weight: 600; color: var(--text-2); cursor: pointer; }
.status-pick input { display: none; }
.status-pick label.on { color: #fff; }
.status-pick .pick-대기중.on { background: var(--p1); border-color: var(--p1); }
.status-pick .pick-진행중.on { background: var(--warn); border-color: var(--warn); }
.status-pick .pick-미대상.on { background: var(--p4); border-color: var(--p4); }
.status-pick .pick-처리완료.on { background: var(--ok); border-color: var(--ok); }
fieldset:disabled .status-pick label { cursor: not-allowed; opacity: .6; }
.note { margin: 8px 0 0; }
.err { margin: 0 0 10px; }
.ok { margin: 0 0 10px; }
.actions { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.actions li { border-left: 3px solid var(--line); padding-left: 10px; }
.a-head { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; font-size: 13px; }
.a-body { margin: 4px 0 0; font-size: 12.5px; color: var(--text-2); white-space: pre-wrap; }
.msg-card { margin-top: 16px; }
.msg-grid { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); gap: 0; }
@media (max-width: 1080px) { .msg-grid { grid-template-columns: 1fr; } }
.msg-view { border-left: 1px solid var(--line); padding: 12px 16px; min-width: 0; }
.msg-title { font-weight: 700; font-size: 13px; margin-bottom: 8px; }
.msg-view pre.block { max-height: 520px; overflow: auto; }
</style>
