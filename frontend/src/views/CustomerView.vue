<script setup>
import { computed, onMounted, reactive, ref, toRef } from 'vue'
import { fetchCustomers, createCustomer, updateCustomer } from '../api/adminApi'
import { navigate } from '../composables/useHashRoute'
import { fmtDateTime } from '../utils/format'
import { usePager } from '../composables/usePager'
import { keepListState } from '../composables/useListState'
import ListPager from '../components/voc/ListPager.vue'

/* 고객정보 관리: 고객 목록 · 등록 · 수정 (고객번호 자동 채번)
   상담데이터 등록 화면에서 고객을 선택하는 기준 정보 */

const rows = ref([])
const { page, pages, total, size, pageRows } = usePager(rows)
const loading = ref(false)
const loadError = ref('')
const filter = reactive({ keyword: '', gender: '' })
keepListState('customers', { keyword: toRef(filter, 'keyword'), gender: toRef(filter, 'gender'), page })

const editing = reactive({ mode: null, id: null })
const form = reactive({ customer_name: '', phone: '', gender: '', age: '' })
const current = ref(null)
const saving = ref(false)
const formError = ref('')
const toast = ref('')

async function load() {
  loading.value = true
  loadError.value = ''
  try {
    const params = {}
    if (filter.keyword.trim()) params.keyword = filter.keyword.trim()
    if (filter.gender) params.gender = filter.gender
    rows.value = await fetchCustomers(params)
  } catch (e) {
    loadError.value = e.message
  } finally {
    loading.value = false
  }
}

function flash(msg) {
  toast.value = msg
  setTimeout(() => { if (toast.value === msg) toast.value = '' }, 2500)
}

function openNew() {
  editing.mode = 'new'
  editing.id = null
  current.value = null
  Object.assign(form, { customer_name: '', phone: '', gender: '', age: '' })
  formError.value = ''
}

function openEdit(c) {
  editing.mode = 'edit'
  editing.id = c.customer_id
  current.value = c
  Object.assign(form, { customer_name: c.customer_name, phone: c.phone || '', gender: c.gender || '', age: c.age ?? '' })
  formError.value = ''
}

function closeForm() {
  editing.mode = null
  editing.id = null
  current.value = null
}

// 숫자만 입력해도 010-0000-0000 형태로
function formatPhone() {
  const d = form.phone.replace(/\D/g, '').slice(0, 11)
  if (d.length > 7) form.phone = `${d.slice(0, 3)}-${d.slice(3, d.length - 4)}-${d.slice(-4)}`
  else if (d.length > 3) form.phone = `${d.slice(0, 3)}-${d.slice(3)}`
  else form.phone = d
}

const phoneOk = computed(() => /^01[016789]-\d{3,4}-\d{4}$/.test(form.phone))

function validate() {
  if (!form.customer_name.trim()) return '고객명을 입력하세요.'
  if (!phoneOk.value) return '핸드폰번호를 010-0000-0000 형식으로 입력하세요.'
  if (form.age !== '' && (Number(form.age) < 0 || Number(form.age) > 130)) return '나이는 0~130 사이로 입력하세요.'
  return ''
}

