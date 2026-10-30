<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import {
  fetchCriteria,
  createGrade,
  updateGrade,
  createBaseRule,
  updateBaseRule,
  createAdjustRule,
  updateAdjustRule,
} from '../api/vocApi'
import { fmtDateTime } from '../utils/format'
import SeverityBadge from '../components/voc/SeverityBadge.vue'
import { useAuth } from '../composables/useAuth'

/* 장애등급 판별기준 관리 - 등급 정의 / 기본 등급 규칙 / 등급 조정 규칙 */

const TABS = [
  { key: 'grade', label: '등급 정의' },
  { key: 'base', label: '기본 등급 규칙' },
  { key: 'adjust', label: '등급 조정 규칙' },
]
const ERROR_TYPES = ['로그인', '인증', '조회', '이체', 'UI오류', '기타']
const CHANNELS = ['앱', '웹', 'ARS', '기타']
const ROLES = ['담당', '부담당', '팀장']
const RULE_TYPES = {
  KEYWORD: '키워드',
  REPORT_COUNT: '제보 건수',
  MASS_SIGNAL: '대규모 신호',
  FALSE_POSITIVE: '오탐',
}
const ACTION_TYPES = {
  RAISE: '등급 상향',
  SET_GRADE: '등급 지정',
  RAISE_TO: '최소 등급',
  LOWER_TO: '최대 등급',
  FALSE_POSITIVE: '오탐 처리',
}
const SOURCE_DESC = {
  DB: 'DB 기준 사용 중',
  CODE: 'DB 기준 없음 · 코드 기본값 사용 중',
  'DB+CODE': 'DB 일부 비어 있음 · 빈 항목은 코드 기본값 사용',
}

const tab = ref('grade')
const data = ref(null)
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const formError = ref('')
const toast = ref('')
const showInactive = ref(true)

// 편집 상태: mode = 'edit' | 'new' | null
const editing = reactive({ mode: null, key: null })
const form = reactive({})
const auth = useAuth()
// 수정자는 로그인 사용자로 기록 (서버에서도 로그인 아이디로 저장)
const audit = reactive({ updated_by: auth.state.user?.login_id || 'admin', change_reason: '' })

const editable = computed(() => !!data.value?.tables_exist)
const gradeCodes = computed(() => (data.value?.grades || []).map((g) => g.grade_code))

const rows = computed(() => {
  if (!data.value) return []
  const list = tab.value === 'grade' ? data.value.grades
    : tab.value === 'base' ? data.value.base_rules
      : data.value.adjust_rules
  return showInactive.value ? list : list.filter((r) => r.use_yn !== false)
})

const counts = computed(() => {
  const d = data.value
  if (!d) return {}
  const on = (l) => l.filter((r) => r.use_yn !== false).length
  return { grade: on(d.grades), base: on(d.base_rules), adjust: on(d.adjust_rules) }
})

function rowKey(r) {
  if (tab.value === 'grade') return r.grade_code
  if (tab.value === 'base') return r.rule_id ?? `${r.error_type}-${r.channel || ''}`
  return r.rule_code
}

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    data.value = await fetchCriteria()
  } catch (e) {
    loadError.value = errMsg(e)
  } finally {
    loading.value = false
  }
}

function errMsg(e) {
  const d = e?.response?.data?.detail
  if (Array.isArray(d)) return d.map((x) => `${(x.loc || []).slice(-1)[0]}: ${x.msg}`).join(' / ')
  return d || e?.message || '요청 실패'
}

function flash(msg) {
  toast.value = msg
  setTimeout(() => { if (toast.value === msg) toast.value = '' }, 2500)
}

function switchTab(k) {
  tab.value = k
  closeForm()
}

function closeForm() {
  editing.mode = null
  editing.key = null
  formError.value = ''
}

function fill(obj) {
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, obj)
  audit.change_reason = ''
  formError.value = ''
}

