<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import mascot from '../../assets/mascot.png'
import { SEVERITY_LABEL } from '../../utils/format'

/* 사건 해결 장면 (상담이력등록 SCR-03)
   에이전트 실행 과정을 START 부터 END 까지 이어 재생하면 마지막에 결과를 '사건 해결' 카드와 도장으로 보여줍니다.
   [판별 결과 보기] → 판별 결과 팝업, [닫기]·×·Esc → 닫기 (바깥을 눌러서는 닫히지 않음) */

const props = defineProps({ run: { type: Object, required: true } })
const emit = defineEmits(['close', 'result'])

const out = computed(() => {
  const by = {}
  for (const s of props.run.steps || []) if (s.output?.node) by[s.output.node] = s.output
  return by
})

// 결과 종류는 판별 결과 팝업(RunResultModal)과 같은 기준
const scene = computed(() => {
  const o = out.value
  const det = o.detect || {}
  const dd = o.dedup || {}
  const sev = o.severity
  const sent = o.notify || o.record
  const g = sent?.severity || sev?.severity
  const what = `${g} ${det.error_type || '장애'}`
  const facts = [det.error_type && `${det.error_type} · ${det.channel || '-'}`,
    dd.customer_count > 1 && `같은 증상 고객 ${dd.customer_count}명`].filter(Boolean)
  if (props.run.status === 'FAILED') return { tone: 'p1', title: '수사가 중단됐습니다', em: '', stamp: '실행 실패', facts: ['실패한 단계를 확인해 주세요'] }
  if (o.improve) return { tone: 'ok', title: '장애가 아닌', em: '개선의견', tail: '입니다', stamp: '개선의견 기록', facts }
  if (!sev) return { tone: 'ok', title: '이상 없음 — ', em: '장애 아님', stamp: '무혐의', facts: ['일반 상담으로 판단'] }
  if (o.notify?.sent) return { tone: 'p1', title: '사건 해결! 범인은 ', em: what, stamp: 'IT 담당자\n출동 요청', facts: [...facts, `IT 담당자 ${(o.notify.recipients || []).length}명에게 메신저 전송`] }
  if (o.notify) return { tone: 'p1', title: '이미 수사 중인 사건 ', em: what, stamp: '제보 누적', facts: [...facts, o.notify.skipped_reason || '이미 알림 발송됨'] }
  if (sev.false_positive) return { tone: 'gray', title: '과거 오탐 사건과 동일 — ', em: '알림 제외', stamp: '오탐 종결', facts }
  if (sent?.incident_status === '관찰') return { tone: 'warn', title: `${g} ${SEVERITY_LABEL[g] || ''} · `, em: '관찰 대상', stamp: '센터관리자\n확인 요청', facts }
  return { tone: 'gray', title: `${g} · `, em: '알림 미대상', stamp: '종결', facts }
})

const onKey = (e) => { if (e.key === 'Escape') emit('close') }
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="solved">
    <div class="panel" :class="'tone-' + scene.tone" role="dialog" aria-modal="true" aria-label="사건 해결">
      <button class="x" type="button" title="닫기 (Esc)" aria-label="닫기" @click="emit('close')">×</button>
      <img :src="mascot" alt="콜록이" width="130" height="130">
      <div class="k">CASE CLOSED</div>
      <h2>{{ scene.title }}<em>{{ scene.em }}</em>{{ scene.tail || '' }}</h2>
      <p>{{ scene.facts.join(' · ') }}</p>
      <div class="stamp">{{ scene.stamp }}</div>
      <div class="actions">
        <button class="btn btn-sm" type="button" @click="emit('close')">닫기</button>
        <button class="btn btn-sm btn-primary" type="button" @click="emit('result')">판별 결과 보기 →</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.solved { position: fixed; inset: 0; background: rgba(25, 31, 40, .55); display: grid; place-items: center; z-index: 100; padding: 16px; animation: fade .3s ease-out; }
@keyframes fade { from { opacity: 0; } }
.panel { --tone: var(--p1); background: var(--surface); border-radius: 20px; padding: 22px 30px 24px; text-align: center; position: relative; max-width: min(560px, 100%); animation: zoom .35s cubic-bezier(.3, 1.6, .5, 1); margin-top: 60px; }
@keyframes zoom { from { transform: scale(.7); } }
.tone-ok { --tone: var(--ok); }
.tone-warn { --tone: var(--warn); }
.tone-gray { --tone: var(--text-2); }
.panel img { width: 130px; height: 130px; margin-top: -84px; object-fit: contain; filter: drop-shadow(0 6px 10px rgba(0, 0, 0, .2)); }
.k { font-size: 13px; font-weight: 700; color: var(--text-3); letter-spacing: .1em; }
h2 { margin: 2px 0 6px; font-size: 24px; word-break: keep-all; }
h2 em { font-style: normal; color: var(--tone); }
p { margin: 0; color: var(--text-2); font-size: 13.5px; word-break: keep-all; }
.stamp { position: absolute; right: -22px; top: 14px; border: 4px solid var(--tone); color: var(--tone); font-weight: 900; font-size: 16px; padding: 6px 12px; border-radius: 10px; background: rgba(255, 255, 255, .92); line-height: 1.25; white-space: pre-line; opacity: 0; transform: rotate(14deg) scale(3); animation: stamp .35s .55s cubic-bezier(.3, 1.4, .6, 1) forwards; }
@keyframes stamp { to { transform: rotate(14deg) scale(1); opacity: 1; } }
.actions { margin-top: 16px; display: flex; gap: 8px; justify-content: center; }
.x { position: absolute; top: 10px; left: 12px; width: 32px; height: 32px; border: 0; border-radius: 50%; background: transparent; color: var(--text-3); font-size: 22px; line-height: 1; cursor: pointer; }
.x:hover { background: var(--line); color: var(--text); }
@media (max-width: 560px) { .stamp { right: 6px; top: -10px; font-size: 13px; } h2 { font-size: 20px; } }
</style>
