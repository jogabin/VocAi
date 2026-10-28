import http from './http'

/* ---------- STT 원문조회 API ---------- */
export async function fetchSttCalls({ keyword, registered, consultStatus, dateFrom, dateTo, limit = 50, offset = 0 } = {}) {
  const params = { limit, offset }
  if (keyword) params.keyword = keyword
  if (consultStatus) params.consult_status = consultStatus
  if (dateFrom) params.date_from = dateFrom   // 통화 시작일 (YYYY-MM-DD)
  if (dateTo) params.date_to = dateTo
  if (registered !== undefined && registered !== null && registered !== '') params.registered = registered
  const { data } = await http.get('/stt', { params })
  return data
}

export async function fetchSttCall(callId) {
  const { data } = await http.get(`/stt/${encodeURIComponent(callId)}`)
  return data
}

// 관리자: 상담 진행 중인 통화에 대화 추가 (speaker: CUSTOMER | AGENT)
export async function addUtterance(callId, payload) {
  const { data } = await http.post(`/stt/${encodeURIComponent(callId)}/utterances`, payload)
  return data
}

// 상담요약 초안: STT 원문 전체를 상담사 관점으로 요약 → { summary, source: 'LLM' | '규칙' }
export async function draftConsultSummary(callId) {
  const { data } = await http.post(`/stt/${encodeURIComponent(callId)}/summary-draft`)
  return data
}

/* ---------- 상담이력조회 / 등록 API ---------- */
export async function fetchConsults({ keyword, limit = 20, offset = 0 } = {}) {
  const params = { limit, offset }
  if (keyword) params.keyword = keyword
  const { data } = await http.get('/consults', { params })
  return data
}

// 등록 → { consult, run_id }  (백엔드에서 장애 알림 에이전트가 백그라운드로 실행됨)
export async function createConsult(payload) {
  const { data } = await http.post('/consults', payload)
  return data
}

/* ---------- 업무담당자조회 API ---------- */
export async function fetchOwners(errorType) {
  const { data } = await http.get('/owners', { params: errorType ? { error_type: errorType } : {} })
  return data
}

/* ---------- 장애알림정보 API ---------- */
export async function fetchIncidents({ status, openOnly, box, period, dateFrom, dateTo, limit = 50 } = {}) {
  const params = { limit }
  if (status) params.status = status
  if (openOnly) params.open_only = true
  if (box) params.box = box          // registered | urgent | messaged | same_type | resolved
  if (period) params.period = period // today | 7d | all
  if (dateFrom) params.date_from = dateFrom   // 장애 등록일 (YYYY-MM-DD)
  if (dateTo) params.date_to = dateTo
  const { data } = await http.get('/incidents', { params })
  return data
}

/* ---------- 개선의견 API ---------- */
export async function fetchImprovements({ dateFrom, dateTo, limit = 100 } = {}) {
  const params = { limit }
  if (dateFrom) params.date_from = dateFrom
  if (dateTo) params.date_to = dateTo
  const { data } = await http.get('/improvements', { params })
  return data
}

export async function fetchIncident(incidentId) {
  const { data } = await http.get(`/incidents/${incidentId}`)
  return data
}

export async function createIncident(payload) {
  const { data } = await http.post('/incidents', payload)
  return data
}

export async function updateIncident(incidentId, payload) {
  const { data } = await http.patch(`/incidents/${incidentId}`, payload)
  return data
}

/* ---------- 메신저전송 API ---------- */
export async function sendMessenger(payload) {
  const { data } = await http.post('/messenger/send', payload)
  return data
}

export async function fetchMessengerLogs({ incidentId, limit = 50 } = {}) {
  const params = { limit }
  if (incidentId) params.incident_id = incidentId
  const { data } = await http.get('/messenger/logs', { params })
  return data
}

/* ---------- 에이전트 실행 이력 / 모니터 ---------- */
export async function fetchAgentRuns(limit = 20) {
  const { data } = await http.get('/agent-runs', { params: { limit } })
  return data
}

export async function fetchAgentRun(runId) {
  const { data } = await http.get(`/agent-runs/${runId}`)
  return data
}

export async function rerunAgent(consultId) {
  const { data } = await http.post('/agent-runs', { consult_id: consultId })
  return data
}

// 장애 알림 모니터 건수 박스
export async function fetchMonitorCounts({ dateFrom, dateTo } = {}) {
  const params = {}
  if (dateFrom) params.date_from = dateFrom
  if (dateTo) params.date_to = dateTo
  const { data } = await http.get('/monitor/counts', { params })
  return data
}

// 관찰 장애 수동 알림 (센터관리자·시스템관리자): 미리보기 → 전송 / 알림 없이 종결
export async function fetchManualNotify(incidentId, severity) {
  const { data } = await http.get(`/incidents/${incidentId}/manual-notify`, { params: severity ? { severity } : {} })
  return data
}

export async function sendManualNotify(incidentId, payload) {
  const { data } = await http.post(`/incidents/${incidentId}/manual-notify`, payload)
  return data
}

export async function closeIncident(incidentId, payload) {
  const { data } = await http.post(`/incidents/${incidentId}/close`, payload)
  return data
}

// 장애 상세: 처리 상태(대기중/진행중/오탐/처리완료) · 처리 내용 등록
export async function addIncidentAction(incidentId, payload) {
  const { data } = await http.post(`/incidents/${incidentId}/actions`, payload)
  return data
}

export async function fetchMonitorSummary() {
  const { data } = await http.get('/monitor/summary')
  return data
}

/* ---------- 장애등급 판별기준 ---------- */
export async function fetchCriteria() {
  const { data } = await http.get('/severity-criteria')
  return data
}

export async function createGrade(payload) {
  const { data } = await http.post('/severity-criteria/grades', payload)
  return data
}

export async function updateGrade(code, payload) {
  const { data } = await http.patch(`/severity-criteria/grades/${encodeURIComponent(code)}`, payload)
  return data
}

export async function createBaseRule(payload) {
  const { data } = await http.post('/severity-criteria/base-rules', payload)
  return data
}

export async function updateBaseRule(id, payload) {
  const { data } = await http.patch(`/severity-criteria/base-rules/${id}`, payload)
  return data
}

export async function createAdjustRule(payload) {
  const { data } = await http.post('/severity-criteria/adjust-rules', payload)
  return data
}

export async function updateAdjustRule(code, payload) {
  const { data } = await http.patch(`/severity-criteria/adjust-rules/${encodeURIComponent(code)}`, payload)
  return data
}

/** 텔레그램 봇에게 최근 메시지를 보낸 대화 목록 (인사정보 메신저 ID = chat_id 확인용) */
export async function fetchTelegramChats() {
  const { data } = await http.get('/messenger/telegram/chats')
  return data
}
