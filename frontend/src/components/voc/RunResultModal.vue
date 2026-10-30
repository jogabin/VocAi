<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import SeverityBadge from './SeverityBadge.vue'
import { incidentNo } from '../../utils/format'

/* 장애 판별 결과 팝업 (상담이력등록 SCR-03)
   에이전트 실행이 끝나면 각 단계 결과(run.steps[].output)로
   ① 몇 등급인지 ② 알림을 보냈는지 / 앞으로 어떻게 처리되는지 ③ 어떤 근거로 그렇게 판단했는지를 보여줍니다. */

const props = defineProps({ run: { type: Object, required: true } })
const emit = defineEmits(['close', 'open-incident'])
const showAll = ref(false)

const out = computed(() => {
  const by = {}
  for (const s of props.run.steps || []) if (s.output?.node) by[s.output.node] = s.output
  return by
})
const det = computed(() => out.value.detect || {})
const dd = computed(() => out.value.dedup || null)
const sev = computed(() => out.value.severity || null)
const sent = computed(() => out.value.notify || out.value.record || null)
const grade = computed(() => sent.value?.severity || sev.value?.severity || null)

// 결과 종류: sent(알림 전송) · dup(이미 알림 나간 장애) · observe(관찰) · closed(미대상) · fp(오탐) · normal(장애 아님) · improve(개선의견) · fail
const kind = computed(() => {
  if (props.run.status === 'FAILED') return 'fail'
  if (out.value.improve) return 'improve'
  if (!sev.value) return 'normal'
  if (out.value.notify) return out.value.notify.sent ? 'sent' : 'dup'
  if (sev.value.false_positive) return 'fp'
  if (sent.value?.incident_status === '관찰') return 'observe'
  if (sent.value?.incident_status === '미대상') return 'closed'
  return 'record'
})

const head = computed(() => {
  const g = grade.value
  const no = sent.value?.incident_id ? incidentNo(sent.value.incident_id) : ''
  switch (kind.value) {
    case 'sent': return {
      tone: g === 'P1' ? 'p1' : 'info',
      title: g === 'P1' ? 'P1 긴급 알림을 전송했습니다' : `${g} 장애 알림을 전송했습니다`,
      guide: `장애 ${no}로 등록하고 IT 담당자에게 메신저로 알렸습니다. 담당자가 장애 상세정보에서 확인·조치하며, 같은 증상 문의가 더 들어오면 이 장애에 누적됩니다.`,
    }
    case 'dup': return {
      tone: 'info', title: '이미 알림이 나간 장애에 누적했습니다',
      guide: `장애 ${no}는 ${out.value.notify.skipped_reason || '이미 알림이 발송된'} 상태라 다시 보내지 않고 제보 건수만 늘렸습니다. 등급이 더 올라가면 다시 알립니다.`,
    }
    case 'observe': return {
      tone: 'warn', title: `${g} · 관찰 대상으로 등록했습니다`,
      guide: `IT 담당자에게 바로 알리지 않고 장애 ${no}를 '관찰'로 등록했습니다. 센터관리자가 장애 상세정보에서 확인한 뒤 필요하면 IT 담당자에게 직접 알립니다. 같은 증상 제보가 늘면 등급을 다시 판정합니다.`,
    }
    case 'closed': return {
      tone: 'gray', title: `${g} · 알림 없이 종결했습니다`,
      guide: `장애 ${no}를 '미대상'으로 기록하고 알림은 보내지 않았습니다. 같은 증상 제보가 더 들어오면 다시 판정합니다.`,
    }
    case 'fp': return {
      tone: 'gray', title: '과거 오탐 사례와 같아 알림에서 제외했습니다',
      guide: `고객 귀책 등 과거 오탐으로 확인된 사례와 같은 유형이라 장애 ${no}를 '오탐'으로 기록했습니다. 알림은 보내지 않습니다.`,
    }
    case 'record': return { tone: 'gray', title: `${g} · 장애 정보만 등록했습니다`, guide: `장애 ${no}로 기록했고 알림은 보내지 않았습니다.` }
    case 'improve': return {
      tone: 'ok', title: '개선의견으로 기록했습니다',
      guide: '해결된 상담의 문구·안내·절차 개선 요청으로 분류해 개선의견 목록에 남겼습니다. 장애 알림과 누적에는 넣지 않습니다.',
    }
    case 'fail': return {
      tone: 'p1', title: '장애 판별 중 오류가 났습니다',
      guide: '에이전트 실행이 끝까지 진행되지 않았습니다. 아래 실행 과정의 실패 단계를 확인하고, 시스템관리자에게 재실행을 요청하세요.',
    }
    default: return {
      tone: 'ok', title: '장애가 아닌 일반 상담입니다',
      guide: '장애 신호가 확인되지 않아 알림 없이 상담이력만 저장했습니다.',
    }
  }
})