/* ---------- 폼 열기 ---------- */
function openEdit(r) {
  editing.mode = 'edit'
  editing.key = rowKey(r)
  if (tab.value === 'grade') {
    fill({
      grade_code: r.grade_code,
      grade_name: r.grade_name || '',
      grade_order: r.grade_order ?? null,
      definition: r.definition || '',
      judge_examples: r.judge_examples || '',
      notify_on: r.notify_min_reports != null,
      notify_min_reports: r.notify_min_reports ?? 1,
      observe_yn: !!r.observe_yn,
      roles: (r.recipient_roles || '').split(',').map((x) => x.trim()).filter(Boolean),
      target_ack_min: r.target_ack_min ?? null,
      target_resolve_min: r.target_resolve_min ?? null,
      message_prefix: r.message_prefix || '[장애알림]',
      use_yn: r.use_yn !== false,
      valid_to: r.valid_to || '',
    })
  } else if (tab.value === 'base') {
    fill({
      error_type: r.error_type,
      channel: r.channel || '',
      system_name: r.system_name || '',
      base_grade: r.base_grade,
      rationale: r.rationale || '',
      use_yn: r.use_yn !== false,
      valid_to: r.valid_to || '',
    })
  } else {
    fill({
      rule_code: r.rule_code,
      rule_name: r.rule_name || '',
      rule_type: r.rule_type,
      keywords: (r.keywords || []).join(', '),
      threshold: r.threshold ?? null,
      action_type: r.action_type,
      raise_steps: r.raise_steps ?? 1,
      target_grade: r.target_grade || '',
      condition_grade: r.condition_grade || '',
      target_error_type: r.target_error_type || '',
      apply_order: r.apply_order ?? 100,
      description: r.description || '',
      use_yn: r.use_yn !== false,
      valid_to: r.valid_to || '',
    })
  }
}

function openNew() {
  editing.mode = 'new'
  editing.key = null
  const lastGrade = gradeCodes.value[gradeCodes.value.length - 1] || 'P4'
  if (tab.value === 'grade') {
    const n = (data.value?.grades || []).length + 1
    fill({
      grade_code: `P${n}`, grade_name: '', grade_order: n, definition: '', judge_examples: '',
      notify_on: false, notify_min_reports: 1, observe_yn: false, roles: ['담당'],
      target_ack_min: null, target_resolve_min: null, message_prefix: '[장애알림]', use_yn: true, valid_to: '',
    })
  } else if (tab.value === 'base') {
    fill({ error_type: '기타', channel: '', system_name: '', base_grade: lastGrade, rationale: '', use_yn: true, valid_to: '' })
  } else {
    fill({
      rule_code: '', rule_name: '', rule_type: 'KEYWORD', keywords: '', threshold: 2,
      action_type: 'RAISE', raise_steps: 1, target_grade: '', condition_grade: '', target_error_type: '',
      apply_order: 100, description: '', use_yn: true, valid_to: '',
    })
  }
}

/* ---------- 조정 규칙 입력 항목 노출 조건 ---------- */
const needKeywords = computed(() => ['KEYWORD', 'FALSE_POSITIVE'].includes(form.rule_type))
const needThreshold = computed(() => ['REPORT_COUNT', 'MASS_SIGNAL'].includes(form.rule_type))
const needSteps = computed(() => form.action_type === 'RAISE')
const needTarget = computed(() => ['SET_GRADE', 'RAISE_TO', 'LOWER_TO', 'FALSE_POSITIVE'].includes(form.action_type))

/* ---------- 저장 ---------- */
const nul = (v) => (v === '' || v === undefined ? null : v)
const num = (v) => (v === '' || v === null || v === undefined ? null : Number(v))

function buildPayload() {
  const isNew = editing.mode === 'new'
  const f = form
  let p
  if (tab.value === 'grade') {
    p = {
      grade_name: f.grade_name.trim(),
      grade_order: num(f.grade_order),
      definition: f.definition.trim(),
      judge_examples: nul(f.judge_examples.trim()),
      notify_min_reports: f.notify_on ? num(f.notify_min_reports) : null,
      observe_yn: !!f.observe_yn,
      recipient_roles: ROLES.filter((r) => f.roles.includes(r)).join(','),
      target_ack_min: num(f.target_ack_min),
      target_resolve_min: num(f.target_resolve_min),
      message_prefix: f.message_prefix.trim() || '[장애알림]',
      use_yn: f.use_yn,
    }
    if (isNew) p.grade_code = f.grade_code.trim().toUpperCase()
    else {
      p.clear_notify = !f.notify_on
      p.valid_to = nul(f.valid_to)
    }
  } else if (tab.value === 'base') {
    p = {
      channel: nul(f.channel),
      system_name: nul(f.system_name.trim()),
      base_grade: f.base_grade,
      rationale: nul(f.rationale.trim()),
      use_yn: f.use_yn,
    }
    if (isNew) p.error_type = f.error_type
    else p.valid_to = nul(f.valid_to)
  } else {
    const kw = f.keywords.split(/[,\n]/).map((x) => x.trim()).filter(Boolean)
    p = {
      rule_name: f.rule_name.trim(),
      keywords: needKeywords.value ? kw : null,
      threshold: needThreshold.value ? num(f.threshold) : null,
      action_type: f.action_type,
      raise_steps: needSteps.value ? num(f.raise_steps) : null,
      target_grade: needTarget.value ? nul(f.target_grade) : null,
      condition_grade: nul(f.condition_grade),
      target_error_type: nul(f.target_error_type),
      apply_order: num(f.apply_order) ?? 100,
      description: nul(f.description.trim()),
      use_yn: f.use_yn,
    }
    if (isNew) {
      p.rule_code = f.rule_code.trim().toUpperCase()
      p.rule_type = f.rule_type
    } else p.valid_to = nul(f.valid_to)
  }
  p.updated_by = audit.updated_by.trim() || 'admin'
  p.change_reason = nul(audit.change_reason.trim())
  return p
}

