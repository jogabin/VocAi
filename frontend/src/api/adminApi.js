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
