<script setup>
import { computed, onMounted, ref } from 'vue'
import { fetchDemoReset, runDemoReset } from '../api/adminApi'
import { fmtDateTime } from '../utils/format'

/* 데이터 초기화 (시스템관리자)
   - 시연 데이터(상담·장애·알림·에이전트 실행·개선의견)를 처음 시연 상태로 되돌림. 재배포 없이 화면에서 실행
   - 계정·인사정보·판별기준·고객정보는 그대로 둠
   - 실수로 지우지 않도록 '초기화'를 직접 입력해야 실행 */

const COUNT_LABELS = [
  { key: 'stt_call', label: '통화(STT)' },
  { key: 'consult_history', label: '상담이력' },
  { key: 'incident_alert', label: '장애' },
  { key: 'agent_run', label: '에이전트 실행' },
  { key: 'improvement_opinion', label: '개선의견' },
]

const info = ref(null)
const loadError = ref('')
const confirmText = ref('')
const running = ref(false)
const runError = ref('')
const done = ref(null)

const canRun = computed(() => confirmText.value.trim() === '초기화' && !running.value)

async function load() {
  loadError.value = ''
  try {
    info.value = await fetchDemoReset()
  } catch (e) {
    loadError.value = e.message
  }
}

async function run() {
  if (!canRun.value) return
  running.value = true
  runError.value = ''
  done.value = null
  try {
    done.value = await runDemoReset(confirmText.value.trim())
    confirmText.value = ''
    await load()
  } catch (e) {
    runError.value = e.response?.data?.detail || e.message
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>데이터 초기화</h2>
        <p>시연하며 쌓인 상담·장애·알림 데이터를 처음 시연 상태로 되돌립니다. 재배포 없이 바로 적용됩니다.</p>
      </div>
    </div>

    <div class="grid-2">
      <section class="card">
        <div class="card-head"><h3>초기화 범위</h3></div>
        <div class="card-body">
          <h4 class="sec">처음 시연 상태로 되돌리는 것</h4>
          <ul class="scope">
            <li>상담현황의 통화(STT 원문)와 상담이력</li>
            <li>장애 정보 · 처리 이력 · 메신저 알림 기록</li>
            <li>에이전트 실행 이력 · 개선의견</li>
          </ul>
          <h4 class="sec">그대로 두는 것</h4>
          <ul class="scope keep">
            <li>로그인 계정 · 인사정보 · 고객정보</li>
            <li>판별기준(등급 정의 · 기본 등급 · 조정 규칙)</li>
          </ul>
          <p class="note">기본 직원·고객 중 지운 것이 있으면 시연 데이터와 맞추려고 다시 추가합니다. 고친 내용은 바꾸지 않습니다.</p>

          <h4 class="sec">현재 건수</h4>
          <p v-if="loadError" class="err">{{ loadError }}</p>
          <div v-else-if="info" class="counts">
            <div v-for="c in COUNT_LABELS" :key="c.key" class="count">
              <span>{{ c.label }}</span><strong>{{ info.counts[c.key] ?? '-' }}</strong>
            </div>
          </div>
          <p class="muted last">
            마지막 초기화:
            <template v-if="info?.last">{{ fmtDateTime(info.last.at) }} · {{ info.last.by }}</template>
            <template v-else>기록 없음</template>
          </p>
        </div>
      </section>

      <section class="card">
        <div class="card-head"><h3>초기화 실행</h3></div>
        <div class="card-body">
          <div class="warn">
            <strong>되돌릴 수 없습니다</strong>
            <p>지금까지 등록한 상담이력과 장애 정보가 모두 지워집니다. 다른 사람이 시연 중이 아닌지 먼저 확인하세요.</p>
          </div>
          <div class="field">
            <label for="confirm">확인을 위해 <strong>초기화</strong>를 입력하세요</label>
            <input id="confirm" v-model="confirmText" placeholder="초기화" autocomplete="off" :disabled="running" @keyup.enter="run">
          </div>
          <p v-if="runError" class="err">{{ runError }}</p>
          <div class="form-actions">
            <button class="btn btn-primary btn-lg danger" type="button" :disabled="!canRun" @click="run">
              {{ running ? '초기화 중… (30초 정도 걸립니다)' : '시연 데이터 초기화' }}
            </button>
          </div>
          <div v-if="done" class="ok">
            <strong>초기화했습니다</strong>
            <p>통화 {{ done.counts.stt_call }}건 · 상담이력 {{ done.counts.consult_history }}건 · 장애 {{ done.counts.incident_alert }}건으로 되돌렸습니다.
              과거 장애 검색(RAG) 정보는 첫 상담 등록 때 다시 만들어집니다.</p>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.sec { font-size: 13px; margin: 0 0 6px; }
.scope { margin: 0 0 14px; padding-left: 18px; font-size: 13px; line-height: 1.7; }
.scope.keep { color: var(--text-2); }
.note { font-size: 12px; color: var(--text-3); margin: -6px 0 16px; }
.counts { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 6px; margin-bottom: 12px; }
.count { background: var(--surface-2); border-radius: var(--radius-badge); padding: 8px 12px; display: flex; flex-direction: column; font-size: 12px; color: var(--text-3); }
.count strong { font-size: 17px; color: var(--text); }
.last { font-size: 12px; margin: 0; }
.warn { background: var(--p1-soft); color: var(--p1); border-radius: var(--radius); padding: 12px 14px; margin-bottom: 16px; }
.warn p, .ok p { margin: 4px 0 0; font-size: 13px; color: var(--text); }
.ok { background: var(--ok-soft); color: var(--ok); border-radius: var(--radius); padding: 12px 14px; margin-top: 14px; }
.field input { width: 100%; }
.form-actions { margin-top: 12px; }
.danger { background: var(--p1); border-color: var(--p1); }
.danger:hover:not(:disabled) { background: #b81b28; border-color: #b81b28; }
.err { margin: 8px 0 0; }
</style>
