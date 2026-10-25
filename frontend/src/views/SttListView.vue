<script setup>
import { ref, onMounted, watch } from 'vue'
import { fetchSttCalls, fetchSttCall } from '../api/vocApi'
import { navigate } from '../composables/useHashRoute'
import { fmtDateTime, fmtDuration } from '../utils/format'
import ChatTranscript from '../components/voc/ChatTranscript.vue'

const calls = ref([])
const loading = ref(false)
const error = ref('')
const keyword = ref('')
const registered = ref('')   // '' 전체 / 'false' 미등록 / 'true' 등록

const selectedId = ref(null)
const detail = ref(null)
const detailError = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    calls.value = await fetchSttCalls({ keyword: keyword.value.trim(), registered: registered.value })
    if (!selectedId.value && calls.value.length) select(calls.value[0].call_id)
  } catch (e) {
    error.value = e.message
    calls.value = []
  } finally {
    loading.value = false
  }
}

async function select(callId) {
  selectedId.value = callId
  detailError.value = ''
  try {
    detail.value = await fetchSttCall(callId)
  } catch (e) {
    detail.value = null
    detailError.value = e.message
  }
}

watch(registered, load)
onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>STT 대화목록</h2>
        <p>콜센터 통화의 STT 원문을 확인하고, 상담 완료 후 상담이력을 등록합니다.</p>
      </div>
      <div class="toolbar">
        <select v-model="registered">
          <option value="">전체</option>
          <option value="false">상담이력 미등록</option>
          <option value="true">상담이력 등록완료</option>
        </select>
        <input v-model="keyword" placeholder="고객명 · 통화ID · 대화내용" @keyup.enter="load" style="width: 220px" />
        <button class="btn" @click="load" :disabled="loading">조회</button>
      </div>
    </div>

    <div class="grid-2">
      <!-- 통화 목록 -->
      <section class="card">
        <div class="card-head">
          <h3>통화 목록 <span class="sub">{{ calls.length }}건</span></h3>
        </div>
        <p v-if="error" class="err card-body">{{ error }}</p>
        <div class="scroll" style="max-height: calc(100vh - 230px)">
          <table class="tbl">
            <thead>
              <tr><th>통화시각</th><th>고객</th><th>첫 발화</th><th>상태</th></tr>
            </thead>
            <tbody>
              <tr v-for="c in calls" :key="c.call_id" :class="{ selected: c.call_id === selectedId }" @click="select(c.call_id)">
                <td>
                  <div>{{ fmtDateTime(c.started_at) }}</div>
                  <div class="muted mono">{{ c.call_id }}</div>
                </td>
                <td>
                  <div>{{ c.customer_name }}</div>
                  <div class="muted">{{ c.agent_name }}</div>
                </td>
                <td><div class="ellipsis" style="max-width: 220px">{{ c.preview }}</div></td>
                <td>
                  <span v-if="c.consult_id" class="badge badge-green">등록 #{{ c.consult_id }}</span>
                  <span v-else class="badge badge-amber">미등록</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-if="!loading && !calls.length && !error" class="empty">조회된 통화가 없습니다.</div>
          <div v-if="loading" class="empty">불러오는 중...</div>
        </div>
      </section>

      <!-- STT 원문 -->
      <section class="card">
        <template v-if="detail">
          <div class="card-head">
            <h3>{{ detail.customer_name }} 고객 통화 <span class="sub mono">{{ detail.call_id }}</span></h3>
            <button v-if="!detail.consult" class="btn btn-primary btn-sm"
                    @click="navigate('/consult', { call: detail.call_id })">
              이 통화로 상담이력 등록 →
            </button>
            <span v-else class="badge badge-green">상담이력 #{{ detail.consult.consult_id }} 등록완료</span>
          </div>
          <div class="card-body">
            <dl class="kv" style="margin: 0 0 16px">
              <dt>고객ID</dt><dd class="mono">{{ detail.customer_id }}</dd>
              <dt>상담사</dt><dd>{{ detail.agent_name }}</dd>
              <dt>통화시각</dt><dd>{{ fmtDateTime(detail.started_at) }} ({{ fmtDuration(detail.duration_sec) }})</dd>
              <template v-if="detail.consult">
                <dt>상담요약</dt><dd>{{ detail.consult.summary }}</dd>
              </template>
            </dl>
            <div class="scroll" style="max-height: calc(100vh - 380px); padding-right: 4px">
              <ChatTranscript :utterances="detail.utterances" :customer-name="detail.customer_name" :agent-name="detail.agent_name" />
            </div>
          </div>
        </template>
        <p v-else-if="detailError" class="err card-body">{{ detailError }}</p>
        <div v-else class="empty">왼쪽 목록에서 통화를 선택하세요.</div>
      </section>
    </div>
  </div>
</template>