function validate(p) {
  if (editing.mode === 'edit' && !p.change_reason) return '변경 사유를 입력하세요. (판정 근거 추적용)'
  if (tab.value === 'grade') {
    if (editing.mode === 'new' && !/^P\d$/.test(p.grade_code)) return '등급코드는 P1~P9 형식입니다.'
    if (!p.grade_name) return '등급명을 입력하세요.'
    if (!p.grade_order || p.grade_order < 1) return '심각도 순서는 1 이상입니다.'
    if (!p.definition || p.definition.length < 2) return '등급 정의를 입력하세요.'
    if (p.notify_min_reports != null && p.notify_min_reports < 1) return '알림 최소 제보 건수는 1 이상입니다.'
    if (p.notify_min_reports != null && !p.recipient_roles) return '알림 대상 등급은 수신 역할이 1개 이상 필요합니다.'
  } else if (tab.value === 'adjust') {
    if (editing.mode === 'new' && !/^[A-Z0-9_]{2,30}$/.test(p.rule_code)) return '규칙코드는 영문 대문자·숫자·_ 2~30자입니다.'
    if (!p.rule_name) return '규칙명을 입력하세요.'
    if (needKeywords.value && !p.keywords.length) return '키워드를 1개 이상 입력하세요.'
    if (needThreshold.value && !(p.threshold >= 1)) return '기준 제보 건수는 1 이상입니다.'
    if (needSteps.value && !(p.raise_steps >= 1)) return '상향 단계는 1 이상입니다.'
    if (needTarget.value && !p.target_grade) return '지정 등급을 선택하세요.'
  }
  return ''
}

async function save() {
  const p = buildPayload()
  formError.value = validate(p)
  if (formError.value) return
  saving.value = true
  try {
    const isNew = editing.mode === 'new'
    let row
    if (tab.value === 'grade') row = isNew ? await createGrade(p) : await updateGrade(editing.key, p)
    else if (tab.value === 'base') row = isNew ? await createBaseRule(p) : await updateBaseRule(editing.key, p)
    else row = isNew ? await createAdjustRule(p) : await updateAdjustRule(editing.key, p)
    await load()
    flash(isNew ? '등록했습니다. 다음 판정부터 적용됩니다.' : '저장했습니다. 다음 판정부터 적용됩니다.')
    const fresh = row && rows.value.find((r) => rowKey(r) === rowKey(row))
    if (fresh) openEdit(fresh)
    else closeForm()
  } catch (e) {
    formError.value = errMsg(e)
  } finally {
    saving.value = false
  }
}

/* 조정 규칙 표에서 바로 켜기/끄기 */
async function toggleRule(r) {
  if (!editable.value) return
  const next = !(r.use_yn !== false)
  const reason = window.prompt(`${r.rule_code} 규칙을 ${next ? '사용' : '중지'}합니다. 변경 사유:`, next ? '규칙 재사용' : '규칙 일시 중지')
  if (reason === null) return
  try {
    await updateAdjustRule(r.rule_code, { use_yn: next, updated_by: audit.updated_by || 'admin', change_reason: reason || null })
    await load()
    flash(`${r.rule_code} ${next ? '사용' : '중지'}`)
    if (editing.key === r.rule_code) {
      const fresh = data.value.adjust_rules.find((x) => x.rule_code === r.rule_code)
      if (fresh) openEdit(fresh)
    }
  } catch (e) {
    flash(errMsg(e))
  }
}

