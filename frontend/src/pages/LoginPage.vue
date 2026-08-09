<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const email = ref('submitter@example.local')
const password = ref('demo-submitter')
const busy = ref(false)
const error = ref('')

async function login() {
  busy.value = true
  error.value = ''
  try {
    const res = await fetch('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: email.value, password: password.value }),
    })
    const body = await res.json()
    if (!res.ok) throw new Error(body.detail?.message ?? '登录失败')
    sessionStorage.setItem('accessToken', body.access_token)
    sessionStorage.setItem('loginEmail', email.value)
    router.replace('/workbench')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section class="login-surface">
    <div class="login-copy">
      <p class="overline">AI-CodeReview</p>
      <h1>把交付结论留在证据链上。</h1>
      <p>演示账户可完成从上传资料、冻结 Git 快照到生成核验报告的最小闭环。</p>
    </div>
    <form class="login-form" @submit.prevent="login">
      <label>邮箱<input v-model="email" type="email" autocomplete="username" /></label>
      <label>密码<input v-model="password" type="password" autocomplete="current-password" /></label>
      <p v-if="error" class="login-error">{{ error }}</p>
      <button :disabled="busy">登录工作台</button>
    </form>
  </section>
</template>
