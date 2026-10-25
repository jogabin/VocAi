<script setup>
import { computed, ref, watch } from 'vue'
import { fetchMonitorCounts, fetchMonitorSummary, fetchIncidents, fetchAgentRuns } from '../api/vocApi'
import { useHashRoute, navigate } from '../composables/useHashRoute'
import { usePolling } from '../composables/usePolling'
import { fmtTime, timeAgo, PROCESS_BADGE } from '../utils/format'
import SeverityBadge from '../components/voc/SeverityBadge.vue'
import StatusBadge from '../components/voc/StatusBadge.vue'

/* 장애 알림 모니터
   - 상단 건수 박스 5개 (긴급 장애가 있으면 깜빡임)
   - 박스를 누르면 아래에 해당 장애 목록, 목록을 누르면 장애 상세정보 화면 */

const { query } = useHashRoute()

// 예전 링크(#/monitor?incident=N)는 장애 상세정보로
if (query.value.incident) navigate('/incident', { id: query.value.incident })

const PERIODS = [
  { key: 'today', label: '오늘' },
  { key: '7d', label: '최근 7일' },
  { key: 'all', label: '전체' },
]
const BOXES = [
  { key: 'registered', label: '장애 정보 등록', desc: '에이전트가 등록한 전체 장애' },
  { key: 'urgent', label: '긴급 장애', desc: '최상위 등급 · 미처리' },
  { key: 'messaged', label: '메신저 알림 전송', desc: '담당자에게 알림이 나간 장애' },
  { key: 'same_type', label: '동일유형 장애', desc: '60분 내 동일 유형 다발 (대규모 신호)' },
  { key: 'resolved', label: '장애 처리 완료', desc: 'IT담당자 처리완료' },
]

const period = ref(PERIODS.some((p) => p.key === query.value.period) ? query.value.period : 'today')
const box = ref(BOXES.some((b) => b.key === query.value.box) ? query.value.box : 'registered')
const counts = ref(null)
const summary = ref(null)
const list = ref([])
const runs = ref([])
const error = ref('')
const updatedAt = ref(null)

const currentBox = computed(() => BOXES.find((b) => b.key === box.value))
const urgentLabel = computed(() => counts.value ? `긴급 장애 (${counts.value.top_grade} ${counts.value.top_grade_label})` : '긴급 장애')

async function refresh() {
  try {
    const [c, l, s, r] = await Promise.all([
      fetchMonitorCounts(period.value),
      fetchIncidents({ box: box.value, period: period.value, limit: 200 }),
      fetchMonitorSummary(),
      fetchAgentRuns(8),
    ])
    counts.value = c
    list.value = l
    summary.value = s
    runs.value = r
    updatedAt.value = new Date()
    error.value = ''
  } catch (e) {
    error.value = e.message
  }
}

const { enabled: autoRefresh, refresh: refreshNow } = usePolling(refresh, 3000)

function pickBox(key) {
  box.value = key
}
watch([box, period], () => {
  navigate('/monitor', { box: box.value, period: period.value })
  list.value = []
  refreshNow()
})

// 주소(#/monitor?box=..&period=..)로 바뀐 경우에도 박스·기간 반영
watch(() => [query.value.box, query.value.period], ([b, p]) => {
  if (b && b !== box.value && BOXES.some((x) => x.key === b)) box.value = b
  if (p && p !== period.value && PERIODS.some((x) => x.key === p)) period.value = p
})

function openIncident(i) {
  navigate('/incident', { id: i.incident_id })
}

