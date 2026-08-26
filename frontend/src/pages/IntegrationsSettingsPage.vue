<script setup lang="ts">
import { ref, watch } from 'vue'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface ExternalConnection { id: string; provider: string; name: string; repository_slug: string; secret_ref_configured: boolean; is_active: boolean; created_at: string }
interface SyncRun { id: string; connection_id: string; status: string; fetched_count: number; changed_count: number; page_count: number; error_code: string | null; error_message: string | null; finished_at: string | null }
interface GitRepository { id: string; display_url: string; read_only: boolean }

const connections = ref<ExternalConnection[]>([])
const syncRuns = ref<SyncRun[]>([])
const repositories = ref<GitRepository[]>([])
const busy = ref(false)
const message = ref('公开 GitHub 仓库可直接同步；私有仓库只接受服务端环境变量中的凭据引用。')
const connectionForm = ref({ name: '', repositorySlug: '', secretRef: '' })
const repositoryForm = ref({ displayUrl: '', credentialRef: '' })

function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '进行中或尚未完成' }
function syncFor(connectionId: string) { return syncRuns.value.find((run) => run.connection_id === connectionId) }

async function load() {
  const projectId = selectedProjectId.value
  if (!projectId) { connections.value = []; syncRuns.value = []; repositories.value = []; return }
  busy.value = true
  try {
    const [connectionList, runList, repositoryList] = await Promise.all([
      apiRequest<ExternalConnection[]>(`/projects/${projectId}/external-connections`, { headers: projectHeaders() }),
      apiRequest<SyncRun[]>(`/projects/${projectId}/source-sync-runs`, { headers: projectHeaders() }),
      apiRequest<GitRepository[]>(`/projects/${projectId}/git-repositories`, { headers: projectHeaders() }),
    ])
    if (projectId !== selectedProjectId.value) return
    connections.value = connectionList; syncRuns.value = runList; repositories.value = repositoryList
  } catch (error) {
    if (projectId === selectedProjectId.value) message.value = error instanceof Error ? error.message : '集成配置加载失败'
  } finally { if (projectId === selectedProjectId.value) busy.value = false }
}

async function createConnection() {
  const projectId = selectedProjectId.value
  const name = connectionForm.value.name.trim()
  const repositorySlug = connectionForm.value.repositorySlug.trim().replace(/^https:\/\/github\.com\//, '').replace(/\.git$/, '')
  if (!projectId || !name || !repositorySlug) return
  busy.value = true
  try {
    await apiRequest(`/projects/${projectId}/external-connections`, {
      method: 'POST', headers: projectHeaders(true),
      body: JSON.stringify({ provider: 'GITHUB', name, repository_slug: repositorySlug, secret_ref: connectionForm.value.secretRef.trim() || null }),
    })
    connectionForm.value = { name: '', repositorySlug: '', secretRef: '' }
    message.value = 'GitHub 只读连接已保存。公开仓库无需填写凭据引用。'
    await load()
  } catch (error) { message.value = error instanceof Error ? error.message : 'GitHub 连接创建失败' } finally { busy.value = false }
}

async function syncConnection(connection: ExternalConnection) {
  const projectId = selectedProjectId.value
  if (!projectId) return
  busy.value = true
  try {
    const run = await apiRequest<SyncRun>(`/projects/${projectId}/external-connections/${connection.id}/sync`, { method: 'POST', headers: projectHeaders(true) })
    message.value = run.status === 'SUCCEEDED' ? `已同步 ${run.changed_count} 个变更项。` : `${run.error_code ?? 'SOURCE_SYNC_FAILED'}：${run.error_message ?? '同步未完成'}`
    await load()
  } catch (error) { message.value = error instanceof Error ? error.message : 'GitHub 同步失败' } finally { busy.value = false }
}

async function registerRepository() {
  const projectId = selectedProjectId.value
  const displayUrl = repositoryForm.value.displayUrl.trim()
  if (!projectId || !displayUrl) return
  busy.value = true
  try {
    await apiRequest(`/projects/${projectId}/git-repositories`, {
      method: 'POST', headers: projectHeaders(true),
      body: JSON.stringify({ display_url: displayUrl, credential_ref: repositoryForm.value.credentialRef.trim() || null }),
    })
    repositoryForm.value = { displayUrl: '', credentialRef: '' }
    message.value = '只读 Git 仓库已登记。绑定 GitHub Issue 的任务只接受同一来源仓库的 Diff。'
    await load()
  } catch (error) { message.value = error instanceof Error ? error.message : '只读 Git 仓库登记失败' } finally { busy.value = false }
}

watch(selectedProjectId, () => { void load() }, { immediate: true })
</script>

<template>
  <section class="page page-integrations">
    <header class="page-heading"><div><h1>集成与设置</h1><p v-if="selectedProject">{{ selectedProject.name }}：只登记可追溯的外部事实和只读代码范围。</p><p v-else>请先选择项目。</p></div></header>
    <p class="page-context-note">{{ message }}</p>
    <template v-if="selectedProject">
      <div class="integration-grid">
        <section class="surface integration-section">
          <div class="surface-heading"><div><h2>GitHub 代码源</h2><p>同步 Pull Request、Issue 与 Milestone；代码交付列表只展示 Pull Request，不会写入 GitHub。</p></div></div>
          <div v-if="connections.length" class="integration-list"><article v-for="connection in connections" :key="connection.id"><div><strong>{{ connection.name }}</strong><p>{{ connection.repository_slug }} · {{ connection.secret_ref_configured ? '已配置私有凭据引用' : '公开连接' }}</p><small v-if="syncFor(connection.id)">最近同步：{{ syncFor(connection.id)?.status }} · {{ syncFor(connection.id)?.changed_count }} 项变更 · {{ formatDate(syncFor(connection.id)?.finished_at ?? null) }}</small></div><button type="button" :disabled="busy" @click="syncConnection(connection)">同步</button></article></div><p v-else class="empty-row">尚未接入 GitHub 仓库。</p>
          <form class="agent-form" @submit.prevent="createConnection"><h3>接入 GitHub 仓库</h3><label>连接名称<input v-model="connectionForm.name" required placeholder="例如：公开演示仓库" /></label><label>仓库（owner/repository）<input v-model="connectionForm.repositorySlug" required placeholder="例如：octocat/Spoon-Knife" /></label><label>私有仓库凭据引用（可选）<input v-model="connectionForm.secretRef" placeholder="例如：GITHUB_SOURCE_TOKEN" /></label><button class="primary-button" :disabled="busy">保存只读连接</button></form>
        </section>
        <section class="surface integration-section">
          <div class="surface-heading"><div><h2>只读 Git Diff</h2><p>冻结范围只用于交付证据，不执行仓库代码、Hook、构建或测试。</p></div></div>
          <div v-if="repositories.length" class="integration-list"><article v-for="repository in repositories" :key="repository.id"><div><strong>{{ repository.display_url }}</strong><p>{{ repository.read_only ? '只读访问已锁定' : '访问策略异常' }}</p></div></article></div><p v-else class="empty-row">尚未登记用于冻结 Diff 的 Git 仓库。</p>
          <form class="agent-form" @submit.prevent="registerRepository"><h3>登记只读 Git 仓库</h3><label>仓库 URL<input v-model="repositoryForm.displayUrl" required placeholder="https://github.com/owner/repository.git" /></label><label>私有仓库凭据引用（可选）<input v-model="repositoryForm.credentialRef" placeholder="例如：GITHUB_SOURCE_TOKEN" /></label><button class="primary-button" :disabled="busy">登记只读仓库</button></form>
        </section>
      </div>
    </template>
  </section>
</template>
