<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { incidentNo } from '../../utils/format'
import mascot from '../../assets/mascot.png'

/* 에이전트 단계 도식 말풍선 (상담이력등록 SCR-03)
   실행 과정 그래프에서 단계를 누르면 그래프 바로 아래에 말풍선으로 열리고,
   그 단계가 하는 일을 '아이콘 카드 → 카드 → 결론' 도식으로 한눈에 보여줍니다 (시연용으로 짧게).
   열릴 때마다 첫 카드부터 결과까지 차례로 켜지고, 콜록이가 처리 중인 카드 위로 따라가며
   상태에 맞는 모습(조회·추론·전달 → 근거 발견·확인 완료)과 분석 코멘트를 보여줍니다.
   x: 말풍선 꼬리 위치 (그래프 너비 대비 0~1) */

const props = defineProps({ step: { type: Object, required: true }, x: { type: Number, default: 0.5 } })
const emit = defineEmits(['close', 'done'])   // done: 결과 카드까지 다 켜짐 (자동 이어 재생용)

const ROLE = {
  detect: '고객 말과 상담 기록을 읽고 장애인지 판단',
  dedup: '같은 증상의 최근 장애와 묶어 제보 수를 셈',
  severity: '판별기준 · 과거 사례 · AI로 등급과 알림 여부 결정',
  notify: '담당자를 찾아 메신저로 장애를 알림',
  record: '알림 없이 장애 정보만 남김',
  improve: '장애가 아닌 개선 요청으로 기록',
}

const o = computed(() => props.step.output || {})
const node = computed(() => o.value.node)
const inc = (v) => (v ? '장애' : '정상')
const quote = (a) => (a || []).slice(0, 2).map((w) => `'${w}'`).join(', ')
const cut = (t, n = 60) => (t && t.length > n ? t.slice(0, n) + '…' : t || '')

/* 도식 카드: { icon, title, value, tone: hit(눈여겨볼 결과) | miss(해당 없음) | '',
               act: 처리 중 콜록이 모습(scan 조회 | think 추론 | send 전달), say: 콜록이 분석 코멘트 } */