/* ---------- 표시용 ---------- */
function gradeName(code) {
  return (data.value?.grades || []).find((g) => g.grade_code === code)?.grade_name || code
}

function ruleSummary(r) {
  let cond
  if (r.rule_type === 'KEYWORD' || r.rule_type === 'FALSE_POSITIVE') {
    const kw = r.keywords || []
    cond = `발화에 [${kw.slice(0, 4).join(', ')}${kw.length > 4 ? ` 외 ${kw.length - 4}` : ''}] 포함`
  } else if (r.rule_type === 'REPORT_COUNT') cond = `누적 제보 ${r.threshold}건 이상`
  else cond = `같은 증상 ${r.threshold}건 이상 (대규모)`
  if (r.condition_grade) cond += ` · 현재 ${r.condition_grade}일 때`
  if (r.target_error_type) cond += ` · ${r.target_error_type}만`
  let act
  if (r.action_type === 'RAISE') act = `${r.raise_steps || 1}단계 상향`
  else if (r.action_type === 'SET_GRADE') act = `${r.target_grade}로 지정`
  else if (r.action_type === 'RAISE_TO') act = `${r.target_grade} 미만이면 ${r.target_grade}로 상향`
  else if (r.action_type === 'LOWER_TO') act = `${r.target_grade}보다 높으면 ${r.target_grade}로 조정`
  else act = `오탐 처리${r.target_grade ? ` (${r.target_grade})` : ''}`
  return `${cond} → ${act}`
}

function notifyText(g) {
  return g.notify_min_reports == null ? '알림 없음' : `제보 ${g.notify_min_reports}건 이상`
}

function minText(v) {
  if (v == null) return '-'
  return v >= 60 && v % 60 === 0 ? `${v / 60}시간` : `${v}분`
}

