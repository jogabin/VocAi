<script setup>
import { computed, ref, watch } from 'vue'
import { fetchMonitorCounts, fetchMonitorSummary, fetchIncidents, fetchAgentRuns } from '../api/vocApi'
import { useHashRoute, navigate } from '../composables/useHashRoute'
import { usePolling } from '../composables/usePolling'
import { fmtDate, fmtTime, timeAgo, incidentNo, PROCESS_BADGE } from '../utils/format'
import mascot from '../assets/mascot.png'
import SeverityBadge from '../components/voc/SeverityBadge.vue'
import StatusBadge from '../components/voc/StatusBadge.vue'
import { usePager } from '../composables/usePager'
import { keepListState, listState } from '../composables/useListState'
import ListPager from '../components/voc/ListPager.vue'

/* 장애 알림 모니터
   - 상단 건수 박스 5개 (긴급 장애가 있으면 깜빡임)
   - 박스를 누르면 아래에 해당 장애 목록, 목록을 누르면 장애 상세정보 화면 */

const { query } = useHashRoute()

// 예전 링크(#/monitor?incident=N)는 장애 상세정보로
if (query.value.incident) navigate('/incident', { id: query.value.incident })

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/
// 조회 기간(장애 등록일): 주소 ?from=&to= 우선, 예전 링크의 period(today/7d/all)도 날짜로 바꿔 반영.
// 기본: 오늘 포함 최근 7일
function initialDates(q) {
  if (DATE_RE.test(q.from || '') || DATE_RE.test(q.to || '')) {
    return [DATE_RE.test(q.from || '') ? q.from : '', DATE_RE.test(q.to || '') ? q.to : '']
  }
  if (q.period === 'today') return [fmtDate(), fmtDate()]
  if (q.period === 'all') return ['', '']
  return [fmtDate(new Date(), -6), fmtDate()]
}
const BOXES = [
  { key: 'registered', label: '장애 정보 등록', desc: '에이전트가 등록한 전체 장애' },
  { key: 'urgent', label: '긴급 장애', desc: '최상위 등급 · 미처리' },
  { key: 'observing', label: '관찰 (확인 대기)', desc: '알림 미대상 · 센터관리자 확인 필요' },
  { key: 'messaged', label: '메신저 알림 전송', desc: '담당자에게 알림이 나간 장애' },
  { key: 'same_type', label: '동일유형 장애', desc: '60분 내 동일 유형 다발 (대규모 신호)' },
  { key: 'resolved', label: '장애 처리 완료', desc: 'IT담당자 처리완료' },
]

// 주소에 조건이 없으면(메뉴로 들어옴) 마지막으로 보던 박스·기간
const saved = listState('monitor')
const fromUrl = ['box', 'from', 'to', 'period'].some((k) => query.value[k] != null)
const [initFrom, initTo] = !fromUrl && 'dateFrom' in saved ? [saved.dateFrom, saved.dateTo] : initialDates(query.value)
const dateFrom = ref(initFrom)
const dateTo = ref(initTo)
const initBox = fromUrl ? query.value.box : saved.box
const box = ref(BOXES.some((b) => b.key === initBox) ? initBox : 'registered')
const counts = ref(null)
const summary = ref(null)
const list = ref([])
const runs = ref([])
const { page, pages, total, size, pageRows, reset } = usePager(list)
const samePlace = saved.box === box.value && saved.dateFrom === dateFrom.value && saved.dateTo === dateTo.value
keepListState('monitor', { box, dateFrom, dateTo, page }, samePlace ? ['page'] : [])
watch(box, reset)
const error = ref('')
const updatedAt = ref(null)

const currentBox = computed(() => BOXES.find((b) => b.key === box.value))
const urgentLabel = computed(() => counts.value ? `긴급 장애 (${counts.value.top_grade} ${counts.value.top_grade_label})` : '긴급 장애')
const rangeLabel = computed(() => {
  if (!dateFrom.value && !dateTo.value) return '전체 기간'
  if (dateFrom.value === dateTo.value) return dateFrom.value
  return `${dateFrom.value || '처음'} ~ ${dateTo.value || '오늘'}`
})

