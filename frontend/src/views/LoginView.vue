<script setup>
import { onMounted, ref } from 'vue'
import { useAuth } from '../composables/useAuth'

const auth = useAuth()
const loginId = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const idInput = ref(null)

async function submit() {
  error.value = ''
  if (!loginId.value.trim() || !password.value) {
    error.value = '아이디와 비밀번호를 입력하세요.'
    return
  }
  loading.value = true
  try {
    await auth.login(loginId.value.trim(), password.value)
  } catch (e) {
    error.value = e.message || '로그인에 실패했습니다.'
    password.value = ''
  } finally {
    loading.value = false
  }
}

onMounted(() => idInput.value?.focus())
</script>

<template>
  <div class="login-wrap">
    <form class="login-card" @submit.prevent="submit">
      <div class="login-brand">
        <span class="logo">V</span>
        <div>
          <strong>VOC 장애 알림 AI Agent</strong>
          <small>상담이력 기반 자율형 장애 감지 · 알림</small>
        </div>
      </div>

      <h2>로그인</h2>
      <p v-if="auth.state.notice && !error" class="notice">{{ auth.state.notice }}</p>

      <div class="field">
        <label for="login-id">아이디</label>
        <input id="login-id" ref="idInput" v-model="loginId" autocomplete="username" maxlength="30">
      </div>
      <div class="field">
        <label for="login-pw">비밀번호</label>
        <input id="login-pw" v-model="password" type="password" autocomplete="current-password" maxlength="100">
      </div>
      <p v-if="error" class="err">{{ error }}</p>
      <button class="btn btn-primary btn-lg full" type="submit" :disabled="loading">
        {{ loading ? '확인 중…' : '로그인' }}
      </button>

      <!--<div class="demo">
        <span>시연 계정</span>
        <div><code>admin / admin1234</code> 시스템관리자</div>
        <div><code>agent01 / test1234</code> 상담사 · <code>it01 / test1234</code> IT담당자</div>
      </div>-->
    </form>
  </div>
</template>

<style scoped>
.login-wrap { min-height: 100vh; display: grid; place-items: center; padding: 24px 16px; background: radial-gradient(circle at 20% 10%, #e8eefd 0, transparent 45%), var(--bg); }
.login-card { width: 100%; max-width: 380px; background: var(--surface); border: 1px solid var(--line); border-radius: 14px; box-shadow: 0 10px 30px rgba(16, 24, 40, .08); padding: 28px; }
.login-brand { display: flex; align-items: center; gap: 10px; margin-bottom: 24px; }
.login-brand .logo { width: 34px; height: 34px; border-radius: 9px; background: linear-gradient(135deg, #3b6cff, #7c4dff); color: #fff; display: grid; place-items: center; font-weight: 800; }
.login-brand strong { display: block; font-size: 14px; }
.login-brand small { display: block; font-size: 11.5px; color: var(--text-3); }
h2 { font-size: 18px; margin-bottom: 14px; }
.field input { width: 100%; }
.full { width: 100%; margin-top: 4px; }
.err { margin: 0 0 10px; }
.notice { background: var(--accent-soft); color: var(--accent); border-radius: 8px; padding: 8px 10px; font-size: 12.5px; margin: 0 0 12px; }
.demo { margin-top: 18px; padding-top: 14px; border-top: 1px dashed var(--line-strong); font-size: 12px; color: var(--text-3); line-height: 1.8; }
.demo span { display: block; font-weight: 600; color: var(--text-2); }
.demo code { font-family: var(--mono); font-size: 11.5px; color: var(--text-2); background: var(--surface-2); padding: 1px 5px; border-radius: 4px; }
</style>