const cards = computed(() => {
  const x = o.value
  switch (node.value) {
    case 'detect': {
      const stt = x.stt_analysis || {}
      const cons = x.consult_analysis || {}
      const c = [
        { icon: '🎙', title: 'STT 원문', value: inc(stt.is_incident), tone: stt.is_incident ? 'hit' : 'miss', act: 'scan',
          say: stt.is_incident ? (stt.signals?.length ? `STT 원문에서 장애 신호어 ${quote(stt.signals)}를 탐지했습니다.` : 'STT 원문에서 장애 정황을 확인했습니다.')
            : 'STT 원문에서는 장애 신호어를 찾지 못했습니다.' },
        { icon: '📝', title: '상담이력', value: inc(cons.is_incident), tone: cons.is_incident ? 'hit' : 'miss', act: 'scan',
          say: cons.is_incident ? '상담유형과 상담요약이 장애 상담 패턴과 일치합니다.' : '상담이력에서는 장애 정황이 확인되지 않습니다.' },
        { icon: '🧠', title: x.source === 'LLM' ? '종합 (AI)' : '종합 (규칙)', value: x.category === '장애' ? x.error_type : x.category, tone: x.is_incident ? 'hit' : '', act: 'think',
          say: x.category === '장애' ? `두 근거를 종합해 '${x.error_type}' 유형으로 분류했습니다.` + (x.confidence != null ? ` 판정 신뢰도 ${x.confidence}.` : '')
            : x.category === '개선의견' ? '해결된 건에 대한 개선 요청으로 판단했습니다.' : '장애 정황이 부족해 일반 상담으로 판단했습니다.' },
      ]
      if (x.p1_decision) {
        const t = x.similar_types?.[0]?.구분
        c.push({ icon: '🔎', title: '유형 상담 비교', value: t || '비교 완료', tone: 'hit', act: 'think',
          say: cut((t ? `유사 유형 상담 '${t}'과 비교했습니다. ` : '') + (x.p1_decision.reason || ''), 70) })
      }
      return c
    }
    case 'dedup': {
      const skip = x.resolved_by_counselor || x.recovered
      const cand = x.candidates || []
      const c = [{ icon: '🚦', title: '누적 제외 확인', value: x.resolved_by_counselor ? '상담사 해결' : x.recovered ? '정상 진행' : '해당 없음', tone: skip ? 'hit' : 'miss', act: 'scan',
        say: x.resolved_by_counselor ? '상담사가 통화 중 해결한 건이라 미해결 누적 집계에서 제외합니다.'
          : x.recovered ? '재시도 후 정상 진행된 건이라 미해결 누적 집계에서 제외합니다.'
          : '통화 중 해결이나 재시도 성공 이력이 없어 누적 집계 대상에 포함합니다.' }]
      if (!skip) {
        c.push({ icon: '🔍', title: `최근 ${x.window_min}분 비교`, value: cand.length ? `${cand.length}건 · 최고 ${cand[0].score}` : '후보 없음', tone: cand.length ? 'hit' : 'miss', act: 'scan',
          say: cand.length ? `최근 ${x.window_min}분 내 동일 유형 미해결 장애 ${cand.length}건과 비교했습니다. 최고 유사도 ${cand[0].score}.`
            : `최근 ${x.window_min}분 내 비교할 동일 유형 미해결 장애가 없습니다.` })
      }
      c.push({ icon: '🔗', title: '통합 결정', value: x.merged ? `${incidentNo(x.incident_id)} 통합` : '신규 장애', tone: x.merged ? 'hit' : '', act: 'think',
        say: x.merged ? `유사도 ${x.similarity}로 통합 기준을 넘어 ${incidentNo(x.incident_id)}에 동일 제보로 병합합니다.` : '통합 기준을 넘는 장애가 없어 신규 장애로 봅니다.' })
      if (x.merged) {
        c.push({ icon: '📢', title: `제보 ${x.report_count}건 · 고객 ${x.customer_count}명`, value: x.mass_signal ? '대규모 신호' : '대규모 아님', tone: x.mass_signal ? 'hit' : 'miss', act: 'scan',
          say: x.mass_signal ? `서로 다른 고객 ${x.customer_count}명이 같은 증상을 제보해 대규모 장애 신호 기준에 도달했습니다.`
            : `누적 제보 ${x.report_count}건 · 고객 ${x.customer_count}명으로 대규모 신호 기준에는 미달합니다.` })
      }
      return c
    }
    case 'severity': {
      const reasons = x.reasons || []
      const base = reasons.find((r) => r.startsWith('[BASE]')) || ''
      const rules = reasons.filter((r) => r.startsWith('[') && !r.startsWith('[BASE]'))
      const llm = reasons.find((r) => r.startsWith('LLM: '))
      const s1 = x.stage1 || {}
      const s2 = x.stage2 || {}
      const top = (x.similar_cases || [])[0]
      const g = (x.grade_guide || []).find((v) => v.code === s1.severity)
      const baseGrade = base.match(/P\d/)?.[0]
      return [
        { icon: '📏', title: '기본 등급', value: baseGrade || '판별기준', tone: '', act: 'scan',
          say: baseGrade ? `판별기준상 이 오류유형·접촉채널의 기본 등급은 ${baseGrade}입니다.` : '판별기준의 기본 등급을 적용했습니다.' },
        { icon: '⚙', title: '조정 규칙', value: rules.length ? `${rules.length}개 적용` : '없음', tone: rules.length ? 'hit' : 'miss', act: 'scan',
          say: rules.length ? cut(`등급 조정 규칙 ${rules.length}개가 적용됩니다. ${rules[0]}`, 70) : '적용되는 등급 조정 규칙이 없습니다.' },
        { icon: '📚', title: '과거 사례 (RAG)', value: `${x.rag?.count || 0}건`, tone: x.rag?.count ? 'hit' : 'miss', act: 'scan',
          say: top ? cut(`유사 과거 사례 ${x.rag.count}건을 검색했습니다. ${incidentNo(top.incident_id)}(${top.title})이 가장 근접합니다.`, 80) : '유사한 과거 사례가 없습니다.' },
        { icon: '🧠', title: 'AI 판정', value: llm ? '사용' : '규칙만', tone: llm ? 'hit' : 'miss', act: 'think',
          say: llm ? cut(`AI 판단: ${llm.slice(5)}`, 80) : 'AI 판정 없이 판별기준 규칙으로 판정했습니다.' },
        { icon: '✅', title: '1차 판별', value: `${s1.severity || '-'} · ${s1.notify ? '알림' : '미대상'}`, tone: s1.notify ? 'hit' : '', act: 'think',
          say: s1.notify ? `${s1.severity} 등급은 ${g?.notify_min_reports > 1 ? `제보 ${g.notify_min_reports}건부터` : '첫 제보부터'} 알림 대상입니다. 1차 판별 결과 알림이 필요합니다.`
            : `${s1.severity || '이'} 등급은 현재 제보 수로는 알림 대상이 아닙니다.` },
        { icon: '🛡', title: '2차 오탐 대조', value: !s2.checked ? '생략' : x.false_positive ? '오탐' : '통과', tone: x.false_positive ? 'hit' : s2.checked ? '' : 'miss', act: 'scan',
          say: !s2.checked ? '1차에서 알림 미대상이라 오탐 대조를 생략합니다.'
            : x.false_positive ? `과거 오탐 사례 ${incidentNo(s2.matched)}와 일치해 알림에서 제외합니다.`
            : '과거 오탐 사례와 일치하지 않습니다. 알림 대상을 유지합니다.' },
      ]
    }
    case 'notify': {
      const c = [{ icon: '🗂', title: '장애 등록', value: `${incidentNo(x.incident_id)} · ${x.severity}`, tone: '', act: 'scan',
        say: `장애 ${incidentNo(x.incident_id)}를 ${x.severity} 등급으로 등록하고 제보 이력을 연결했습니다.` }]
      if (x.skipped_reason) {
        c.push({ icon: '🔁', title: '중복 발송 확인', value: '이미 알림 · 생략', tone: 'hit', act: 'scan',
          say: `${x.skipped_reason} — 같은 장애라 중복 발송을 생략하고 제보 건수만 늘립니다.` })
        return c
      }
      const p = x.primary || []
      const s = x.secondary || []
      return [...c,
        { icon: '👥', title: '수신자 식별', value: `1차 ${p.length}명 · 2차 ${s.length}명`, tone: 'hit', act: 'scan',
          say: cut(`1차 ${p.join(', ') || '없음'}${s.length ? `, 2차 ${s.join(', ')}` : ''}를 수신자로 지정했습니다.`, 80) },
        { icon: '✉', title: '메신저 전송', value: x.sent ? `${(x.recipients || []).length}명 발송` : '미발송', tone: x.sent ? 'hit' : 'miss', act: 'send',
          say: x.sent ? `장애 상세 링크를 포함해 담당자 ${(x.recipients || []).length}명에게 알림을 발송했습니다.` : '메신저를 발송하지 않았습니다.' }]
    }
    case 'record': {
      const why = (props.step.message || '').match(/메신저 미발송 \((.+)\)$/)?.[1]
      return [
        { icon: '🗂', title: '장애 등록', value: `${incidentNo(x.incident_id)} · ${x.incident_status}`, tone: '', act: 'scan',
          say: `장애 ${incidentNo(x.incident_id)}를 '${x.incident_status}' 상태로 등록했습니다.` },
        { icon: '🔕', title: '메신저', value: '미발송', tone: 'miss', act: 'think',
          say: why ? `${why} — 메신저는 발송하지 않습니다.` : '알림 대상이 아니어서 메신저는 발송하지 않습니다.' },
      ]
    }
    case 'improve':
      return [
        { icon: '💡', title: '개선의견 등록', value: `#${x.improvement_id}`, tone: 'hit', act: 'scan',
          say: `해결된 건의 개선 요청을 개선의견 #${x.improvement_id}로 기록했습니다.` },
        { icon: '🔗', title: '관련 장애', value: x.related_incident_id ? incidentNo(x.related_incident_id) : '없음', tone: x.related_incident_id ? 'hit' : 'miss', act: 'scan',
          say: x.related_incident_id ? `유사한 장애 ${incidentNo(x.related_incident_id)}와 연결했습니다.` : '연결할 유사 장애가 없습니다.' },
      ]
    default: return []
  }
})