const formTitle = computed(() => {
  const name = TABS.find((t) => t.key === tab.value).label
  if (editing.mode === 'new') return `${name} 추가`
  return `${name} 수정 · ${editing.key}`
})

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>장애등급 판별기준 관리</h2>
        <p>심각도 판별 에이전트가 사용하는 기준입니다. 저장하면 재배포 없이 다음 판정부터 적용됩니다.</p>
      </div>
      <div class="toolbar">
        <span v-if="data" class="badge" :class="data.source === 'DB' ? 'badge-green' : 'badge-amber'">
          {{ SOURCE_DESC[data.source] || data.source }}
        </span>
        <span v-if="data" class="badge badge-gray mono">기준 버전 {{ data.version }}</span>
        <button class="btn btn-sm" :disabled="loading" @click="load">새로고침</button>
      </div>
    </div>

    <div v-if="loadError" class="card"><div class="card-body err">기준을 불러오지 못했습니다: {{ loadError }}</div></div>

    <div v-if="data && !data.tables_exist" class="notice">
      <strong>판별기준 테이블이 없습니다.</strong>
      지금은 코드 기본값(<span class="mono">app/agents/rules.py</span>)으로 판정 중이며 이 화면에서는 조회만 됩니다.
      로컬은 <span class="mono">python scripts\init_db.py</span>, Cloud SQL은
      <span class="mono">sql/04_severity_criteria.sql</span>을 실행한 뒤 새로고침하세요.
    </div>

    <template v-if="data">
      <div class="tabs">
        <button v-for="t in TABS" :key="t.key" :class="{ on: tab === t.key }" @click="switchTab(t.key)">
          {{ t.label }} <span class="cnt">{{ counts[t.key] }}</span>
        </button>
        <div class="tabs-right">
          <label class="chk"><input v-model="showInactive" type="checkbox"> 미사용 포함</label>
          <button class="btn btn-sm btn-primary" :disabled="!editable" @click="openNew">+ 추가</button>
        </div>
      </div>

      <div class="crit-grid" :class="{ 'with-form': editing.mode }">
        <!-- ================= 목록 ================= -->
        <div class="card">
          <div class="card-head">
            <h3 v-if="tab === 'grade'">등급 정의<span class="sub">알림 기준·수신 대상·목표 시간. 정의와 판단 예시는 LLM 프롬프트에도 들어갑니다.</span></h3>
            <h3 v-else-if="tab === 'base'">기본 등급 규칙<span class="sub">오류유형·접촉채널별 시작 등급. 접촉채널이 일치하는 규칙이 우선합니다.</span></h3>
            <h3 v-else>등급 조정 규칙<span class="sub">적용 순서대로 기본 등급을 올리거나 지정합니다.</span></h3>
          </div>

          <div class="tbl-wrap">
            <!-- 등급 정의 -->
            <table v-if="tab === 'grade'" class="tbl">
              <thead>
                <tr><th>등급</th><th>정의</th><th>알림 기준</th><th>미대상 처리</th><th>수신 역할</th><th>목표 인지/조치</th><th>사용</th><th>최종 수정</th></tr>
              </thead>
              <tbody>
                <tr v-for="g in rows" :key="g.grade_code" :class="{ selected: editing.key === g.grade_code, off: g.use_yn === false }" @click="openEdit(g)">
                  <td class="nowrap"><SeverityBadge :value="g.grade_code" short /> <strong>{{ g.grade_name }}</strong></td>
                  <td class="wrap">{{ g.definition }}</td>
                  <td class="nowrap" :class="{ muted: g.notify_min_reports == null }">{{ notifyText(g) }}</td>
                  <td class="nowrap">
                    <span v-if="g.notify_min_reports === 1" class="muted">- (항상 알림)</span>
                    <span v-else class="badge" :class="g.observe_yn ? 'badge-blue' : 'badge-gray'">{{ g.observe_yn ? '관찰' : '미대상' }}</span>
                  </td>
                  <td class="nowrap">
                    <span v-if="!g.recipient_roles" class="muted">-</span>
                    <span v-for="r in (g.recipient_roles || '').split(',').filter(Boolean)" :key="r" class="chip">{{ r }}</span>
                  </td>
                  <td class="nowrap">{{ minText(g.target_ack_min) }} / {{ minText(g.target_resolve_min) }}</td>
                  <td><span class="badge" :class="g.use_yn === false ? 'badge-gray' : 'badge-green'">{{ g.use_yn === false ? '미사용' : '사용' }}</span></td>
                  <td class="muted nowrap">{{ g.updated_at ? fmtDateTime(g.updated_at) : '-' }}<br>{{ g.updated_by || '' }}</td>
                </tr>
              </tbody>
            </table>

            <!-- 기본 등급 규칙 -->
            <table v-else-if="tab === 'base'" class="tbl">
              <thead>
                <tr><th>오류유형</th><th>접촉채널</th><th>기본 등급</th><th>대상 시스템</th><th>근거</th><th>사용</th><th>최종 수정</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in rows" :key="rowKey(r)" :class="{ selected: editing.key === rowKey(r), off: r.use_yn === false }" @click="openEdit(r)">
                  <td><strong>{{ r.error_type }}</strong></td>
                  <td :class="{ muted: !r.channel }">{{ r.channel || '전체' }}</td>
                  <td class="nowrap"><SeverityBadge :value="r.base_grade" short /> {{ gradeName(r.base_grade) }}</td>
                  <td :class="{ muted: !r.system_name }">{{ r.system_name || '-' }}</td>
                  <td class="wrap">{{ r.rationale || '-' }}</td>
                  <td><span class="badge" :class="r.use_yn === false ? 'badge-gray' : 'badge-green'">{{ r.use_yn === false ? '미사용' : '사용' }}</span></td>
                  <td class="muted nowrap">{{ r.updated_at ? fmtDateTime(r.updated_at) : '-' }}<br>{{ r.updated_by || '' }}</td>
                </tr>
              </tbody>
            </table>

            <!-- 조정 규칙 -->
            <table v-else class="tbl">
              <thead>
                <tr><th>순서</th><th>규칙</th><th>유형</th><th>조건 → 조치</th><th>사용</th><th>최종 수정</th></tr>
              </thead>
              <tbody>
                <tr v-for="r in rows" :key="r.rule_code" :class="{ selected: editing.key === r.rule_code, off: r.use_yn === false }" @click="openEdit(r)">
                  <td class="mono">{{ r.apply_order }}</td>
                  <td><strong>{{ r.rule_name }}</strong><br><span class="mono muted">{{ r.rule_code }}</span></td>
                  <td><span class="badge" :class="r.rule_type === 'FALSE_POSITIVE' ? 'badge-gray' : 'badge-blue'">{{ RULE_TYPES[r.rule_type] || r.rule_type }}</span></td>
                  <td class="wrap">{{ ruleSummary(r) }}</td>
                  <td>
                    <button class="switch" :class="{ on: r.use_yn !== false }" :disabled="!editable"
                            :title="r.use_yn !== false ? '클릭하면 중지' : '클릭하면 사용'" @click.stop="toggleRule(r)">
                      <span />
                    </button>
                  </td>
                  <td class="muted nowrap">{{ r.updated_at ? fmtDateTime(r.updated_at) : '-' }}<br>{{ r.updated_by || '' }}</td>
                </tr>
              </tbody>
            </table>

            <div v-if="!rows.length" class="empty">등록된 항목이 없습니다.</div>
          </div>

          <div v-if="tab === 'adjust'" class="flow-note">
            판정 순서: 기본 등급 규칙으로 시작 등급 결정 → 조정 규칙을 순서 번호가 작은 것부터 적용 → 결과 등급의 알림 기준·수신 역할로 발송 여부 결정.
            대규모 신호 규칙의 기준 건수는 중복 제보 통합 에이전트에서도 사용합니다.
          </div>
        </div>

        <!-- ================= 편집 폼 ================= -->
        <div v-if="editing.mode" class="card form-card">
          <div class="card-head">
            <h3>{{ formTitle }}</h3>
            <button class="btn btn-sm btn-ghost" @click="closeForm">닫기</button>
          </div>
          <fieldset class="card-body" :disabled="!editable || saving">
            <!-- 등급 정의 폼 -->
            <template v-if="tab === 'grade'">
              <div class="field-row three">
                <div class="field">
                  <label>등급코드</label>
                  <input v-model="form.grade_code" :readonly="editing.mode === 'edit'" placeholder="P5">
                </div>
                <div class="field">
                  <label>등급명</label>
                  <input v-model="form.grade_name" maxlength="20" placeholder="긴급">
                </div>
                <div class="field">
                  <label>심각도 순서</label>
                  <input v-model.number="form.grade_order" type="number" min="1">
                </div>
              </div>
              <div class="field">
                <label>등급 정의</label>
                <textarea v-model="form.definition" rows="3" />
              </div>
              <div class="field">
                <label>판단 예시</label>
                <textarea v-model="form.judge_examples" rows="3" placeholder="예) 다수 고객 이체 불가, 출금 후 미입금" />
                <span class="hint">정의와 함께 LLM 판정 프롬프트에 들어갑니다.</span>
              </div>
              <div class="field">
                <label>알림 발송</label>
                <div class="inline">
                  <label class="chk"><input v-model="form.notify_on" type="checkbox"> 알림 대상 등급</label>
                  <template v-if="form.notify_on">
                    <span class="muted">제보</span>
                    <input v-model.number="form.notify_min_reports" class="w-num" type="number" min="1">
                    <span class="muted">건 이상이면 발송</span>
                  </template>
                  <span v-else class="muted">· 메신저는 보내지 않음</span>
                </div>
              </div>
              <div class="field">
                <label>관찰 여부</label>
                <div class="inline">
                  <label class="chk"><input v-model="form.observe_yn" type="checkbox"> 관찰</label>
                  <span class="muted">· 알림 미대상일 때 {{ form.observe_yn ? "'관찰'로 등록 → 센터관리자가 확인 후 수동 알림 또는 종결" : "'미대상'으로 자동 종결 (추가 제보가 쌓이면 재판정)" }}</span>
                </div>
              </div>
              <div class="field">
                <label>수신 역할</label>
                <div class="inline">
                  <label v-for="r in ROLES" :key="r" class="chk"><input v-model="form.roles" type="checkbox" :value="r"> {{ r }}</label>
                </div>
              </div>
              <div class="field-row three">
                <div class="field">
                  <label>목표 인지(분)</label>
                  <input v-model.number="form.target_ack_min" type="number" min="0">
                </div>
                <div class="field">
                  <label>목표 조치(분)</label>
                  <input v-model.number="form.target_resolve_min" type="number" min="0">
                </div>
                <div class="field">
                  <label>메시지 머리말</label>
                  <input v-model="form.message_prefix" maxlength="50">
                </div>
              </div>
            </template>

            <!-- 기본 등급 규칙 폼 -->
            <template v-else-if="tab === 'base'">
              <div class="field-row">
                <div class="field">
                  <label>오류유형</label>
                  <select v-model="form.error_type" :disabled="editing.mode === 'edit'">
                    <option v-for="t in ERROR_TYPES" :key="t" :value="t">{{ t }}</option>
                  </select>
                  <span v-if="editing.mode === 'edit'" class="hint">오류유형을 바꾸려면 새 규칙을 추가하고 이 규칙은 미사용 처리하세요.</span>
                </div>
                <div class="field">
                  <label>접촉채널</label>
                  <select v-model="form.channel">
                    <option value="">전체 접촉채널</option>
                    <option v-for="c in CHANNELS" :key="c" :value="c">{{ c }}</option>
                  </select>
                </div>
              </div>
              <div class="field-row">
                <div class="field">
                  <label>기본 등급</label>
                  <select v-model="form.base_grade">
                    <option v-for="g in data.grades" :key="g.grade_code" :value="g.grade_code">{{ g.grade_code }} {{ g.grade_name }}</option>
                  </select>
                </div>
                <div class="field">
                  <label>대상 시스템</label>
                  <input v-model="form.system_name" placeholder="예) 인터넷뱅킹 로그인">
                </div>
              </div>
              <div class="field">
                <label>근거</label>
                <textarea v-model="form.rationale" rows="3" />
              </div>
            </template>

            <!-- 조정 규칙 폼 -->
            <template v-else>
              <div class="field-row">
                <div class="field">
                  <label>규칙코드</label>
                  <input v-model="form.rule_code" class="mono" @input="form.rule_code = form.rule_code.toUpperCase()" :readonly="editing.mode === 'edit'" placeholder="ESC_MONEY">
                </div>
                <div class="field">
                  <label>적용 순서</label>
                  <input v-model.number="form.apply_order" type="number">
                </div>
              </div>
              <div class="field">
                <label>규칙명</label>
                <input v-model="form.rule_name" maxlength="100">
              </div>
              <div class="field-row">
                <div class="field">
                  <label>규칙 유형</label>
                  <select v-model="form.rule_type" :disabled="editing.mode === 'edit'">
                    <option v-for="(v, k) in RULE_TYPES" :key="k" :value="k">{{ v }} ({{ k }})</option>
                  </select>
                </div>
                <div class="field">
                  <label>조치</label>
                  <select v-model="form.action_type">
                    <option v-for="(v, k) in ACTION_TYPES" :key="k" :value="k">{{ v }}</option>
                  </select>
                </div>
              </div>
              <div v-if="needKeywords" class="field">
                <label>키워드</label>
                <textarea v-model="form.keywords" rows="2" placeholder="쉼표로 구분: 출금, 전액, 돈이 빠져" />
                <span class="hint">고객 발화에 하나라도 포함되면 적용됩니다. '그룹:단어' 형식(예: 기한:분 남았)은 그룹마다 하나 이상 포함돼야 적용됩니다.</span>
              </div>
              <div v-if="needThreshold" class="field">
                <label>기준 제보 건수</label>
                <input v-model.number="form.threshold" class="w-num" type="number" min="1">
              </div>
              <div class="field-row">
                <div v-if="needSteps" class="field">
                  <label>상향 단계</label>
                  <input v-model.number="form.raise_steps" type="number" min="1">
                </div>
                <div v-if="needTarget" class="field">
                  <label>지정 등급</label>
                  <select v-model="form.target_grade">
                    <option value="">선택</option>
                    <option v-for="g in data.grades" :key="g.grade_code" :value="g.grade_code">{{ g.grade_code }} {{ g.grade_name }}</option>
                  </select>
                </div>
              </div>
              <div class="field-row">
                <div class="field">
                  <label>적용조건 (현재 등급)</label>
                  <select v-model="form.condition_grade">
                    <option value="">항상</option>
                    <option v-for="g in data.grades" :key="g.grade_code" :value="g.grade_code">{{ g.grade_code }}일 때만</option>
                  </select>
                </div>
                <div class="field">
                  <label>적용 오류유형</label>
                  <select v-model="form.target_error_type">
                    <option value="">전체</option>
                    <option v-for="t in ERROR_TYPES" :key="t" :value="t">{{ t }}</option>
                  </select>
                </div>
              </div>
              <div class="field">
                <label>설명</label>
                <textarea v-model="form.description" rows="2" />
              </div>
            </template>

            <!-- 공통 -->
            <div class="field-row">
              <div class="field">
                <label>사용 여부</label>
                <label class="chk"><input v-model="form.use_yn" type="checkbox"> 사용</label>
              </div>
              <div v-if="editing.mode === 'edit'" class="field">
                <label>적용 종료일</label>
                <input v-model="form.valid_to" type="date">
              </div>
            </div>

            <div class="audit">
              <div class="field-row">
                <div class="field">
                  <label>수정자</label>
                  <input :value="(auth.state.user?.user_name || '') + ' (' + audit.updated_by + ')'" readonly>
                </div>
                <div class="field">
                  <label>변경 사유 <span v-if="editing.mode === 'edit'" class="req">*</span></label>
                  <input v-model="audit.change_reason" placeholder="예) 조회 장애 영향 확대로 상향">
                </div>
              </div>
              <p v-if="formError" class="err">{{ formError }}</p>
              <div class="actions">
                <button class="btn" type="button" @click="closeForm">취소</button>
                <button class="btn btn-primary" type="button" :disabled="!editable || saving" @click="save">
                  {{ saving ? '저장 중…' : (editing.mode === 'new' ? '등록' : '저장') }}
                </button>
              </div>
            </div>
          </fieldset>
        </div>
      </div>
    </template>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.notice { background: var(--warn-soft); color: #6b4300; border: 0; border-radius: var(--radius); padding: 12px 16px; font-size: 13px; margin-bottom: 16px; line-height: 1.7; }
.tabs { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin: 0 0 10px; padding: 0 10px; }
.tabs > button { font: inherit; font-weight: 600; font-size: 13.5px; color: var(--text-3); background: none; border: 0; border-radius: var(--radius); padding: 7px 14px; cursor: pointer; white-space: nowrap; }
.tabs > button:hover { background: rgba(255, 255, 255, .6); }
.tabs > button.on { color: var(--text); font-weight: 700; background: var(--surface); }
.tabs .cnt { display: inline-block; min-width: 20px; padding: 0 6px; margin-left: 4px; border-radius: var(--radius-badge); background: var(--p4-soft); color: var(--text-3); font-size: 12px; }
.tabs > button.on .cnt { background: var(--accent-soft); color: var(--accent); }
.tabs-right { margin-left: auto; display: flex; align-items: center; gap: 12px; white-space: nowrap; }
.chk { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text); font-weight: 500; cursor: pointer; }
.chk input { margin: 0; }

