<script setup>
import { computed, ref, watch } from 'vue'
import { fetchImprovements } from '../api/vocApi'
import { navigate } from '../composables/useHashRoute'
import { fmtDate, fmtTime, incidentNo } from '../utils/format'
import { usePager } from '../composables/usePager'
import ListPager from '../components/voc/ListPager.vue'

/* 개선의견 목록
   - 장애감지 에이전트가 '개선의견'(해결·완료된 건의 문구·안내·절차 개선 요청)으로 분류한 상담
   - 알림·승인 대상이 아니며 장애 누적에도 넣지 않음. 관련 장애가 있으면 장애 상세정보로 이동 */

const dateFrom = ref(fmtDate(new Date(), -29))
const dateTo = ref(fmtDate())
const list = ref([])
const { page, pages, total, size, pageRows } = usePager(list)
const error = ref('')
const loading = ref(false)
const opened = ref(null)

const rangeLabel = computed(() => {
  if (!dateFrom.value && !dateTo.value) return '전체 기간'
  return `${dateFrom.value || '처음'} ~ ${dateTo.value || '오늘'}`
})

async function refresh() {
  if (dateFrom.value && dateTo.value && dateFrom.value > dateTo.value) {
    error.value = '조회 시작일이 종료일보다 늦습니다.'
    return
  }
  loading.value = true
  try {
    list.value = await fetchImprovements({ dateFrom: dateFrom.value, dateTo: dateTo.value })
    error.value = ''
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
watch([dateFrom, dateTo], refresh, { immediate: true })

function toggle(o) {
  opened.value = opened.value === o.improvement_id ? null : o.improvement_id
}
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>개선의견 목록</h2>
        <p>해결·완료된 건에 대해 화면 문구·안내·절차를 바꿔 달라는 고객 의견입니다. 알림을 보내지 않고 기록만 남기며, 장애 누적 건수에 넣지 않습니다.</p>
      </div>
    </div>

    <div class="bar">
      <div class="dates">
        <span class="dates-label">조회 기간</span>
        <input v-model.lazy="dateFrom" type="date" aria-label="조회 시작일">
        <span class="muted">~</span>
        <input v-model.lazy="dateTo" type="date" aria-label="조회 종료일">
      </div>
      <button class="btn btn-sm" :disabled="loading" @click="refresh">새로고침</button>
    </div>

    <p v-if="error" class="err" style="margin: 0 0 12px">{{ error }}</p>

    <section class="card">
      <div class="card-head">
        <h3>개선의견 <span class="sub">{{ list.length }}건 · {{ rangeLabel }}</span></h3>
        <span class="muted small">행을 누르면 고객 발화를 펼쳐 봅니다</span>
      </div>
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr><th>번호</th><th>등록</th><th>고객</th><th>오류유형 · 채널</th><th>상담요약</th><th>관련 장애</th></tr>
          </thead>
          <tbody>
            <template v-for="o in pageRows" :key="o.improvement_id">
              <tr @click="toggle(o)">
                <td class="mono">#{{ o.improvement_id }}</td>
                <td class="nowrap muted">{{ fmtDate(o.created_at) }} {{ fmtTime(o.created_at) }}</td>
                <td class="nowrap">{{ o.customer_name || '-' }} <span class="mono muted small">{{ o.call_id }}</span></td>
                <td class="nowrap">{{ o.error_type || '-' }} · {{ o.channel || '-' }}</td>
                <td class="wrap pre">{{ o.content }}</td>
                <td class="nowrap">
                  <a v-if="o.related_incident_id" href="" @click.prevent.stop="navigate('/incident', { id: o.related_incident_id })">
                    {{ incidentNo(o.related_incident_id) }} {{ o.related_title }}
                  </a>
                  <span v-else class="muted">-</span>
                </td>
              </tr>
              <tr v-if="opened === o.improvement_id" class="detail">
                <td colspan="6"><div class="pre">{{ o.customer_excerpt || '고객 발화 없음' }}</div></td>
              </tr>
            </template>
          </tbody>
        </table>
        <div v-if="!list.length" class="empty">{{ loading ? '불러오는 중…' : '해당 기간의 개선의견이 없습니다.' }}</div>
      </div>
      <ListPager v-model:page="page" :pages="pages" :total="total" :size="size" />
    </section>
  </div>
</template>

<style scoped>
.small { font-size: 12px; }
.bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 0 10px 12px; flex-wrap: wrap; }
.dates { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.dates-label { font-size: 13px; font-weight: 600; color: var(--text-2); margin-right: 2px; }
.dates input { padding: 5px 8px; }
.pre { white-space: pre-line; }
.detail td { background: var(--surface-2); color: var(--text-2); font-size: 13px; }
</style>