// 결론: 다음으로 어디로 가는지 (+ 콜록이 마무리 코멘트)
const end = computed(() => {
  const x = o.value
  switch (node.value) {
    case 'detect': return x.category === '개선의견' ? { v: '개선의견 등록', say: '개선의견으로 분류했습니다. 기록 단계로 넘깁니다.' }
      : x.is_incident ? { v: '중복제보 통합', say: '장애로 판정했습니다. 중복제보 통합 단계로 이관합니다.' }
      : { v: '종료 (일반 상담)', say: '장애가 아니므로 분석을 종료합니다.' }
    case 'dedup': return { v: '심각도 판별', say: '제보 집계를 마쳤습니다. 심각도 판별 단계로 넘깁니다.' }
    case 'severity': return { v: `${x.severity} ${x.notify ? '→ 메신저 전송' : '→ 장애이력 등록'}`,
      say: `최종 등급 ${x.severity}(${x.severity_label || '-'})로 확정했습니다. ` + (x.notify ? '메신저 전송 단계로 이관합니다.' : '알림 없이 장애이력으로 등록합니다.') }
    case 'notify': return { v: '종료', say: x.sent ? '알림 절차를 완료했습니다. 담당자 확인을 기다립니다.' : '제보 누적을 마쳤습니다.' }
    case 'record': return { v: '종료', say: '장애이력 등록을 마쳤습니다.' }
    case 'improve': return { v: '종료', say: '개선의견 기록을 마쳤습니다. 장애 알림 대상은 아닙니다.' }
    default: return { v: '종료', say: '' }
  }
})