async function refresh() {
  if (dateFrom.value && dateTo.value && dateFrom.value > dateTo.value) {
    error.value = '조회 시작일이 종료일보다 늦습니다.'
    return
  }
  const range = { dateFrom: dateFrom.value, dateTo: dateTo.value }
  try {
    const [c, l, s, r] = await Promise.all([
      fetchMonitorCounts(range),
      fetchIncidents({ box: box.value, ...range, limit: 200 }),
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
watch([box, dateFrom, dateTo], () => {
  navigate('/monitor', { box: box.value, from: dateFrom.value, to: dateTo.value })
  list.value = []
  refreshNow()
})

// 주소(#/monitor?box=..&from=..&to=..)로 바뀐 경우에도 박스·기간 반영
watch(() => [query.value.box, query.value.from, query.value.to], ([b, f, t]) => {
  if (b && b !== box.value && BOXES.some((x) => x.key === b)) box.value = b
  if (f !== undefined && DATE_RE.test(f) && f !== dateFrom.value) dateFrom.value = f
  if (t !== undefined && DATE_RE.test(t) && t !== dateTo.value) dateTo.value = t
})

function openIncident(i) {
  navigate('/incident', { id: i.incident_id })
}

// RAG 표시 색: 문자열 유사도(설정으로 고른 방식)는 연한 초록, 임베딩 실패로 문자열 유사도로 대체 중이면 주황, 그 밖에는 회색
const ragBadge = computed(() => {
  const r = summary.value?.rag
  if (r?.search === 'text') return 'badge-green'
  return r?.embed_ok === false ? 'badge-amber' : 'badge-gray'
})
const ragLabel = computed(() => {
  const r = summary.value?.rag
  if (!r) return ''
  if (r.search === 'text') return 'RAG 문자열 유사도'
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
        <span v-if="summary" class="badge" :class="ragBadge">{{ ragLabel }}</span>
        <span v-if="summary" class="badge badge-gray">메신저 {{ summary.messenger_mode }}</span>
      </div>
    </div>

    <div class="mon-bar">
      <div class="dates">
        <span class="dates-label">조회 기간</span>
        <input v-model.lazy="dateFrom" type="date" aria-label="조회 시작일">
        <span class="muted">~</span>
        <input v-model.lazy="dateTo" type="date" aria-label="조회 종료일">
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
        <h3>{{ box === 'urgent' ? urgentLabel : currentBox.label }} 목록 <span class="sub">{{ list.length }}건 · {{ rangeLabel }}</span></h3>
        <span class="muted small">행을 누르면 장애 상세정보로 이동</span>
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr><th>장애번호</th><th>등급</th><th>처리상태</th><th>장애 제목</th><th>오류유형 · 채널</th><th>누적 제보</th><th>담당자</th><th>메신저</th><th>최근 제보</th></tr>
          </thead>
          <tbody>
            <tr v-for="i in pageRows" :key="i.incident_id" @click="openIncident(i)">
              <td class="mono" style="white-space: nowrap">{{ incidentNo(i.incident_id) }}</td>
              <td><SeverityBadge :value="i.severity" /></td>
              <td><span class="badge" :class="PROCESS_BADGE[i.process_status]">{{ i.process_status }}</span></td>
              <td class="wrap"><strong>{{ i.title }}</strong></td>
              <td class="nowrap">{{ i.error_type }} · {{ i.channel || '-' }}</td>
              <td class="nowrap">
                {{ i.report_count }}건<span class="muted small"> · 고객 {{ i.customer_count || 1 }}명</span>
                <span v-if="i.mass_signal" class="badge badge-red">동일유형 다발</span>
              </td>
              <td class="nowrap">{{ i.owner_name || '-' }}<span v-if="i.dept" class="muted small"> · {{ i.dept }}</span></td>
              <td class="nowrap"><span v-if="i.message_count" class="badge badge-blue">{{ i.message_count }}건 전송</span><span v-else class="muted">-</span></td>
              <td class="nowrap muted">{{ timeAgo(i.last_reported_at) }}</td>
            </tr>
          </tbody>
        </table>
        <div v-if="!list.length" class="empty">
          <img class="empty-mascot" :src="mascot" alt="" width="96" height="96"><br>해당하는 장애가 없습니다.
        </div>
      </div>
      <ListPager v-model:page="page" :pages="pages" :total="total" :size="size" />
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
.mon-bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 0 10px 12px; flex-wrap: wrap; }
.dates { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.dates-label { font-size: 13px; font-weight: 600; color: var(--text-2); margin-right: 2px; }
.dates input { padding: 5px 10px; }

.boxes { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 10px; margin-bottom: 10px; }
@media (max-width: 1100px) { .boxes { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 640px) { .boxes { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.box { font: inherit; text-align: left; cursor: pointer; background: var(--surface); border: 0; border-radius: var(--radius-card); padding: 16px 18px 14px; box-shadow: none; display: flex; flex-direction: column; gap: 4px; position: relative; overflow: hidden; transition: background .15s; }
.box:hover { background: var(--surface-2); }
.box.on { background: var(--accent-soft); }
.box-label { font-size: 12.5px; font-weight: 600; color: var(--text-3); }
.box-num { font-size: 26px; font-weight: 800; line-height: 1.15; color: var(--text); letter-spacing: -0.02em; }
.box-num small { font-size: 13px; font-weight: 600; margin-left: 3px; color: var(--text-3); }
.box-desc { font-size: 11.5px; color: var(--text-3); }
.box.on .box-num { color: var(--accent); }
.box.blink { animation: urgent-blink 1s ease-in-out infinite; }
.box.blink .box-num { color: var(--p1); }
@keyframes urgent-blink {
  0%, 100% { background: var(--surface); }
  50% { background: var(--p1-soft); }
}
@media (prefers-reduced-motion: reduce) { .box.blink { animation: none; background: var(--p1-soft); } }
</style>
