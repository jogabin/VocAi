<script setup>
import { onMounted, ref } from 'vue'
import { fetchDemoData, runDemoData } from '../api/adminApi'
import { navigate } from '../composables/useHashRoute'
import { fmtDateTime } from '../utils/format'
import SeverityBadge from '../components/voc/SeverityBadge.vue'

/* 시연 데이터 등록 (시스템관리자)
   - 대규모 장애 신호 시연 4건(sql/15_demo_large_signal.sql)을 등록
   - 사전 제보 2건은 상담이력 등록 + 장애 알림 에이전트 실제 실행까지 마쳐 상담완료로, 나머지 2건은 상담현황에 '진행'으로
   - 이미 등록돼 있으면 그 4건과 그 상담으로 생긴 상담이력·에이전트 실행·장애를 지우고 다시 등록
   - 같은 증상 제보는 60분 안에 이어져야 하나로 묶이므로 시연 직전에 등록 */

const items = ref([])
const loadError = ref('')
const running = ref(false)
const runError = ref('')
const doneAt = ref(null)

async function load() {
  loadError.value = ''
  try {
    items.value = (await fetchDemoData()).items
  } catch (e) {
    loadError.value = e.message
  }
}

async function run() {
  if (running.value) return
  if (items.value.some((i) => i.registered)
      && !window.confirm('이미 등록된 시연 데이터 4건과 그 상담으로 생긴 상담이력·장애를 지우고 다시 등록합니다. 계속할까요?')) return
  running.value = true
  runError.value = ''
  doneAt.value = null
  try {
    items.value = (await runDemoData()).items
    doneAt.value = new Date()
  } catch (e) {
    runError.value = e.response?.data?.detail || e.message
    await load()
  } finally {
    running.value = false
  }
}

function open(i) {
  if (i.registered) navigate('/consult', { call: i.call_id })
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>시연 데이터 등록</h2>
        <p>대규모 장애 신호 시연용 상담 4건을 등록합니다. 사전 제보 2건은 상담이력 등록과 에이전트 판별까지 마쳐 두고, 나머지 2건은 시연 때 상담이력을 등록하도록 상담현황에 남깁니다.</p>
      </div>
      <div class="toolbar">
        <button class="btn btn-primary" type="button" :disabled="running" @click="run">
          {{ running ? '등록 중… (에이전트 실행, 1분 정도)' : items.some((i) => i.registered) ? '시연 데이터 다시 등록' : '시연 데이터 등록' }}
        </button>
      </div>
    </div>

    <div class="notice">
      <strong>시연 직전에 등록하세요</strong>
      <p>같은 증상 제보는 60분 안에 이어져야 하나의 장애로 묶입니다. 다시 등록하면 이 4건과 그 상담으로 생긴 상담이력·에이전트 실행·장애를 지우고 새로 넣습니다. 다른 상담 데이터는 그대로 둡니다.</p>
    </div>

    <p v-if="loadError || runError" class="err">{{ runError || loadError }}</p>
    <p v-if="doneAt" class="ok">{{ fmtDateTime(doneAt) }} 등록했습니다. 상담현황에서 진행 중인 2건으로 시연하세요.</p>

    <section class="card">
      <div class="tbl-wrap">
        <table class="tbl">
          <thead>
            <tr><th>통화 ID</th><th>시나리오</th><th>등록 방식</th><th>고객 · 상담사</th><th>상담상태</th><th>등급</th><th>에이전트 결과</th></tr>
          </thead>
          <tbody>
            <tr v-for="i in items" :key="i.call_id" :class="{ link: i.registered }" @click="open(i)">
              <td class="mono nowrap">{{ i.call_id }}</td>
              <td><strong>{{ i.title }}</strong><div class="muted small">{{ i.file }}</div></td>
              <td class="nowrap">
                <span v-if="i.pre" class="badge badge-blue">상담완료 + 에이전트 실행</span>
                <span v-else class="badge badge-gray">상담현황만 (시연 때 등록)</span>
              </td>
              <td class="nowrap">{{ i.registered ? `${i.customer_name} · ${i.agent_name}` : '-' }}</td>
              <td class="nowrap">
                <span v-if="!i.registered" class="muted">미등록</span>
                <span v-else-if="i.consult_status === '진행'" class="badge badge-amber">진행</span>
                <span v-else class="badge badge-gray">상담완료</span>
              </td>
              <td class="nowrap">
                <SeverityBadge v-if="i.severity" :value="i.severity" />
                <span v-else class="muted">-</span>
              </td>
              <td class="wrap small">
                <template v-if="i.run_id">
                  <span v-if="i.incident_no" class="mono">{{ i.incident_no }}</span>
                  <span v-if="i.report_count" class="muted"> · 제보 {{ i.report_count }}건 · 고객 {{ i.customer_count }}명</span>
                  <span v-if="i.mass_signal" class="badge badge-red">대규모 신호</span>
                  <div class="muted">{{ i.outcome || '실행 중…' }}</div>
                </template>
                <span v-else class="muted">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
    <p class="muted small foot">행을 누르면 상담이력등록 화면으로 이동합니다.</p>
  </div>
</template>

<style scoped>
.notice { background: var(--warn-soft); color: var(--warn); border-radius: var(--radius); padding: 12px 14px; margin-bottom: 12px; }
.notice p { margin: 4px 0 0; font-size: 13px; color: var(--text); }
.ok { background: var(--ok-soft); color: var(--ok); border-radius: var(--radius); padding: 10px 14px; margin: 0 0 12px; font-size: 13px; font-weight: 600; }
.err { margin: 0 0 12px; }
tr.link { cursor: pointer; }
.small { font-size: 12px; }
.wrap { min-width: 260px; }
.foot { margin-top: 8px; }
</style>