/* 차례로 켜기: shown 보다 앞 카드는 완료, shown 번째는 실행 중, 뒤는 대기 (마지막 = 결과 카드)
   카드마다 콜록이가 이전 카드에서 쏙 사라졌다가 이번 카드 위에 상황에 맞는 소품을 들고 뿅 나타남
   → 처리 중 모습 + 코멘트 → 결과 반응 */
const VANISH_MS = 175        // 이전 카드에서 사라짐
const APPEAR_MS = 255        // 이번 카드에서 나타남
const ACT_MS = 600           // 처리 중 모습 최소 시간 (코멘트가 길면 다 써질 때까지)
const RESULT_MS = 500        // 결과 반응 유지
const END_MS = 600           // 결과 카드에서 멈춤
const TYPE_MS = 15           // 코멘트 글자 간격
const MARK = { scan: '🔍', think: '···', send: '📨', found: '!', clear: '✓', cheer: '★' }
const WHO = { scan: '조회 중', think: '추론 중', send: '전달 중', found: '근거 발견', clear: '확인 완료', cheer: '단계 완료' }

const shown = ref(0)
const playing = ref(false)
const mood = ref('')
const vis = ref('')                                     // show 나타남 · hide 사라짐 · '' 숨김
const popKey = ref(0)                                   // 나타날 때마다 다시 그려 '뿅' 효과를 처음부터
const prop = ref('')                                    // 손에 든 소품 (카드 아이콘, 전달이면 편지)
const cloud = ref('')                                   // 추론할 때 생각 구름 속 아이콘
const sayText = ref('')
const sayKey = ref(0)                                   // 문장이 바뀔 때만 떠오르는 효과
const pos = ref({ left: 0, sayLeft: null, sayRight: null, flip: false })
const lane = ref(null)
const cardEls = []
let token = 0

const wait = (ms, my) => new Promise((r) => setTimeout(() => r(my === token), ms))
async function type(text, my) {
  sayText.value = ''
  sayKey.value++
  for (const ch of text || '') {
    if (my !== token) return
    sayText.value += ch
    await wait(TYPE_MS, my)
  }
}
function placeOver(i) {                                 // 카드 가운데 위로 이동, 코멘트는 콜록이 옆 (오른쪽이면 왼쪽)
  const el = cardEls[i]
  if (!el || !lane.value) return
  const box = lane.value.getBoundingClientRect()
  const r = el.getBoundingClientRect()
  const cx = r.left - box.left + r.width / 2
  const flip = cx > box.width * 0.55
  pos.value = { left: cx - 34, sayLeft: flip ? null : cx + 40, sayRight: flip ? box.width - cx + 40 : null, flip }
}

