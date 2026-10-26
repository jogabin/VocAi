const pad = (n) => String(n).padStart(2, '0')

export function fmtTime(v) {
  if (!v) return '-'
  const d = new Date(v)
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

export function fmtDateTime(v) {
  if (!v) return '-'
  const d = new Date(v)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// 날짜 입력(type=date) 값: YYYY-MM-DD (브라우저 현지 날짜). days 만큼 앞/뒤로 이동
export function fmtDate(v = new Date(), days = 0) {
  const d = new Date(v)
  d.setDate(d.getDate() + days)
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

export function fmtDuration(sec) {
  if (sec == null) return '-'
  return `${Math.floor(sec / 60)}분 ${pad(sec % 60)}초`
}

export function fmtOffset(sec) {
  return `${pad(Math.floor(sec / 60))}:${pad(sec % 60)}`
}

export function timeAgo(v) {
  if (!v) return '-'
  const s = Math.max(0, Math.floor((Date.now() - new Date(v).getTime()) / 1000))
  if (s < 60) return `${s}초 전`
  if (s < 3600) return `${Math.floor(s / 60)}분 전`
  if (s < 86400) return `${Math.floor(s / 3600)}시간 전`
  return `${Math.floor(s / 86400)}일 전`
}

export const SEVERITY_LABEL = { P1: '긴급', P2: '높음', P3: '보통', P4: '낮음' }

// 장애 처리상태 (화면 표시)
export const PROCESS_STATUSES = ['대기중', '진행중', '미대상', '처리완료']
export const PROCESS_BADGE = { 대기중: 'badge-red', 진행중: 'badge-amber', 미대상: 'badge-gray', 처리완료: 'badge-green' }
