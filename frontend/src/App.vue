<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'

type Project = { id: string; name: string }
type Task = { id: string; title: string; cycle_id: string; cycle_status: string }
type Source = { id: string; logical_name: string; processing_status: string; content_hash: string }
type Repository = { id: string; display_url: string }
type GitSnapshot = { id: string; base_sha: string; target_sha: string; diff_hash: string; coverage: { changedFiles: string[] } }
type ExternalEvidence = { id: string; evidence_type: string; logical_name: string; commit_sha: string; exit_code: number | null }
type Snapshot = { id: string; snapshot_hash: string; purpose: string }
type Run = { id: string; snapshot_id: string; run_status: string; poll_url: string }
type Evidence = { id: string; sourceType: string; excerpt: string; locator: Record<string, unknown>; precision: string }
type Result = { id: string; claim_id: string; claim_key: string; claim_text: string; status: string; reason: string; requires_human_confirmation: boolean; evidence: Evidence[] }
type Report = { id: string; status: string; content_hash: string; editorial_note: string; version: number }

const token = ref(sessionStorage.getItem('accessToken') ?? '')
const email = ref('submitter@example.local')
const password = ref('demo-submitter')
const projectName = ref('交付核验演示')
const reviewerEmail = ref('reviewer@example.local')
const reviewerAdded = ref(false)
const taskTitle = ref('交付记录核验')
const requirementKey = ref('REQ-001')
const sourceRole = ref('ACCEPTANCE')
const repositoryUrl = ref('https://github.com/yyy2045/one.git')
const baseRef = ref('origin/main~1')
const targetRef = ref('origin/main')
const includePaths = ref('backend/**')
const excludePaths = ref('')
const sourceFile = ref<File | null>(null)
const project = ref<Project | null>(null)
const task = ref<Task | null>(null)
const source = ref<Source | null>(null)
const repository = ref<Repository | null>(null)
const gitSnapshot = ref<GitSnapshot | null>(null)
const externalEvidence = ref<ExternalEvidence | null>(null)
const externalEvidenceType = ref('TEST')
const externalEvidenceName = ref('pytest-output.txt')
const externalEvidenceContent = ref('')
const externalExitCode = ref('0')
const formalSnapshot = ref<Snapshot | null>(null)
const run = ref<Run | null>(null)
const results = ref<Result[]>([])
const report = ref<Report | null>(null)
const reportNote = ref('')
const selectedResult = ref<Result | null>(null)
const question = ref('这条核验结论的依据是什么？')
const answer = ref<{ answer: string; fact_status: string; citations: Array<Record<string, unknown>> } | null>(null)
const retrievedEvidence = ref<Evidence[]>([])
const activeTab = ref<'record' | 'question'>('record')
const reviewReason = ref('已核对交付记录与证据引用。')
const message = ref('使用演示账户登录后，按左侧证据来源冻结正式输入。')
const busy = ref(false)
let pollTimer: number | undefined

const authenticated = computed(() => Boolean(token.value))
const isActiveRun = computed(() => run.value && ['QUEUED', 'RUNNING'].includes(run.value.run_status))
const resultEvidenceIds = computed(() => selectedResult.value?.evidence.map((item) => item.id) ?? [])
const questionEvidenceIds = computed(() => retrievedEvidence.value.length ? retrievedEvidence.value.map((item) => item.id) : resultEvidenceIds.value)

function headers(extra: HeadersInit = {}) {
  return { Authorization: `Bearer ${token.value}`, 'Idempotency-Key': crypto.randomUUID(), ...extra }
}

function splitPaths(value: string) {
  return value.split(/[\n,]/).map((item) => item.trim()).filter(Boolean)
}

function showError(error: unknown) {
  message.value = error instanceof Error ? error.message : '请求失败，请稍后重试。'
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.message ?? body.detail?.message ?? body.detail ?? `请求失败 (${response.status})`)
  return body as T
}

