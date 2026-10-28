<script setup>
import { onMounted, ref } from 'vue'
import { useAuth } from '../composables/useAuth'
import mascot from '../assets/mascot.png'

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
      <img class="mascot" :src="mascot" alt="VOC 장애 알림 AI Agent 마스코트" width="150" height="150">
      <div class="login-brand">
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
        <div><code>admin / admin</code> 시스템관리자</div>
        <div><code>user01 / user01</code> 상담사 · <code>user02 / user02</code> IT담당자</div>
      </div>-->
    </form>
  </div>
</template>

<style scoped>
.login-wrap { min-height: 100vh; display: grid; place-items: center; padding: 24px 16px; background: linear-gradient(180deg, #e3f3fc 0, #f2f4f6 55%); }
.login-card { position: relative; width: 100%; max-width: 400px; margin-top: 96px; background: var(--surface); border: 1px solid var(--line); border-top: 4px solid var(--accent); border-radius: var(--radius); box-shadow: 0 10px 30px rgba(0, 0, 0, .06); padding: 70px 30px 32px; }
/* 마스코트가 카드 위로 살짝 걸쳐 앉음 */
.mascot { position: absolute; top: -104px; left: 50%; transform: translateX(-50%); width: 150px; height: 150px; object-fit: contain; filter: drop-shadow(0 8px 12px rgba(0, 0, 0, .12)); }
.login-brand { text-align: center; margin-bottom: 24px; }
.login-brand strong { display: block; font-size: 18px; color: var(--navy); letter-spacing: -0.03em; }
.login-brand small { display: block; font-size: 12px; color: var(--text-3); margin-top: 2px; }
h2 { font-size: 22px; color: #222; letter-spacing: -0.03em; margin-bottom: 18px; padding-bottom: 12px; border-bottom: 2px solid var(--text); }
.field input { width: 100%; }
.full { width: 100%; margin-top: 4px; }
.err { margin: 0 0 10px; }
.notice { background: var(--accent-soft); color: var(--accent-strong); border-radius: 4px; padding: 8px 10px; font-size: 12.5px; margin: 0 0 12px; }
.demo { margin-top: 18px; padding-top: 14px; border-top: 1px dashed var(--line-strong); font-size: 12px; color: var(--text-3); line-height: 1.8; }
.demo span { display: block; font-weight: 600; color: var(--text-2); }
.demo code { font-family: var(--mono); font-size: 11.5px; color: var(--text-2); background: var(--surface-2); padding: 1px 5px; border-radius: 4px; }
</style>
