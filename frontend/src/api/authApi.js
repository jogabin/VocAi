import http from './http'

export async function login(loginId, password) {
  const { data } = await http.post('/auth/login', { login_id: loginId, password })
  return data
}

export async function fetchMe() {
  const { data } = await http.get('/auth/me')
  return data
}

export async function logout() {
  const { data } = await http.post('/auth/logout')
  return data
}

export async function changePassword(currentPassword, newPassword) {
  const { data } = await http.post('/auth/password', { current_password: currentPassword, new_password: newPassword })
  return data
}