async function login() {
  busy.value = true
  try {
    const result = await request<{ access_token: string }>('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: email.value, password: password.value }) })
    token.value = result.access_token
    sessionStorage.setItem('accessToken', token.value)
    message.value = '登录成功。先创建项目和核验任务，再上传权威资料。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function createProject() {
  busy.value = true
  try {
    project.value = await request<Project>('/projects', { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ name: projectName.value }) })
    message.value = '项目已创建。现在创建本次交付的核验任务。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function createTask() {
  if (!project.value) return
  busy.value = true
  try {
    task.value = await request<Task>(`/projects/${project.value.id}/verification-tasks`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ title: taskTitle.value, requirement_key: requirementKey.value }) })
    message.value = '任务与首个核验轮次已创建。上传 Markdown 或纯文本资料。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function addReviewer() {
  if (!project.value) return
  busy.value = true
  try {
    await request(`/projects/${project.value.id}/members`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ user_email: reviewerEmail.value, role: 'REVIEWER' }) })
    reviewerAdded.value = true
    message.value = '审核者已加入项目。提交报告后可切换审核账户继续复核。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

function chooseFile(event: Event) {
  sourceFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
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
    message.value = '资料已处理为 READY。接下来登记只读 Git 仓库。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function registerRepository() {
  if (!project.value) return
  busy.value = true
  try {
    repository.value = await request<Repository>(`/projects/${project.value.id}/git-repositories`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ display_url: repositoryUrl.value }) })
    message.value = '只读仓库已登记。冻结 SHA 范围后不会再跟随分支变化。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function freezeGit() {
  if (!task.value || !repository.value) return
  busy.value = true
  try {
    gitSnapshot.value = await request<GitSnapshot>(`/cycles/${task.value.cycle_id}/git-snapshots`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ repository_id: repository.value.id, base_ref: baseRef.value, target_ref: targetRef.value, diff_mode: 'TWO_DOT', include_paths: splitPaths(includePaths.value), exclude_paths: splitPaths(excludePaths.value) }) })
    message.value = 'Git SHA 与路径范围已冻结。现在生成正式输入快照。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function freezeFormalSnapshot() {
  if (!task.value || !source.value || !gitSnapshot.value) return
  busy.value = true
  try {
    formalSnapshot.value = await request<Snapshot>(`/cycles/${task.value.cycle_id}/input-snapshots/formal`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ source_revision_ids: [source.value.id], git_snapshot_id: gitSnapshot.value.id, external_evidence_ids: externalEvidence.value ? [externalEvidence.value.id] : [] }) })
    message.value = '正式快照已冻结，可启动核验运行。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function importExternalEvidence() {
  if (!task.value || !gitSnapshot.value || !externalEvidenceContent.value.trim()) return
  busy.value = true
  try {
    externalEvidence.value = await request<ExternalEvidence>(`/cycles/${task.value.cycle_id}/external-evidence`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ evidence_type: externalEvidenceType.value, logical_name: externalEvidenceName.value, commit_sha: gitSnapshot.value.target_sha, content: externalEvidenceContent.value, exit_code: externalExitCode.value === '' ? null : Number(externalExitCode.value) }) })
    message.value = '外部测试或构建结果已绑定当前目标 SHA，将随正式快照冻结。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function loadResults() {
  if (!run.value) return
  results.value = await request<Result[]>(`/analysis-runs/${run.value.id}/results`, { headers: { Authorization: `Bearer ${token.value}` } })
  selectedResult.value ??= results.value[0] ?? null
}

async function refreshRun() {
  if (!run.value) return
  try {
    run.value = await request<Run>(run.value.poll_url, { headers: { Authorization: `Bearer ${token.value}` } })
    if (!['QUEUED', 'RUNNING'].includes(run.value.run_status)) {
      window.clearInterval(pollTimer)
      pollTimer = undefined
      await loadResults()
      message.value = run.value.run_status === 'SUCCEEDED' ? '分析已完成。请在中栏检查每条 Claim 的证据和状态。' : `运行结束：${run.value.run_status}`
    }
  } catch (error) { showError(error) }
}