.crit-grid { display: grid; grid-template-columns: 1fr; gap: 10px; align-items: start; }
.crit-grid.with-form { grid-template-columns: minmax(0, 7fr) minmax(380px, 5fr); }
.crit-grid > .card { min-width: 0; }
.crit-grid > .card + .card { margin-top: 0; }
@media (max-width: 1180px) { .crit-grid.with-form { grid-template-columns: 1fr; } .form-card { position: static; } }
.form-card { position: sticky; top: 72px; }

.tbl-wrap { overflow-x: auto; }
.tbl td.wrap { min-width: 220px; white-space: normal; }
.tbl td.nowrap { white-space: nowrap; }
.tbl tbody tr.off td { color: var(--text-3); }
.chip { display: inline-block; padding: 1px 7px; margin: 0 4px 2px 0; border-radius: 6px; background: var(--surface-2); border: 1px solid var(--line); font-size: 12px; }
.flow-note { padding: 10px 16px; border-top: 1px solid var(--line); background: var(--surface-2); color: var(--text-2); font-size: 12.5px; border-radius: 0 0 var(--radius) var(--radius); }

.switch { width: 36px; height: 20px; border-radius: 999px; border: none; background: #c9d0d8; position: relative; cursor: pointer; padding: 0; transition: background .15s; }
.switch span { position: absolute; top: 2px; left: 2px; width: 16px; height: 16px; border-radius: 50%; background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.2); transition: left .15s; }
.switch.on { background: var(--ok); }
.switch.on span { left: 18px; }
.switch:disabled { opacity: .5; cursor: not-allowed; }

fieldset { border: none; margin: 0; min-width: 0; }
.field-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.field-row.three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.field > input:not([type=checkbox]), .field > select, .field > textarea { width: 100%; min-width: 0; }
.field > input.w-num, .w-num { width: 80px; }
.inline { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; min-height: 36px; }

.audit { border-top: 1px dashed var(--line-strong); margin-top: 4px; padding-top: 14px; }
.req { color: var(--p1); }
.actions { display: flex; justify-content: flex-end; gap: 8px; }
.err { margin: 0 0 10px; }
@media (max-width: 560px) { .field-row, .field-row.three { grid-template-columns: 1fr; } }
</style>