// 판단 근거: 업무 말로 정리한 핵심 + 판별 상세(심각도 판별 에이전트의 reasons 원문)
const facts = computed(() => {
  const list = []
  const d = det.value
  if (d.reason) list.push({ label: '장애 감지', text: `${d.reason}${d.source ? ` (${d.source} 판단)` : ''}` })
  if (d.error_type && kind.value !== 'normal') list.push({ label: '분류', text: `오류유형 ${d.error_type} · 접촉채널 ${d.channel || '-'}` })
  if (d.p1_decision?.reason) list.push({ label: '감지 판정', text: d.p1_decision.reason })
  const x = dd.value
  if (x) {
    if (x.merged) {
      let t = `최근 ${x.window_min}분 안에 같은 증상의 장애 ${incidentNo(x.incident_id)}가 있어 하나로 묶었습니다 (유사도 ${x.similarity}). `
        + `지금까지 제보 ${x.report_count}건 · 서로 다른 고객 ${x.customer_count}명입니다.`
      if (x.mass_signal) t += ' 같은 증상 고객이 기준 이상이라 대규모 장애 신호로 봤습니다.'
      list.push({ label: '같은 증상 제보', text: t, hit: x.report_count > 1 })
    } else if (x.resolved_by_counselor) {
      list.push({ label: '같은 증상 제보', text: '상담사가 통화 중 해결한 건이라 미해결 장애 누적에서 뺐습니다.' })
    } else if (x.recovered) {
      list.push({ label: '같은 증상 제보', text: `고객이 다시 시도해 정상 진행된 건(${x.recovered.slice(0, 3).join(', ')})이라 미해결 장애 누적에서 뺐습니다.` })
    } else {
      list.push({ label: '같은 증상 제보', text: `최근 ${x.window_min}분 안에 비슷한 미해결 장애가 없어 새 장애로 봤습니다 (이번이 첫 제보).` })
    }
  }
  const s = sev.value
  if (s) {
    const rules = (s.reasons || []).filter((r) => r.startsWith('[') && !r.startsWith('[BASE]'))
    const base = (s.reasons || []).find((r) => r.startsWith('[BASE]'))
    if (base) list.push({ label: '기본 등급', text: base.replace(/^\[BASE\]\s*/, '') })
    for (const r of rules) list.push({ label: '적용 규칙', text: r, hit: true })
    const llm = (s.reasons || []).find((r) => r.startsWith('LLM: '))
    if (llm) list.push({ label: 'AI 판단', text: llm.slice(5) })
    const g = (s.grade_guide || []).find((v) => v.code === s.severity)
    if (g?.notify_min_reports != null) {
      list.push({ label: '알림 조건', text: `${s.severity}는 제보 ${g.notify_min_reports}건 이상이면 알림 대상입니다. 이번 판정 시점 제보 ${s.report_count ?? '-'}건 → ${s.stage1?.notify ? '알림 대상' : '미대상'}.` })
    }
    const cases = (s.similar_cases || []).slice(0, 2)
    if (cases.length) {
      list.push({ label: '과거 유사 사례', text: cases.map((c) => `${incidentNo(c.incident_id)} [${c.status}] ${c.title} (유사도 ${c.similarity})`).join(' · ') })
    }
    if (s.stage2?.checked) {
      list.push({ label: '오탐 대조', text: s.false_positive ? `과거 오탐 사례 ${incidentNo(s.stage2.matched)}와 일치해 알림에서 뺐습니다.` : '과거 오탐 사례와 일치하지 않아 알림 대상을 유지했습니다.' })
    }
  }
  if (kind.value === 'sent' && out.value.notify?.recipients?.length) {
    list.push({ label: '알림 받은 사람', text: out.value.notify.recipients.join(', ') })
  }
  if (kind.value === 'fail') {
    const f = (props.run.steps || []).find((st) => st.status === 'FAILED')
    if (f) list.push({ label: '실패 단계', text: `${f.agent_name}: ${f.message}` })
  }
  return list
})

const guideRows = computed(() => sev.value?.grade_guide || [])
function guideText(g) {
  if (g.notify_min_reports == null) return g.observe ? '알림 없음 · 관찰 등록 (센터관리자 확인)' : '알림 없음 · 미대상 종결'
  const n = g.notify_min_reports <= 1 ? '첫 제보부터 바로 IT 담당자 알림' : `제보 ${g.notify_min_reports}건부터 IT 담당자 알림`
  return n + (g.observe ? ', 그 전에는 관찰 등록' : '')
}