async function startRun() {
  if (!formalSnapshot.value) return
  busy.value = true
  try {
    run.value = await request<Run>(`/input-snapshots/${formalSnapshot.value.id}/analysis-runs`, { method: 'POST', headers: headers() })
    message.value = '分析任务已入队。工作台每 3 秒刷新一次进度。'
    window.clearInterval(pollTimer)
    pollTimer = window.setInterval(refreshRun, 3000)
    await refreshRun()
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function createDraft() {
  if (!task.value || !run.value) return
  busy.value = true
  try {
    report.value = await request<Report>(`/cycles/${task.value.cycle_id}/reports/from-run/${run.value.id}`, { method: 'POST', headers: headers() })
    reportNote.value = report.value.editorial_note
    message.value = '报告草稿已从当前运行的结果快照生成。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function saveDraft() {
  if (!report.value) return
  busy.value = true
  try {
    report.value = await request<Report>(`/report-versions/${report.value.id}`, { method: 'PUT', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ editorial_note: reportNote.value, item_dispositions: {}, expected_version: report.value.version }) })
    message.value = '草稿说明已保存，报告哈希已更新。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function reportAction(action: 'submit' | 'approve' | 'request-changes' | 'reject' | 'publish') {
  if (!report.value) return
  busy.value = true
  try {
    const body = ['approve', 'request-changes', 'reject'].includes(action) ? JSON.stringify({ reason: reviewReason.value }) : undefined
    const headersForAction = body ? headers({ 'Content-Type': 'application/json' }) : headers()
    const result = await request<Report | { id: string }>(`/report-versions/${report.value.id}/${action}`, { method: 'POST', headers: headersForAction, body })
    if ('status' in result) report.value = result
    message.value = action === 'publish' ? '交付记录已发布为不可变版本。' : `报告操作完成：${action}`
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function askEvidence() {
  if (!formalSnapshot.value || !questionEvidenceIds.value.length) {
    message.value = '请先检索资料，或选择一条带有证据的核验结果。'
    return
  }
  busy.value = true
  try {
    answer.value = await request(`/input-snapshots/${formalSnapshot.value.id}/questions`, { method: 'POST', headers: headers({ 'Content-Type': 'application/json' }), body: JSON.stringify({ question: question.value, evidence_ids: questionEvidenceIds.value }) })
  } catch (error) { showError(error) } finally { busy.value = false }
}

async function retrieveEvidence() {
  if (!formalSnapshot.value || !question.value.trim()) return
  busy.value = true
  try {
    const result = await request<{ items: Array<{ evidenceId: string; excerpt: string; locator: Record<string, unknown>; precision: string }> }>(`/input-snapshots/${formalSnapshot.value.id}/search`, { method: 'POST', headers: { Authorization: `Bearer ${token.value}`, 'Content-Type': 'application/json' }, body: JSON.stringify({ query: question.value, limit: 5 }) })
    retrievedEvidence.value = result.items.map((item) => ({ id: item.evidenceId, sourceType: 'DOCUMENT', excerpt: item.excerpt, locator: item.locator, precision: item.precision }))
    message.value = retrievedEvidence.value.length ? `已检索到 ${retrievedEvidence.value.length} 条当前快照资料证据。` : '当前快照中没有匹配的资料证据。'
  } catch (error) { showError(error) } finally { busy.value = false }
}

function logout() {
  token.value = ''
  sessionStorage.removeItem('accessToken')
  window.clearInterval(pollTimer)
  pollTimer = undefined
  message.value = '已退出。'
}

onBeforeUnmount(() => window.clearInterval(pollTimer))
</script>

<template>
  <main class="app-shell">
    <header class="topbar">
      <div class="brand"><span class="brand-mark">AC</span><div><strong>AI-CodeReview</strong><small>多源证据核验与交付记录</small></div></div>
      <div class="topbar-status"><span class="status-dot" :class="isActiveRun ? 'is-live' : ''"></span><span>{{ run?.run_status ?? '准备输入' }}</span><button v-if="authenticated" class="text-button" @click="logout">退出</button></div>
    </header>

    <section v-if="!authenticated" class="login-surface">
      <div class="login-copy"><p class="overline">受控核验工作台</p><h1>把交付结论留在证据链上。</h1><p>演示账户可完成从资料、冻结 Git 到分析报告的最小闭环。</p></div>
      <form class="login-form" @submit.prevent="login"><label>邮箱<input v-model="email" type="email" autocomplete="username" /></label><label>密码<input v-model="password" type="password" autocomplete="current-password" /></label><button :disabled="busy">登录工作台</button></form>
    </section>

    <section v-else class="workspace">
      <aside class="source-panel panel">
        <div class="panel-heading"><div><p class="overline">01 · 输入</p><h2>证据来源</h2></div><span class="panel-state">{{ formalSnapshot ? '已冻结' : '草稿' }}</span></div>
        <div class="form-section"><label>项目名称<input v-model="projectName" :disabled="!!project" /></label><button :disabled="busy || !!project" @click="createProject">创建项目</button><p v-if="project" class="item-meta">{{ project.name }}</p><template v-if="project"><label>审核者邮箱<input v-model="reviewerEmail" :disabled="reviewerAdded" /></label><button :disabled="busy || reviewerAdded" @click="addReviewer">添加审核者</button><p v-if="reviewerAdded" class="item-meta">审核者 · REVIEWER</p></template></div>
        <div class="form-section"><label>任务标题<input v-model="taskTitle" :disabled="!!task" /></label><label>需求标识<input v-model="requirementKey" :disabled="!!task" /></label><button :disabled="busy || !project || !!task" @click="createTask">创建核验任务</button><p v-if="task" class="item-meta">轮次 · {{ task.cycle_status }}</p></div>
        <div class="form-section"><label>资料角色<select v-model="sourceRole" :disabled="!!source"><option>ACCEPTANCE</option><option>REQUIREMENT</option><option>DESIGN</option><option>MEETING</option></select></label><label class="file-field">Markdown / 纯文本<input accept=".md,.txt,text/markdown,text/plain" type="file" :disabled="!!source" @change="chooseFile" /></label><button :disabled="busy || !task || !sourceFile || !!source" @click="uploadSource">上传资料版本</button><p v-if="source" class="item-meta">{{ source.logical_name }} · {{ source.processing_status }}</p></div>
        <div class="form-section git-section"><label>只读仓库<input v-model="repositoryUrl" :disabled="!!repository" /></label><button :disabled="busy || !source || !!repository" @click="registerRepository">登记仓库</button><template v-if="repository"><label>基准 Ref<input v-model="baseRef" :disabled="!!gitSnapshot" /></label><label>目标 Ref<input v-model="targetRef" :disabled="!!gitSnapshot" /></label><label>包含路径<input v-model="includePaths" :disabled="!!gitSnapshot" /></label><label>排除路径<input v-model="excludePaths" :disabled="!!gitSnapshot" /></label><button :disabled="busy || !!gitSnapshot" @click="freezeGit">冻结 Git 范围</button></template><p v-if="gitSnapshot" class="item-meta mono">{{ gitSnapshot.target_sha.slice(0, 12) }} · {{ gitSnapshot.coverage.changedFiles.length }} files</p></div>
        <div v-if="gitSnapshot" class="form-section"><label>外部证据类型<select v-model="externalEvidenceType" :disabled="!!externalEvidence"><option>TEST</option><option>BUILD</option></select></label><label>结果名称<input v-model="externalEvidenceName" :disabled="!!externalEvidence" /></label><label>退出码<input v-model="externalExitCode" type="number" :disabled="!!externalEvidence" /></label><label>结果摘要<textarea v-model="externalEvidenceContent" :disabled="!!externalEvidence" rows="3" placeholder="例如：pytest 12 passed"></textarea></label><button :disabled="busy || !externalEvidenceContent.trim() || !!externalEvidence" @click="importExternalEvidence">导入外部证据</button><p v-if="externalEvidence" class="item-meta">{{ externalEvidence.evidence_type }} · {{ externalEvidence.logical_name }} · {{ externalEvidence.exit_code ?? '未提供退出码' }}</p></div>
        <button class="freeze-button" :disabled="busy || !source || !gitSnapshot || !!formalSnapshot" @click="freezeFormalSnapshot">冻结正式输入快照</button>
      </aside>

      <section class="verification-panel panel">
        <div class="panel-heading"><div><p class="overline">02 · 分析</p><h2>交付核验</h2></div><button class="primary-action" :disabled="busy || !formalSnapshot || !!isActiveRun" @click="startRun">{{ run ? '重新分析' : '启动分析' }}</button></div>
        <div class="snapshot-strip"><div><span>资料</span><strong>{{ source?.processing_status ?? '未选择' }}</strong></div><div><span>Git</span><strong>{{ gitSnapshot ? 'SHA 已冻结' : '未冻结' }}</strong></div><div><span>快照</span><strong>{{ formalSnapshot ? 'FORMAL' : '未生成' }}</strong></div><div><span>运行</span><strong>{{ run?.run_status ?? '未启动' }}</strong></div></div>
        <div v-if="isActiveRun" class="run-progress"><span></span><div><strong>正在核验冻结范围</strong><small>仅轮询运行状态；不会把实时分支变更带入本次结论。</small></div></div>
        <div v-if="!results.length" class="empty-state"><strong>尚无核验结果</strong><p>冻结正式快照后启动分析。系统将保留资料、SHA、Hunk 与结果之间的关联。</p></div>
        <ol v-else class="result-list"><li v-for="item in results" :key="item.id" :class="['result-row', { selected: selectedResult?.id === item.id }]" @click="selectedResult = item"><div class="result-number">{{ item.claim_key.replace('DOC-', '') }}</div><div class="result-content"><div class="result-title"><strong>{{ item.claim_text }}</strong><span :class="['result-status', item.status.toLowerCase()]">{{ item.status }}</span></div><p>{{ item.reason }}</p><small>{{ item.evidence.length ? `${item.evidence.length} 条代码证据` : '没有可验证的代码证据' }}{{ item.requires_human_confirmation ? ' · 需人工确认' : '' }}</small></div></li></ol>
      </section>

      <aside class="inspector-panel panel">
        <div class="panel-heading"><div><p class="overline">03 · 复核</p><h2>核验详情</h2></div></div>
        <div class="tabs"><button :class="{ active: activeTab === 'record' }" @click="activeTab = 'record'">交付记录</button><button :class="{ active: activeTab === 'question' }" @click="activeTab = 'question'">证据问答</button></div>
        <template v-if="activeTab === 'record'"><div v-if="selectedResult" class="evidence-detail"><p class="detail-label">当前 Claim</p><strong>{{ selectedResult.claim_key }}</strong><p>{{ selectedResult.claim_text }}</p><div v-for="evidence in selectedResult.evidence" :key="evidence.id" class="evidence-row"><span>{{ evidence.sourceType }}</span><div><strong>{{ String(evidence.locator.path ?? '文件级定位') }}</strong><p>{{ evidence.excerpt }}</p><small>{{ evidence.precision }} · {{ String(evidence.locator.hunk ?? '') }}</small></div></div></div><div class="report-actions"><p class="detail-label">报告版本</p><strong>{{ report ? `${report.status} · ${report.content_hash.slice(0, 18)}…` : '尚未生成' }}</strong><button :disabled="busy || !run || !['SUCCEEDED', 'PARTIALLY_COMPLETED'].includes(run.run_status) || !!report" @click="createDraft">从结果创建草稿</button><label>草稿说明<textarea v-model="reportNote" :disabled="report?.status !== 'DRAFT'" rows="3"></textarea></label><button :disabled="busy || report?.status !== 'DRAFT'" @click="saveDraft">保存草稿</button><button :disabled="busy || report?.status !== 'DRAFT'" @click="reportAction('submit')">提交审核</button><label>审核理由<textarea v-model="reviewReason" rows="2"></textarea></label><div class="review-actions"><button :disabled="busy || report?.status !== 'SUBMITTED'" @click="reportAction('approve')">批准</button><button :disabled="busy || report?.status !== 'SUBMITTED'" @click="reportAction('request-changes')">要求补证</button></div><button class="publish-action" :disabled="busy || report?.status !== 'APPROVED'" @click="reportAction('publish')">发布交付记录</button><small>后端会拒绝提交者自审；批准和发布始终以服务端状态为准。</small></div></template>
        <template v-else><div class="question-panel"><p>问答只读取当前快照中已授权的证据，不会修改任务、审批或发布状态。</p><textarea v-model="question" rows="4"></textarea><button :disabled="busy || !formalSnapshot" @click="retrieveEvidence">检索当前快照资料</button><div v-if="retrievedEvidence.length" class="retrieval-list"><small>将引用以下 {{ retrievedEvidence.length }} 条资料证据</small><p v-for="item in retrievedEvidence" :key="item.id">{{ item.excerpt }}</p></div><button :disabled="busy || !questionEvidenceIds.length" @click="askEvidence">基于受控证据回答</button><div v-if="answer" class="answer"><span :class="['result-status', answer.fact_status.toLowerCase()]">{{ answer.fact_status }}</span><p>{{ answer.answer }}</p><small>{{ answer.citations.length }} 条可解析引用</small></div></div></template>
      </aside>
    </section>
    <p class="notice" role="status">{{ message }}</p>
  </main>
</template>
