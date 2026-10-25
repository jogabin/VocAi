import http from './http'

// 목록 조회: 값이 있는 조건만 쿼리스트링으로 전달
export async function fetchUsers({ email, name, limit = 10, offset = 0 } = {}) {
  const params = { limit, offset }
  if (email) params.email = email
  if (name) params.name = name

  const { data } = await http.get('/users', { params })
  return data
}

// 단건 조회
export async function fetchUser(userId) {
  const { data } = await http.get(`/users/${userId}`)
  return data
}