async function save() {
  formError.value = validate()
  if (formError.value) return
  const p = {
    customer_name: form.customer_name.trim(),
    phone: form.phone,
    gender: form.gender || null,
    age: form.age === '' ? null : Number(form.age),
  }
  saving.value = true
  try {
    let row
    if (editing.mode === 'new') {
      row = await createCustomer(p)
      flash(`${row.customer_name} 고객을 등록했습니다. (${row.customer_id})`)
    } else {
      row = await updateCustomer(editing.id, p)
      flash('저장했습니다.')
    }
    await load()
    openEdit(rows.value.find((r) => r.customer_id === row.customer_id) || row)
  } catch (e) {
    formError.value = e.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>고객정보 관리</h2>
        <p>상담 대상 고객의 기본 정보를 관리합니다. 상담데이터 등록 시 고객을 선택하는 기준 정보로 사용됩니다.</p>
      </div>
      <button class="btn btn-primary" @click="openNew">+ 고객 등록</button>
    </div>

    <div class="split" :class="{ 'with-form': editing.mode }">
      <div class="card">
        <div class="card-head">
          <h3>고객 목록<span class="sub">{{ rows.length }}명</span></h3>
          <form class="toolbar" @submit.prevent="load">
            <input v-model="filter.keyword" placeholder="고객명 · 고객번호 · 핸드폰번호" style="width: 210px">
            <select v-model="filter.gender" @change="load">
              <option value="">성별 전체</option>
              <option>남</option>
              <option>여</option>
            </select>
            <button class="btn btn-sm" type="submit" :disabled="loading">조회</button>
          </form>
        </div>
        <p v-if="loadError" class="err card-body">{{ loadError }}</p>
        <div class="tbl-wrap">
          <table class="tbl">
            <thead><tr><th>고객번호</th><th>고객명</th><th>핸드폰번호</th><th>성별</th><th>나이</th><th>최근 상담</th></tr></thead>
            <tbody>
              <tr v-for="c in pageRows" :key="c.customer_id" :class="{ selected: editing.id === c.customer_id }" @click="openEdit(c)">
                <td class="mono">{{ c.customer_id }}</td>
                <td class="nowrap"><strong>{{ c.customer_name }}</strong></td>
                <td class="mono" :class="{ muted: !c.phone }">{{ c.phone || '미등록' }}</td>
                <td>{{ c.gender || '-' }}</td>
                <td>{{ c.age ?? '-' }}</td>
                <td class="muted nowrap">{{ c.last_call_at ? fmtDateTime(c.last_call_at) : '-' }}<span v-if="c.call_count > 1"> · {{ c.call_count }}건</span></td>
              </tr>
            </tbody>
          </table>
          <div v-if="!rows.length && !loading" class="empty">조회된 고객이 없습니다.</div>
        </div>
        <ListPager v-model:page="page" :pages="pages" :total="total" :size="size" />
      </div>

      <div v-if="editing.mode" class="card form-card">
        <div class="card-head">
          <h3>{{ editing.mode === 'new' ? '고객 등록' : `고객 상세 · ${current?.customer_name}` }}</h3>
          <button class="btn btn-sm btn-ghost" @click="closeForm">닫기</button>
        </div>
        <fieldset class="card-body" :disabled="saving">
          <p v-if="current" class="meta">
            등록 {{ fmtDateTime(current.created_at) }} · 최근 상담 {{ current.last_call_at ? fmtDateTime(current.last_call_at) : '없음' }}
          </p>
          <div class="field-row">
            <div class="field">
              <label>고객번호</label>
              <input :value="editing.mode === 'new' ? '자동 채번' : current?.customer_id" readonly class="mono">
              <span v-if="editing.mode === 'new'" class="hint">등록 시 자동 채번</span>
            </div>
            <div class="field">
              <label>고객명 <span class="req">*</span></label>
              <input v-model="form.customer_name" maxlength="50">
            </div>
          </div>
          <div class="field">
            <label>핸드폰번호 <span class="req">*</span></label>
            <input v-model="form.phone" class="mono" inputmode="numeric" placeholder="010-0000-0000" maxlength="13" @input="formatPhone">
          </div>
          <div class="field-row">
            <div class="field">
              <label>성별</label>
              <div class="inline">
                <label class="chk"><input v-model="form.gender" type="radio" value="남"> 남</label>
                <label class="chk"><input v-model="form.gender" type="radio" value="여"> 여</label>
              </div>
            </div>
            <div class="field">
              <label>나이</label>
              <input v-model="form.age" type="number" min="0" max="130">
            </div>
          </div>
          <div class="form-section">
            <p v-if="formError" class="err">{{ formError }}</p>
            <div class="form-actions">
              <button v-if="editing.mode === 'edit'" class="btn btn-ghost" type="button" @click="navigate('/consult-data', { customer: editing.id })">이 고객으로 상담데이터 등록 →</button>
              <button class="btn" type="button" @click="closeForm">취소</button>
              <button class="btn btn-primary" type="button" @click="save">{{ saving ? '저장 중…' : (editing.mode === 'new' ? '등록' : '저장') }}</button>
            </div>
          </div>
        </fieldset>
      </div>
    </div>

    <div v-if="toast" class="toast">{{ toast }}</div>
  </div>
</template>

<style scoped>
.err { margin: 0 0 10px; }
</style>
