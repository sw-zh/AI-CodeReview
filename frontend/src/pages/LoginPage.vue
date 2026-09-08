<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import EvidenceLens from '../features/login/EvidenceLens.vue'

const router = useRouter()
const email = ref('submitter@example.local')
const password = ref('demo-submitter')
const showPassword = ref(false)
const busy = ref(false)
const error = ref('')

async function login() {
  if (busy.value || !email.value.trim() || !password.value) return
  busy.value = true
  error.value = ''
  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value.trim(), password: password.value }),
    })
    const body = await res.json()
    if (!res.ok) throw new Error(typeof body.detail === 'string' ? body.detail : body.detail?.message ?? '登录失败，请稍后重试')
    sessionStorage.setItem('accessToken', body.access_token)
    sessionStorage.setItem('loginEmail', email.value.trim())
    await router.replace('/workbench')
  } catch (e) {
    error.value = e instanceof TypeError ? '暂时无法连接服务，请检查网络后重试。' : e instanceof Error ? e.message : '登录失败，请稍后重试'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="auth-page">
    <section class="auth-story" aria-labelledby="auth-story-title">
      <div class="auth-brand">
        <img class="auth-brand-mark" src="/project-icon.svg" alt="" width="36" height="36" />
        <strong>AI-CodeReview</strong>
      </div>
      <div class="auth-story-content">
        <h1 id="auth-story-title">每一次交付，都有据可查。</h1>
        <p class="auth-introduction">把代码变更、交付内容与审查依据连在一起。让 AI 辅助发现问题，让团队基于证据作出判断。</p>
        <EvidenceLens />
      </div>
      <p class="auth-story-footer">连接 Pull Request，保留可追溯的交付记录。</p>
    </section>
    <section class="auth-entry" aria-labelledby="auth-login-title">
      <div class="auth-form-container">
        <header class="auth-form-heading"><h2 id="auth-login-title">欢迎回来</h2><p>登录工作台，继续你的项目审查。</p></header>
        <form class="auth-form" :aria-busy="busy" @submit.prevent="login">
          <div class="auth-field">
            <label for="auth-email">邮箱地址</label>
            <input id="auth-email" v-model="email" name="email" type="email" autocomplete="username" inputmode="email" autocapitalize="none" :spellcheck="false" placeholder="name@example.com" required :disabled="busy" :aria-describedby="error ? 'auth-error' : undefined" @input="error = ''" />
          </div>
          <div class="auth-field">
            <label for="auth-password">密码</label>
            <div class="auth-password-field">
              <input id="auth-password" v-model="password" name="password" :type="showPassword ? 'text' : 'password'" autocomplete="current-password" placeholder="输入你的密码" required :disabled="busy" :aria-describedby="error ? 'auth-error' : undefined" @input="error = ''" />
              <button class="auth-password-toggle" type="button" :aria-label="showPassword ? '隐藏密码' : '显示密码'" :aria-pressed="showPassword" :disabled="busy" @click="showPassword = !showPassword">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" /><circle cx="12" cy="12" r="3" /><path v-if="showPassword" d="m3 3 18 18" /></svg>
              </button>
            </div>
          </div>
          <div class="auth-feedback" aria-live="polite"><p v-if="error" id="auth-error" role="alert">{{ error }}</p></div>
          <button class="auth-submit" type="submit" :disabled="busy || !email.trim() || !password"><span v-if="busy" class="auth-spinner" aria-hidden="true"></span>{{ busy ? '正在登录…' : '登录工作台' }}<svg v-if="!busy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12h16m-6-6 6 6-6 6" /></svg></button>
        </form>
        <p class="auth-form-note"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="10" width="14" height="11" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3m-4 5v2" /></svg>登录后查看你有权限访问的项目</p>
      </div>
      <p class="auth-entry-footer">代码审查 · 交付核验 · 证据追溯</p>
    </section>
  </main>
</template>

<style scoped>
.auth-page { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); min-height: 100dvh; color: var(--ink); background: var(--surface); }
.auth-story { display: flex; flex-direction: column; min-width: 0; padding: 34px clamp(28px, 3vw, 48px) 26px; background: #edf2f8; border-right: 1px solid #dfe6f0; }
.auth-brand { display: flex; align-items: center; gap: 12px; }
.auth-brand-mark { display: block; flex-shrink: 0; width: 36px; height: 36px; }
.auth-brand strong { font-size: 18px; font-weight: 650; letter-spacing: -.025em; }
.auth-story-content { width: 100%; max-width: 720px; margin: auto 0; padding: 26px 0 18px; }
.auth-story h1 { margin: 0; font-size: clamp(24px, 2.25vw, 30px); line-height: 1.5; letter-spacing: -.025em; font-weight: 550; color: #304967; }
.auth-introduction { max-width: 54ch; margin: 12px 0 0; font-size: 13px; line-height: 1.85; color: #586b83; }
.auth-story-footer { margin: 0; color: #586b83; font-size: 12px; line-height: 1.7; }
.auth-entry { position: relative; display: flex; flex-direction: column; justify-content: center; align-items: center; min-width: 0; padding: 80px clamp(28px, 5vw, 80px); }
.auth-form-container { width: 100%; max-width: 380px; }
.auth-form-heading { margin-bottom: 34px; }
.auth-form-heading h2 { margin: 0; font-size: 28px; font-weight: 650; line-height: 1.4; letter-spacing: -.025em; }
.auth-form-heading p { margin: 10px 0 0; color: var(--muted); font-size: 14px; line-height: 1.7; }
.auth-form { display: grid; }
.auth-field + .auth-field { margin-top: 22px; }
.auth-field > label { display: block; margin-bottom: 9px; color: #354257; font-size: 13px; font-weight: 550; }
.auth-field input { width: 100%; min-width: 0; height: 48px; border: 1px solid #d4dce8; border-radius: 8px; padding: 12px 14px; color: var(--ink); background: #fbfcfe; font-size: 14px; transition: border-color 140ms ease-out, background-color 140ms ease-out; }
.auth-field input:hover:not(:disabled) { border-color: #a9b9cf; }
.auth-field input:focus { border-color: var(--brand); background: white; outline: 2px solid #dbe6fb; outline-offset: 1px; }
.auth-field input:disabled { opacity: .65; cursor: wait; }
.auth-password-field { position: relative; }
.auth-password-field input { padding-right: 50px; }
.auth-password-toggle { position: absolute; top: 4px; right: 4px; display: grid; place-items: center; width: 40px; height: 40px; border-radius: 5px; padding: 0; color: #66768c; background: transparent; }
.auth-password-toggle:hover:not(:disabled) { background: #eaf0f8; color: var(--brand); }
.auth-password-toggle svg { width: 19px; height: 19px; }
.auth-feedback { min-height: 30px; }
.auth-feedback p { margin: 10px 0 12px; padding: 10px 12px; border-radius: 6px; color: var(--danger); background: #fff0ef; font-size: 13px; line-height: 1.6; overflow-wrap: anywhere; }
.auth-submit { display: flex; align-items: center; justify-content: center; gap: 12px; width: 100%; min-height: 48px; border-radius: 8px; padding: 12px 16px; color: white; background: var(--brand); font-size: 14px; font-weight: 600; }
.auth-submit svg { width: 18px; height: 18px; }
.auth-submit:hover:not(:disabled) { background: #214f9c; }
.auth-submit:active:not(:disabled) { background: #1c4385; }
.auth-submit:disabled { opacity: .55; cursor: not-allowed; }
.auth-page button:focus-visible { outline: 2px solid var(--brand); outline-offset: 3px; }
.auth-spinner { width: 16px; height: 16px; border: 2px solid rgb(255 255 255 / .4); border-top-color: white; border-radius: 50%; animation: auth-spin 800ms linear infinite; }
.auth-form-note { display: flex; align-items: center; justify-content: center; gap: 7px; margin: 20px 0 0; color: var(--muted); font-size: 12px; line-height: 1.6; }
.auth-form-note svg { flex: 0 0 14px; width: 14px; height: 14px; }
.auth-entry-footer { position: absolute; bottom: 30px; margin: 0; color: var(--muted); font-size: 12px; line-height: 1.7; }
@keyframes auth-spin { to { transform: rotate(360deg); } }
@media (min-width: 1500px) {
  .auth-story { padding-left: max(80px, calc((100vw - 1280px) / 2)); }
}
@media (max-width: 900px) {
  .auth-story { padding: 30px 28px; }
  .auth-entry { padding: 70px 28px; }
  .auth-story h1 { font-size: 25px; }
}
@media (max-width: 700px) {
  .auth-page { grid-template-columns: 1fr; }
  .auth-story { padding: 24px; border-right: 0; border-bottom: 1px solid #dfe6f0; }
  .auth-brand strong { font-size: 16px; }
  .auth-brand-mark { width: 32px; height: 32px; }
  .auth-story-content { padding: 28px 0 0; max-width: none; }
  .auth-story h1 { font-size: 22px; }
  .auth-introduction { margin-top: 12px; font-size: 13px; }
  .auth-story-footer { display: none; }
  .auth-entry { padding: 36px 24px 24px; }
  .auth-form-heading { margin-bottom: 26px; }
  .auth-form-heading h2 { font-size: 24px; }
  .auth-entry-footer { position: static; margin-top: 36px; }
}
@media (prefers-reduced-motion: reduce) {
  .auth-spinner { animation: none; }
  .auth-field input { transition: none; }
}
</style>