async function play() {
  const my = ++token
  playing.value = true
  shown.value = 0
  mood.value = ''
  vis.value = ''
  sayText.value = ''
  await nextTick()
  const total = cards.value.length
  for (let i = 0; i <= total; i++) {
    if (my !== token) return
    const c = i < total ? cards.value[i] : null
    if (vis.value === 'show') {                         // 이전 카드에서 쏙 사라지고
      vis.value = 'hide'
      if (!(await wait(VANISH_MS, my))) return
    }
    sayText.value = ''
    placeOver(i)                                        // 이번 카드 위에 상황에 맞는 모습으로 뿅
    prop.value = c ? (c.act === 'send' ? '✉' : c.icon) : ''
    cloud.value = c ? c.icon : ''
    mood.value = c ? c.act : 'cheer'
    vis.value = 'show'
    popKey.value++
    if (!(await wait(APPEAR_MS, my))) return
    if (!c) {                                           // 결과 카드
      shown.value = total + 1
      await type(end.value.say, my)
      if (!(await wait(END_MS, my))) return
      break
    }
    mood.value = c.act
    await Promise.all([type(c.say, my), wait(ACT_MS, my)])
    if (my !== token) return
    mood.value = c.tone === 'hit' ? 'found' : 'clear'
    shown.value = i + 1
    if (!(await wait(RESULT_MS, my))) return
  }
  playing.value = false
  emit('done')
}
const state = (i) => (i < shown.value ? 'on' : i === shown.value ? 'running' : 'idle')
watch(() => `${props.step.seq}:${cards.value.length}`, play, { immediate: true })   // 문자열로 비교 (폴링마다 새 배열이 와도 재시작하지 않게)

// 꼬리가 화면 밖으로 나가지 않게
const tail = computed(() => `${Math.min(96, Math.max(4, props.x * 100))}%`)
const onKey = (e) => { if (e.key === 'Escape') emit('close') }
const onResize = () => placeOver(Math.min(shown.value, cards.value.length))
onMounted(() => { document.addEventListener('keydown', onKey); window.addEventListener('resize', onResize) })
onBeforeUnmount(() => { document.removeEventListener('keydown', onKey); window.removeEventListener('resize', onResize); token++ })
</script>

<template>
  <div class="bubble" :style="{ '--tail': tail }" role="dialog" aria-label="에이전트 단계 도식">
    <div class="b-head">
      <strong>{{ step.agent_name }}</strong>
      <StatusBadge v-if="step.status" :value="step.status" />
      <span v-if="step.elapsed_ms != null && step.status !== 'RUNNING'" class="ms">{{ (step.elapsed_ms / 1000).toFixed(1) }}s</span>
      <span class="role">{{ ROLE[node] }}</span>
      <button class="replay" type="button" :disabled="playing" title="처음부터 다시 보기" @click="play">↻ 다시 보기</button>
      <button class="x" type="button" title="닫기" @click="emit('close')">×</button>
    </div>
    <div v-if="cards.length" ref="lane" class="lane">
      <div :key="'a' + popKey" class="agent" :class="vis" :style="{ left: pos.left + 'px' }">
        <span class="puff" />
        <div class="fig" :class="mood">
          <img :src="mascot" alt="콜록이" width="72" height="72">
          <span class="prop">{{ prop }}</span>
          <span class="cloud">{{ cloud }}</span>
          <span class="spark s1">✨</span><span class="spark s2">✨</span>
          <span v-if="MARK[mood]" :key="mood" class="mark">{{ MARK[mood] }}</span>
        </div>
      </div>
      <div v-if="vis" :key="'s' + popKey" class="say" :class="[mood, vis, { flip: pos.flip }]"
           :style="{ left: pos.sayLeft != null ? pos.sayLeft + 'px' : 'auto', right: pos.sayRight != null ? pos.sayRight + 'px' : 'auto' }">
        <span class="who">콜록이{{ WHO[mood] ? ' · ' + WHO[mood] : '' }}</span>
        <span :key="sayKey" class="text">{{ sayText }}</span>
      </div>
      <div class="flow">
        <template v-for="(c, i) in cards" :key="i">
          <div :ref="(el) => (cardEls[i] = el)" class="card" :class="['s-' + state(i), state(i) === 'on' ? c.tone : '']">
            <span class="icon">{{ c.icon }}</span>
            <span class="title">{{ c.title }}</span>
            <span class="value">{{ c.value }}</span>
          </div>
          <span class="arrow" :class="{ on: i < shown }">→</span>
        </template>
        <div :ref="(el) => (cardEls[cards.length] = el)" class="card end" :class="'s-' + state(cards.length)">
          <span class="icon">🏁</span><span class="title">결과</span><span class="value">{{ end.v }}</span>
        </div>
      </div>
    </div>
    <p v-else class="muted wait">{{ step.status === 'RUNNING' ? '실행 중입니다…' : '상세 기록이 없습니다.' }}</p>
  </div>
