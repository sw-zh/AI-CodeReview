<script setup lang="ts">
import { computed, ref } from 'vue'

type Project = { id: string; name: string }
type Task = { id: string; title: string; cycle_id: string; cycle_status: string }
type Source = { id: string; logical_name: string; processing_status: string; content_hash: string }
type Snapshot = { id: string; snapshot_hash: string; purpose: string }

const token = ref(sessionStorage.getItem('accessToken') ?? '')
const email = ref('submitter@example.local')
const password = ref('demo-submitter')
const projectName = ref('交付核验演示')
const taskTitle = ref('用户登录验收')
const requirementKey = ref('REQ-001')
const sourceRole = ref('ACCEPTANCE')
const sourceFile = ref<File | null>(null)
const project = ref<Project | null>(null)
const task = ref<Task | null>(null)
const source = ref<Source | null>(null)
const snapshot = ref<Snapshot | null>(null)
const message = ref('请使用演示账户登录后，依次创建项目、任务、资料与准备快照。')
const busy = ref(false)

const authenticated = computed(() => Boolean(token.value))

function headers(extra: HeadersInit = {}) {
  return { Authorization: `Bearer ${token.value}`, 'Idempotency-Key': crypto.randomUUID(), ...extra }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.detail?.message ?? body.detail ?? `请求失败 (${response.status})`)
  return body as T
}

async function login() {
  busy.value = true
  try {
    const result = await request<{ access_token: string }>('/auth/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email.value, password: password.value }),
    })
    token.value = result.access_token
    sessionStorage.setItem('accessToken', token.value)
    message.value = '登录成功。现在创建项目。'
  } catch (error) { message.value = (error as Error).message } finally { busy.value = false }
}

async function createProject() {
  busy.value = true
  try {
    project.value = await request<Project>('/projects', { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ name: projectName.value }) })
    message.value = '项目已创建。现在创建核验任务。'
  } catch (error) { message.value = (error as Error).message } finally { busy.value = false }
}

async function createTask() {
  if (!project.value) return
  busy.value = true
  try {
    task.value = await request<Task>(`/projects/${project.value.id}/verification-tasks`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ title: taskTitle.value, requirement_key: requirementKey.value }) })
    message.value = '任务与首个草稿轮次已创建。现在上传 Markdown 或纯文本资料。'
  } catch (error) { message.value = (error as Error).message } finally { busy.value = false }
}

async function uploadSource() {
  if (!project.value || !sourceFile.value) return
  busy.value = true
  try {
    const form = new FormData()
    form.set('file', sourceFile.value)
    form.set('source_role', sourceRole.value)
    form.set('logical_name', sourceFile.value.name)
    source.value = await request<Source>(`/projects/${project.value.id}/sources`, { method: 'POST', headers: headers(), body: form })
    message.value = '资料已处理为 READY。现在冻结准备快照。'
  } catch (error) { message.value = (error as Error).message } finally { busy.value = false }
}

async function freezeSnapshot() {
  if (!task.value || !source.value) return
  busy.value = true
  try {
    snapshot.value = await request<Snapshot>(`/cycles/${task.value.cycle_id}/input-snapshots`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ source_revision_ids: [source.value.id] }) })
    message.value = '准备快照已冻结。Git 范围冻结后才能启动正式分析。'
  } catch (error) { message.value = (error as Error).message } finally { busy.value = false }
}

function chooseFile(event: Event) {
  sourceFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

function logout() {
  token.value = ''
  sessionStorage.removeItem('accessToken')
  message.value = '已退出。'
}
</script>

<template>
  <main class="shell">
    <header class="heading">
      <div><p class="eyebrow">AI-CodeReview</p><h1>任务与不可变输入快照</h1></div>
      <button v-if="authenticated" class="secondary" @click="logout">退出</button>
    </header>

    <section v-if="!authenticated" class="card">
      <h2>登录</h2>
      <label>邮箱<input v-model="email" type="email" /></label>
      <label>密码<input v-model="password" type="password" /></label>
      <button :disabled="busy" @click="login">登录</button>
    </section>

    <section v-else class="steps">
      <article class="card"><h2>1. 项目</h2><label>项目名称<input v-model="projectName" /></label><button :disabled="busy || !!project" @click="createProject">创建项目</button><p v-if="project">{{ project.name }} · {{ project.id }}</p></article>
      <article class="card"><h2>2. 核验任务</h2><label>任务标题<input v-model="taskTitle" /></label><label>需求标识<input v-model="requirementKey" /></label><button :disabled="busy || !project || !!task" @click="createTask">创建任务</button><p v-if="task">{{ task.title }} · {{ task.cycle_status }}</p></article>
      <article class="card"><h2>3. 资料版本</h2><label>资料角色<select v-model="sourceRole"><option>ACCEPTANCE</option><option>REQUIREMENT</option><option>DESIGN</option><option>MEETING</option></select></label><label>Markdown / 文本<input accept=".md,.txt,text/markdown,text/plain" type="file" @change="chooseFile" /></label><button :disabled="busy || !task || !sourceFile || !!source" @click="uploadSource">上传资料</button><p v-if="source">{{ source.logical_name }} · {{ source.processing_status }}</p></article>
      <article class="card"><h2>4. 准备快照</h2><button :disabled="busy || !source || !!snapshot" @click="freezeSnapshot">冻结准备快照</button><p v-if="snapshot">{{ snapshot.purpose }} · {{ snapshot.snapshot_hash }}</p></article>
    </section>
    <p class="message" role="status">{{ message }}</p>
  </main>
</template>