const onKey = (e) => { if (e.key === 'Escape') emit('close') }
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="run-result-title">
      <div class="m-head">
        <div class="m-title">
          <SeverityBadge v-if="grade && !['normal', 'improve', 'fail'].includes(kind)" :value="grade" />
          <h3 id="run-result-title">장애 판별 결과</h3>
        </div>
        <button class="x" type="button" title="닫기" @click="emit('close')">×</button>
      </div>

      <div class="m-body">
        <div class="result" :class="'tone-' + head.tone">
          <strong>{{ kind === 'sent' && grade === 'P1' ? '🚨 ' : '' }}{{ head.title }}</strong>
          <p>{{ head.guide }}</p>
        </div>

        <h4>왜 이렇게 판단했나요?</h4>
        <ul class="facts">
          <li v-for="(f, i) in facts" :key="i" :class="{ hit: f.hit }">
            <span class="lbl">{{ f.label }}</span>
            <span class="txt">{{ f.text }}</span>
          </li>
        </ul>

        <template v-if="guideRows.length">
          <h4>등급별 처리 기준 <span class="sub">현재 판별기준 {{ sev.criteria_version }}</span></h4>
          <table class="guide">
            <tbody>
              <tr v-for="g in guideRows" :key="g.code" :class="{ on: g.code === grade }">
                <td class="nowrap"><SeverityBadge :value="g.code" short /> {{ g.name }}</td>
                <td>{{ guideText(g) }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <div v-if="sev?.reasons?.length" class="all">
          <button class="link" type="button" @click="showAll = !showAll">{{ showAll ? '판별 상세 근거 접기 ▴' : '판별 상세 근거 전체 보기 ▾' }}</button>
          <ol v-if="showAll"><li v-for="(r, i) in sev.reasons" :key="i">{{ r }}</li></ol>
        </div>
      </div>

      <div class="m-foot">
        <button v-if="sent?.incident_id" class="btn btn-sm" type="button" @click="emit('open-incident', sent.incident_id)">
          장애 {{ incidentNo(sent.incident_id) }} 상세 보기 →
        </button>
        <button class="btn btn-sm btn-primary" type="button" @click="emit('close')">확인</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overlay { position: fixed; inset: 0; background: rgba(25, 31, 40, .45); display: grid; place-items: center; z-index: 100; padding: 16px; }
.modal { background: var(--surface); border-radius: var(--radius-card); width: min(640px, 100%); max-height: calc(100vh - 32px); display: flex; flex-direction: column; box-shadow: 0 12px 40px rgba(25, 31, 40, .2); }
.m-head { display: flex; justify-content: space-between; align-items: center; padding: 18px 22px 10px; }
.m-title { display: flex; align-items: center; gap: 8px; }
.m-title h3 { font-size: 17px; }
.x { font: inherit; font-size: 22px; line-height: 1; border: 0; background: none; color: var(--text-3); cursor: pointer; padding: 4px 8px; border-radius: var(--radius-badge); }
.x:hover { background: var(--line); color: var(--text); }
.m-body { padding: 4px 22px 8px; overflow-y: auto; }
.result { border-radius: var(--radius); padding: 14px 16px; margin-bottom: 18px; }
.result strong { display: block; font-size: 15px; margin-bottom: 4px; }
.result p { margin: 0; font-size: 13px; line-height: 1.6; }
.tone-p1 { background: var(--p1-soft); color: var(--p1); }
.tone-p1 p { color: var(--text); }
.tone-warn { background: var(--warn-soft); color: var(--warn); }
.tone-warn p { color: var(--text); }
.tone-info { background: var(--accent-soft); color: var(--accent); }
.tone-info p { color: var(--text); }
.tone-ok { background: var(--ok-soft); color: var(--ok); }
.tone-ok p { color: var(--text); }
.tone-gray { background: var(--surface-2); color: var(--text); }
h4 { font-size: 13.5px; margin: 0 0 8px; }
h4 .sub { font-weight: 500; font-size: 12px; color: var(--text-3); margin-left: 4px; }
.facts { list-style: none; margin: 0 0 18px; padding: 0; display: grid; gap: 6px; }
.facts li { display: grid; grid-template-columns: 96px 1fr; gap: 10px; font-size: 13px; line-height: 1.55; padding: 8px 12px; background: var(--surface-2); border-radius: var(--radius-badge); }
.facts li.hit { box-shadow: inset 3px 0 0 var(--accent); }
.facts .lbl { font-weight: 700; color: var(--text-2); font-size: 12.5px; }
.facts .txt { color: var(--text); word-break: keep-all; overflow-wrap: anywhere; }
.guide { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-bottom: 14px; }
.guide td { padding: 7px 10px; border-bottom: 1px solid var(--line); }
.guide tr.on td { background: var(--accent-soft); font-weight: 600; }
.nowrap { white-space: nowrap; }
.all { margin-bottom: 8px; }
.link { font: inherit; font-size: 12.5px; border: 0; background: none; color: var(--accent); cursor: pointer; padding: 0; }
.all ol { margin: 8px 0 0; padding-left: 20px; font-size: 12px; color: var(--text-2); line-height: 1.6; }
.m-foot { display: flex; justify-content: flex-end; gap: 6px; padding: 12px 22px 18px; border-top: 1px solid var(--line); }
@media (max-width: 560px) { .facts li { grid-template-columns: 1fr; gap: 2px; } }
</style>