</template>

<style scoped>
.bubble { position: relative; margin: 14px auto 0; max-width: 980px; background: var(--surface); border: 1.5px solid var(--accent); border-radius: var(--radius-card); padding: 12px 14px 14px; box-shadow: 0 6px 20px rgba(25, 31, 40, .12); animation: pop .16s ease-out; }
.bubble::before, .bubble::after { content: ''; position: absolute; left: var(--tail); transform: translateX(-50%); border: 9px solid transparent; border-top: 0; }
.bubble::before { top: -10px; border-bottom: 10px solid var(--accent); }
.bubble::after { top: -8px; border-bottom: 10px solid var(--surface); }
.b-head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 13.5px; }
.ms { font-size: 11px; color: var(--text-3); font-family: var(--mono); }
.role { font-size: 12.5px; color: var(--text-3); }
.replay { margin-left: auto; font: inherit; font-size: 12px; font-weight: 600; border: 0; background: none; color: var(--accent); cursor: pointer; padding: 2px 6px; border-radius: var(--radius-badge); }
.replay:disabled { color: var(--text-3); cursor: default; }
.replay:not(:disabled):hover { background: var(--accent-soft); }
.x { font: inherit; font-size: 20px; line-height: 1; border: 0; background: none; color: var(--text-3); cursor: pointer; padding: 2px 8px; border-radius: var(--radius-badge); }
.x:hover { background: var(--line); color: var(--text); }