const ragLabel = computed(() => {
  const r = summary.value?.rag
  if (!r) return ''
  const mode = { pgvector: 'pgvector', array: '임베딩(배열)', missing: '미구성' }[r.vector_mode] || r.vector_mode
  return r.embed_ok === false ? `RAG ${mode} · 문자열 유사도 대체` : `RAG ${mode} · ${r.model}`
})
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>장애 알림 모니터</h2>
        <p>장애 알림 건수를 한눈에 확인합니다. 건수 박스를 누르면 아래에 해당 장애 목록이 나오고, 목록을 누르면 장애 상세정보로 이동합니다.</p>
      </div>
      <div class="toolbar">
        <span v-if="summary" class="badge" :class="summary.llm_enabled ? 'badge-blue' : 'badge-gray'">
          {{ summary.llm_enabled ? 'LLM ' + summary.llm_desc : '규칙 기반 모드' }}
        </span>
        <span v-if="summary" class="badge" :class="summary.rag?.embed_ok === false ? 'badge-amber' : 'badge-gray'">{{ ragLabel }}</span>
        <span v-if="summary" class="badge badge-gray">메신저 {{ summary.messenger_mode }}</span>
      </div>
    </div>

    <div class="mon-bar">
      <div class="period">
        <button v-for="p in PERIODS" :key="p.key" :class="{ on: period === p.key }" @click="period = p.key">{{ p.label }}</button>
      </div>
      <div class="toolbar">
        <label class="chk"><input v-model="autoRefresh" type="checkbox"> 자동 새로고침(3초)</label>
        <span class="muted small">{{ updatedAt ? fmtTime(updatedAt) + ' 갱신' : '' }}</span>
        <button class="btn btn-sm" @click="refreshNow">새로고침</button>
      </div>
    </div>

    <p v-if="error" class="err" style="margin: 0 0 12px">{{ error }}</p>

    <!-- ============ 건수 박스 ============ -->
    <div class="boxes">
      <button v-for="b in BOXES" :key="b.key" class="box" :class="['box-' + b.key, {
        on: box === b.key,
        blink: b.key === 'urgent' && counts && counts.urgent > 0,
      }]" @click="pickBox(b.key)">
        <span class="box-label">{{ b.key === 'urgent' ? urgentLabel : b.label }}</span>
        <strong class="box-num">{{ counts ? counts[b.key] : '-' }}<small>건</small></strong>
        <span class="box-desc">{{ b.desc }}</span>
      </button>
    </div>

    <!-- ============ 선택한 박스의 장애 목록 ============ -->
    <section class="card">
      <div class="card-head">
        <h3>{{ box === 'urgent' ? urgentLabel : currentBox.label }} 목록 <span class="sub">{{ list.length }}건 · {{ PERIODS.find((p) => p.key === period).label }}</span></h3>
        <span class="muted small">행을 누르면 장애 상세정보로 이동</span>
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr><th>장애번호</th><th>등급</th><th>처리상태</th><th>장애 제목</th><th>오류유형 · 채널</th><th>누적 제보</th><th>담당자</th><th>메신저</th><th>최근 제보</th></tr>
          </thead>
          <tbody>
            <tr v-for="i in list" :key="i.incident_id" @click="openIncident(i)">
              <td class="mono">#{{ i.incident_id }}</td>
              <td><SeverityBadge :value="i.severity" /></td>
              <td><span class="badge" :class="PROCESS_BADGE[i.process_status]">{{ i.process_status }}</span></td>
              <td class="wrap"><strong>{{ i.title }}</strong></td>
              <td class="nowrap">{{ i.error_type }} · {{ i.channel || '-' }}</td>
              <td class="nowrap">
                {{ i.report_count }}건
                <span v-if="i.mass_signal" class="badge badge-red">동일유형 다발</span>
              </td>
              <td class="nowrap">{{ i.owner_name || '-' }}<span v-if="i.dept" class="muted small"> · {{ i.dept }}</span></td>
              <td class="nowrap"><span v-if="i.message_count" class="badge badge-blue">{{ i.message_count }}건 전송</span><span v-else class="muted">-</span></td>
              <td class="nowrap muted">{{ timeAgo(i.last_reported_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!list.length" class="empty">해당하는 장애가 없습니다.</div>
      </div>
    </section>

    <!-- ============ 에이전트 실행 현황 ============ -->
    <section class="card">
      <div class="card-head">
        <h3>최근 에이전트 실행 <span class="sub">상담이력 등록 시 자동 실행</span></h3>
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead><tr><th>실행</th><th>시각</th><th>고객</th><th>상태</th><th>결과</th></tr></thead>
          <tbody>
            <tr v-for="r in runs" :key="r.run_id" @click="r.call_id && navigate('/consult', { call: r.call_id })">
              <td class="mono">#{{ r.run_id }}</td>
              <td class="nowrap muted">{{ fmtTime(r.started_at) }}</td>
              <td class="nowrap">{{ r.customer_name || '-' }} <span class="mono muted small">{{ r.call_id }}</span></td>
              <td><StatusBadge :value="r.status" /></td>
              <td class="wrap muted">{{ r.outcome || '실행 중…' }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!runs.length" class="empty">실행 이력이 없습니다.</div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.small { font-size: 12px; }
.mon-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px; flex-wrap: wrap; }
.period { display: inline-flex; background: var(--surface); border: 1px solid var(--line-strong); border-radius: 9px; padding: 3px; }
.period button { font: inherit; font-size: 13px; font-weight: 600; color: var(--text-2); background: none; border: none; border-radius: 6px; padding: 5px 14px; cursor: pointer; }
.period button.on { background: var(--text); color: #fff; }

.boxes { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
@media (max-width: 1100px) { .boxes { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) { .boxes { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.box { --c: var(--accent); --soft: var(--accent-soft); font: inherit; text-align: left; cursor: pointer; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px 12px; box-shadow: var(--shadow); display: flex; flex-direction: column; gap: 4px; position: relative; overflow: hidden; transition: border-color .15s, box-shadow .15s, transform .1s; }
.box::before { content: ''; position: absolute; left: 0; top: 0; bottom: 0; width: 4px; background: var(--c); }
.box:hover { border-color: var(--line-strong); transform: translateY(-1px); }
.box.on { border-color: var(--c); box-shadow: 0 0 0 2px var(--soft), var(--shadow); }
.box-label { font-size: 13px; font-weight: 700; color: var(--text-2); }
.box-num { font-size: 34px; font-weight: 800; line-height: 1.1; color: var(--c); letter-spacing: -0.02em; }
.box-num small { font-size: 14px; font-weight: 600; margin-left: 3px; color: var(--text-3); }
.box-desc { font-size: 11.5px; color: var(--text-3); }
.box-registered { --c: var(--accent); --soft: var(--accent-soft); }
.box-urgent { --c: var(--p1); --soft: var(--p1-soft); }
.box-messaged { --c: #7c4dff; --soft: #efe9ff; }
.box-same_type { --c: var(--p2); --soft: var(--p2-soft); }
.box-resolved { --c: var(--ok); --soft: var(--ok-soft); }
.box.blink { animation: urgent-blink 1s ease-in-out infinite; border-color: var(--p1); }
.box.blink .box-num { color: var(--p1); }
@keyframes urgent-blink {
  0%, 100% { background: var(--surface); box-shadow: 0 0 0 0 rgba(217, 45, 32, 0); }
  50% { background: var(--p1-soft); box-shadow: 0 0 0 4px rgba(217, 45, 32, .25); }
}
@media (prefers-reduced-motion: reduce) { .box.blink { animation: none; background: var(--p1-soft); } }
</style>
