<script setup>
import { computed, ref } from 'vue'
import { fetchSttCalls } from '../api/vocApi'
import { navigate } from '../composables/useHashRoute'
import { usePolling } from '../composables/usePolling'
import { fmtDate, fmtDateTime, fmtDuration } from '../utils/format'

/* 상담현황 목록: 조회 기간(통화 시작일)의 상담 진행 중인 통화와 상담완료 통화를 실시간(5초)으로 표시.
   행을 누르면 상담이력등록 화면으로 이동합니다. 상담이력이 등록된 통화는 [등록완료] 버튼으로 등록 내용을 봅니다. */

const TABS = [
  { key: '', label: '전체' },
  { key: '진행', label: '진행' },
  { key: '상담완료', label: '상담완료' },
]
const all = ref([])
const tab = ref('')
const keyword = ref('')
const dateFrom = ref(fmtDate(new Date(), -6))   // 기본 조회 기간: 오늘 포함 최근 7일
const dateTo = ref(fmtDate())
const loading = ref(false)
const error = ref('')
const updatedAt = ref(null)

const rows = computed(() => all.value.filter((c) => !tab.value || c.consult_status === tab.value))
const counts = computed(() => ({
  '': all.value.length,
  진행: all.value.filter((c) => c.consult_status === '진행').length,
  상담완료: all.value.filter((c) => c.consult_status === '상담완료').length,
}))

async function load() {
  loading.value = true
  try {
    if (dateFrom.value && dateTo.value && dateFrom.value > dateTo.value) {
      error.value = '조회 시작일이 종료일보다 늦습니다.'
      return
    }
    all.value = await fetchSttCalls({
      keyword: keyword.value.trim(), dateFrom: dateFrom.value, dateTo: dateTo.value, limit: 200,
    })
    updatedAt.value = new Date()
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function open(c) {
  navigate('/consult', { call: c.call_id })
}

const agentName = (n) => (n || '').replace(/^상담사\s*/, '')

usePolling(load, 5000)   // 화면 진입 시 즉시 1회 + 5초마다
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>상담현황</h2>
        <p>조회 기간의 상담 진행 중인 통화와 상담완료 통화를 실시간으로 보여줍니다. 통화를 누르면 상담이력등록 화면으로, [등록완료]를 누르면 등록된 상담이력으로 이동합니다.</p>
      </div>
      <div class="toolbar">
        <span class="live"><span class="dot pulse" /> 5초마다 자동 갱신<template v-if="updatedAt"> · {{ fmtDateTime(updatedAt).slice(11) }}</template></span>
      </div>
    </div>

    <div class="seg">
      <button v-for="t in TABS" :key="t.key" :class="{ on: tab === t.key }" @click="tab = t.key">
        {{ t.label }} <span class="cnt">{{ counts[t.key] }}</span>
      </button>
      <form class="seg-right" @submit.prevent="load">
        <span class="dates">
          <input v-model="dateFrom" type="date" aria-label="조회 시작일" @change="load">
          <span class="muted">~</span>
          <input v-model="dateTo" type="date" aria-label="조회 종료일" @change="load">
        </span>
        <input v-model="keyword" placeholder="고객명 · 통화ID · 대화내용" style="width: 220px; padding: 6px 10px">
        <button class="btn btn-sm" type="submit" :disabled="loading">조회</button>
      </form>
    </div>

    <div class="card">
      <p v-if="error" class="err card-body">{{ error }}</p>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr><th>상담상태</th><th>통화 ID</th><th>고객번호</th><th>고객명</th><th>상담사</th><th>통화 시작</th><th>통화 시간</th><th>고객 첫 발화</th><th>상담이력</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in rows" :key="c.call_id" :class="{ 'on-air': c.consult_status === '진행' }" @click="open(c)">
              <td class="nowrap">
                <span v-if="c.consult_status === '진행'" class="badge badge-blue"><span class="dot pulse" /> 진행</span>
                <span v-else class="badge badge-gray">상담완료</span>
              </td>
              <td class="mono">{{ c.call_id }}</td>
              <td class="mono muted">{{ c.customer_id }}</td>
              <td class="nowrap"><strong>{{ c.customer_name }}</strong></td>
              <td class="nowrap">{{ agentName(c.agent_name) }}</td>
              <td class="nowrap muted">{{ fmtDateTime(c.started_at) }}</td>
              <td class="nowrap muted">{{ fmtDuration(c.duration_sec) }}</td>
              <td><div class="ellipsis">{{ c.preview }}</div></td>
              <td class="nowrap">
                <button v-if="c.consult_id" class="btn btn-sm btn-done" type="button" @click.stop="open(c)">등록완료</button>
                <span v-else class="go">등록하기 →</span>
              </td>
            </tr>
          </tbody>
        </table>
        <div v-if="!rows.length && !loading" class="empty">조회 기간에 {{ tab ? tab + ' 상태인 상담이 없습니다.' : '상담 내역이 없습니다.' }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.live { font-size: 12px; color: var(--text-3); display: inline-flex; align-items: center; gap: 6px; }
.live .dot { color: var(--ok); }
.badge .dot { width: 6px; height: 6px; }
.dates { display: inline-flex; align-items: center; gap: 6px; }
.dates input { padding: 5px 8px; }
.btn-done { color: var(--ok); border-color: var(--ok); background: var(--ok-soft); font-weight: 600; }
.btn-done:hover:not(:disabled) { background: var(--ok-soft); filter: brightness(0.96); }
.go { font-size: 12.5px; font-weight: 600; color: var(--accent); }
.tbl tbody tr.on-air td:first-child { box-shadow: inset 3px 0 0 var(--accent); }
.err { margin: 0; }
</style>
