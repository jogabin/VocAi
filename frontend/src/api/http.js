import axios from 'axios'
import { getToken, notifyUnauthorized } from './authToken'

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  timeout: 10000, // 10초
})

// 로그인 토큰을 모든 요청에 첨부
http.interceptors.request.use((config) => {
  const token = getToken()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 응답 에러를 한 곳에서 일관되게 처리
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    // FastAPI 에러 형식: { "detail": "..." }
    const detail = error.response?.data?.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((d) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join(' / ') // 422 검증 오류
          : detail
            ? JSON.stringify(detail)
            : error.message
    // 세션 만료 → 로그인 화면으로 (로그인 요청 자체의 실패는 제외)
    if (status === 401 && !String(error.config?.url || '').includes('/auth/login')) {
      notifyUnauthorized(message)
    }
    const err = new Error(message)
    err.status = status
    err.response = error.response
    return Promise.reject(err)
  },
)

export default http