/* 카드 위 무대: 콜록이가 처리 중인 카드 위로 이동하고, 옆에 분석 코멘트 */
.lane { position: relative; padding-top: 100px; }
.agent { position: absolute; top: 22px; width: 76px; height: 76px; z-index: 2; pointer-events: none; opacity: 0; }
.fig { position: relative; width: 76px; height: 76px; }
.fig img { width: 72px; height: 72px; display: block; margin: 4px 0 0 2px; transform-origin: 50% 100%; }
/* 나타남 · 사라짐: 카드 위에서 '뿅' 나왔다가 다음 카드로 갈 때 '쏙' 사라짐 */
.agent.show, .agent.hide { opacity: 1; }
.agent.show .fig { animation: popIn .38s cubic-bezier(.3, 1.6, .5, 1); }
.agent.hide .fig { animation: popOut .2s ease-in forwards; }
@keyframes popIn  { 0% { transform: scale(0) translateY(14px); opacity: 0; } 60% { opacity: 1; } 100% { transform: scale(1); } }
@keyframes popOut { to { transform: scale(0) translateY(10px); opacity: 0; } }
.puff { position: absolute; left: 50%; top: 58%; width: 64px; height: 64px; margin: -32px 0 0 -32px; border-radius: 50%; opacity: 0; }
.agent.show .puff { animation: puff .5s ease-out; }
@keyframes puff { 0% { opacity: .9; transform: scale(.3); box-shadow: 0 0 0 6px rgba(240, 197, 90, .55), 0 0 0 14px rgba(27, 100, 218, .18); } 100% { opacity: 0; transform: scale(1.5); box-shadow: 0 0 0 1px rgba(240, 197, 90, 0), 0 0 0 2px rgba(27, 100, 218, 0); } }
.mark { position: absolute; right: -6px; top: -4px; min-width: 24px; height: 24px; padding: 0 5px; border-radius: 12px; display: grid; place-items: center; font-size: 12px; font-weight: 900; color: #fff; z-index: 3; animation: markIn .2s cubic-bezier(.3, 1.6, .5, 1); }
@keyframes markIn { from { transform: scale(0); } }
.scan .mark, .send .mark { background: var(--accent); }
.think .mark { background: #7a5af5; letter-spacing: -1px; }
.found .mark { background: var(--p1); }
.clear .mark { background: var(--ok); }
.cheer .mark { background: #f0c55a; color: #6b4a00; }
/* 상황별 소품: 조회·발견은 카드 아이콘을 들고, 추론은 생각 구름, 전달은 편지를 날림 */
.prop { position: absolute; right: -10px; bottom: 6px; font-size: 22px; line-height: 1; filter: drop-shadow(0 2px 3px rgba(25, 31, 40, .2)); opacity: 0; }
.cloud { position: absolute; left: -40px; top: -16px; width: 46px; height: 38px; border-radius: 50%; background: var(--surface); border: 1.5px solid #d9cffd; display: grid; place-items: center; font-size: 20px; opacity: 0; transform: scale(.4); transition: opacity .25s, transform .25s; box-shadow: 0 3px 8px rgba(122, 90, 245, .15); }
.cloud::before, .cloud::after { content: ''; position: absolute; border-radius: 50%; background: var(--surface); border: 1.5px solid #d9cffd; }
.cloud::before { width: 10px; height: 10px; right: -4px; bottom: -6px; }
.cloud::after { width: 6px; height: 6px; right: -10px; bottom: -12px; }
.spark { position: absolute; font-size: 14px; opacity: 0; }
.spark.s1 { left: -8px; top: 6px; }
.spark.s2 { right: -14px; top: -2px; }
/* 조회: 자료(카드 아이콘)를 들고 돋보기로 훑음 */
.scan img { animation: scan .7s ease-in-out infinite; }
.scan .prop { opacity: 1; animation: hold .7s ease-in-out infinite; }
@keyframes scan { 0%, 100% { transform: rotate(-7deg) translateX(-2px); } 50% { transform: rotate(7deg) translateX(2px); } }
@keyframes hold { 50% { transform: translateY(-3px) rotate(-6deg); } }
/* 추론: 생각 구름 속 카드 아이콘, 고개 갸웃 */
.think img { animation: think 1.4s ease-in-out infinite; }
.think .cloud { opacity: 1; transform: scale(1); animation: float 1.4s ease-in-out infinite; }
@keyframes think { 0%, 100% { transform: rotate(0); } 50% { transform: rotate(-10deg) translateY(-2px); } }
@keyframes float { 50% { transform: translateY(-4px); } }
/* 전달: 편지를 오른쪽 위로 날려 보냄 */
.send img { animation: send .5s ease-in-out infinite; }
.send .prop { opacity: 1; bottom: auto; top: 22px; animation: fly .9s ease-in infinite; }
@keyframes send { 50% { transform: translate(4px, -4px) rotate(6deg); } }
@keyframes fly { 0% { transform: translate(0, 0) scale(.8); opacity: 0; } 20% { opacity: 1; } 100% { transform: translate(46px, -26px) rotate(18deg) scale(1.1); opacity: 0; } }
/* 근거 발견: 펄쩍 + 소품을 번쩍 들어 올림 + 반짝 */
.found img { animation: found .45s ease-out; }
.found .prop { opacity: 1; bottom: auto; top: -8px; right: -14px; transform: scale(1.25) rotate(-10deg); }
.found .spark { animation: spark .6s ease-out; }
@keyframes found { 40% { transform: translateY(-16px) scale(1.06); } }
@keyframes spark { 0% { opacity: 1; transform: scale(.4); } 100% { opacity: 0; transform: scale(1.4) translateY(-8px); } }
/* 확인 완료: 끄덕 + 소품을 내려놓음 */
.clear img { animation: clear .5s ease-out; }
.clear .prop { opacity: .55; bottom: 0; right: -8px; transform: scale(.85); }
@keyframes clear { 30% { transform: rotate(6deg); } 60% { transform: rotate(-4deg); } }
/* 단계 완료: 만세 점프 + 축하 반짝이 */
.cheer img { animation: cheer .5s ease-out 2; }
.cheer .spark { animation: spark .8s ease-out 2; }
@keyframes cheer { 40% { transform: translateY(-20px) scale(1.08); } }

/* 부드러운 코멘트 말풍선: 상태 색이 옅게 비치는 배경 + 콜록이 쪽 둥근 꼬리 */
.say { --tone: var(--accent); --tint: #f3f8ff; position: absolute; top: 8px; max-width: min(430px, 60%); background: linear-gradient(180deg, var(--surface), var(--tint)); border: 1px solid rgba(27, 100, 218, .12); border-radius: 18px; padding: 9px 15px 10px; font-size: 13px; line-height: 1.6; color: var(--text-2); box-shadow: 0 6px 18px rgba(25, 31, 40, .07), 0 1px 3px rgba(25, 31, 40, .05); transition: opacity .2s, transform .2s, background .4s; z-index: 3; word-break: keep-all; }
.say.show { animation: sayIn .3s cubic-bezier(.3, 1.4, .5, 1); }
.say.hide { opacity: 0; transform: scale(.94) translateY(4px); }
@keyframes sayIn { from { opacity: 0; transform: scale(.9) translateY(6px); } }
.say::before { content: ''; position: absolute; left: -6px; top: 22px; width: 13px; height: 13px; background: var(--tint); border-left: 1px solid rgba(27, 100, 218, .12); border-bottom: 1px solid rgba(27, 100, 218, .12); border-bottom-left-radius: 4px; transform: rotate(45deg); transition: background .4s; }
.say.flip::before { left: auto; right: -6px; transform: rotate(-135deg); }
.say .who { display: flex; align-items: center; gap: 6px; font-size: 11px; font-weight: 700; color: var(--tone); margin-bottom: 2px; transition: color .3s; }
.say .who::before { content: ''; width: 7px; height: 7px; border-radius: 50%; background: var(--tone); box-shadow: 0 0 0 3px color-mix(in srgb, var(--tone) 18%, transparent); }
.say .text { display: block; min-height: 1.6em; animation: fadeUp .3s ease-out; }
@keyframes fadeUp { from { opacity: 0; transform: translateY(3px); } }
.say.found { --tone: var(--p1); --tint: #fff5f6; }
.say.clear { --tone: var(--ok); --tint: #f2fbf6; }
.say.think { --tone: #7a5af5; --tint: #f7f4ff; }
.say.cheer { --tone: #b07d00; --tint: #fffaec; }

.flow { display: flex; align-items: stretch; gap: 6px; }
.card { flex: 1 1 0; min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 10px 4px; border-radius: var(--radius); background: var(--surface-2); border: 1.5px solid var(--line); text-align: center; }
.card .icon { font-size: 20px; line-height: 1.2; }
.card .title { font-size: 11.5px; color: var(--text-3); font-weight: 600; }
.card .value { font-size: 12.5px; font-weight: 700; color: var(--text); word-break: keep-all; }
.card.hit { background: var(--accent-soft); border-color: var(--accent); }
.card.hit .value { color: var(--accent); }
.card.miss { border-style: dashed; }
.card.miss .value { color: var(--text-3); }
.card.end { background: var(--ok-soft); border-color: var(--ok); }
.card.end .value { color: var(--ok); }
.arrow { align-self: center; color: var(--line-strong); font-weight: 700; transition: color .25s; flex-shrink: 0; }
.arrow.on { color: var(--accent); }
/* 차례로 켜기: 대기(흐리게) → 실행 중(깜빡임) → 완료(결과 색) */
.card { transition: background .25s, border-color .25s, opacity .25s, transform .25s; }
.card.s-idle { opacity: .35; border-style: dashed; background: var(--surface); }
.card.s-idle .value { visibility: hidden; }
.card.s-running { border-color: var(--accent); background: var(--surface); transform: translateY(-2px); animation: glow .6s ease-in-out infinite; }
.card.s-running .value { visibility: hidden; }
.card.end:not(.s-on) { background: var(--surface); border-color: var(--line); }
.card.end:not(.s-on) .value { color: var(--text-3); }
@keyframes glow { 0%, 100% { box-shadow: 0 0 0 0 transparent; } 50% { box-shadow: 0 0 0 4px var(--accent-soft); } }
.wait { margin: 10px 0 0; font-size: 12.5px; }
@keyframes pop { from { opacity: 0; transform: translateY(-4px); } }
@media (max-width: 640px) { .arrow { display: none; } .card .title { font-size: 10.5px; } .say { max-width: 70%; } }
</style>
