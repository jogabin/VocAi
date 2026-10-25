import http from './http'

/* ---------- 사용자관리 ---------- */
export async function fetchUsers(params = {}) {
  const { data } = await http.get('/voc-users', { params })
  return data
}

export async function createUser(payload) {
  const { data } = await http.post('/voc-users', payload)
  return data
}

export async function updateUser(id, payload) {
  const { data } = await http.patch(`/voc-users/${id}`, payload)
  return data
}

/* ---------- 인사정보 ---------- */
export async function fetchEmployees(params = {}) {
  const { data } = await http.get('/employees', { params })
  return data
}

export async function fetchEmployee(id) {
  const { data } = await http.get(`/employees/${id}`)
  return data
}

export async function createEmployee(payload) {
  const { data } = await http.post('/employees', payload)
  return data
}

export async function updateEmployee(id, payload) {
  const { data } = await http.patch(`/employees/${id}`, payload)
  return data
}

/* ---------- 고객정보 ---------- */
export async function fetchCustomers(params = {}) {
  const { data } = await http.get('/customers', { params })
  return data
}

export async function createCustomer(payload) {
  const { data } = await http.post('/customers', payload)
  return data
}

export async function updateCustomer(id, payload) {
  const { data } = await http.patch(`/customers/${encodeURIComponent(id)}`, payload)
  return data
}

/* ---------- 상담데이터 등록 (통화 + 대화 생성, 상담상태 '진행') ---------- */
export async function createConsultData(payload) {
  const { data } = await http.post('/stt', payload)
  return data
}

/** 대화내용 엑셀 읽기: 저장하지 않고 [{ speaker, text }] 목록만 받음 */
export async function readDialogExcel(file) {
  const body = new FormData()
  body.append('file', file)
  const { data } = await http.post('/stt/dialog-excel', body)
  return data
}

/** 대화내용 엑셀 양식 내려받기 (로그인 토큰이 필요해서 링크 대신 Blob 으로 받음) */
export async function downloadDialogTemplate() {
  const { data } = await http.get('/stt/dialog-excel/template', { responseType: 'blob' })
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = '상담대화_양식.xlsx'
  a.click()
  URL.revokeObjectURL(url)
}
