/* 초기 분석(incident_alert.analysis) 문장을 화면용 구조로 나눔
   - LLM은 3~5문장 서술형, 규칙 기반은 '우선 점검: a, b' 같은 줄 단위로 씀 (backend/app/agents/severity.py)
   - 저장 형식은 그대로 두고 화면에서만 나눔: 상황·추정 원인 / 점검 항목 / 참고(유사 사례·관찰)
   - 메신저 알림 본문(backend/app/services/analysis_format.py)과 같은 규칙이므로 한쪽을 바꾸면 같이 고침 */

const CAUSE_RE = /가능성|의심|보입니다|추정|원인|문제보다/
const NOTE_RE = /ERR-\d+|유사 사례|과거 사례|유사한 과거|모니터링|추이|관찰/
const ACTION_RE = /(세요|십시오)\.?$|것이 좋습니다\.?$/

function splitSentences(text) {
  return text
    .split(/\n+|(?<=[다요]\.)\s+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

// 괄호 안 쉼표는 나누지 않음
function splitTopLevel(text) {
  const out = []
  let depth = 0
  let cur = ''
  for (const ch of text) {
    if ('(（['.includes(ch)) depth++
    if (')）]'.includes(ch)) depth = Math.max(0, depth - 1)
    if (ch === ',' && depth === 0) { out.push(cur); cur = '' } else cur += ch
  }
  out.push(cur)
  return out
}

function cleanItem(s) {
  return s.trim().replace(/[,，]$/, '').replace(/(입니다|등입니다)\.?$/, '').replace(/\.$/, '').trim()
}

// '점검 포인트는 ① a ② b 입니다.' / '점검 포인트는 a, b, c입니다.' / '우선 점검: a, b'
function checkItems(sentence) {
  const m = sentence.match(/점검 ?포인트(?:는|은)?\s*:?\s*(.+)$/) || sentence.match(/^우선 점검\s*:\s*(.+)$/)
  if (!m) return null
  const body = m[1]
  const parts = /[①-⑳]/.test(body) ? body.split(/[①-⑳]/).slice(1) : splitTopLevel(body)
  return parts.map(cleanItem).filter(Boolean)
}

export function structureAnalysis(text) {
  const result = { causes: [], checks: [], notes: [] }
  if (!text) return result
  for (const s of splitSentences(text)) {
    if (/^재현 환경\s*:/.test(s)) continue            // 재현 정보 항목에 이미 표시
    const items = checkItems(s)
    if (items) result.checks.push(...items)
    else if (NOTE_RE.test(s)) result.notes.push(s)
    else if (CAUSE_RE.test(s)) result.causes.push(s)
    else if (ACTION_RE.test(s)) result.checks.push(cleanItem(s))
    else result.causes.push(s)
  }
  return result
}
