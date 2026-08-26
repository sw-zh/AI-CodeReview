<script setup lang="ts">
import { computed, onMounted, provide, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { apiRequest, createProject, loadProjects, projectContextLoading, projects, selectProject, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface ExternalConnection { id: string }
interface SyncRun { status: string; changed_count: number; error_code: string | null; error_message: string | null }

const route = useRoute()
const router = useRouter()
const navigationItems = [
  { label: '主页', to: '/workbench' },
  { label: '代码交付', to: '/tasks' },
  { label: '知识库', to: '/knowledge-base' },
  { label: '审批', to: '/approvals' },
  { label: '交付记录', to: '/deliveries' },
  { label: '设置', to: '/settings' },
]
const title = computed(() => String(route.meta.title ?? 'AI-CodeReview'))
const showProjectOnboarding = ref(false)
const onboardingForm = ref({ name: '', description: '', repositoryUrl: '', credentialRef: '' })
const onboardingBusy = ref(false)
const onboardingStep = ref('')
const onboardingMessage = ref('')
const onboardingProjectId = ref<string | null>(null)
const onboardingConnectionId = ref<string | null>(null)
const onboardingRepositoryRegistered = ref(false)
const requiresProjectContext = computed(() => route.path !== '/workbench' && !projectContextLoading.value && !selectedProject.value)

function logout() {
  sessionStorage.removeItem('accessToken')
  router.replace('/login')
}

function changeProject(event: Event) {
  selectProject((event.target as HTMLSelectElement).value)
}

function resetOnboarding() {
  onboardingForm.value = { name: '', description: '', repositoryUrl: '', credentialRef: '' }
  onboardingMessage.value = ''
  onboardingStep.value = ''
  onboardingProjectId.value = null
  onboardingConnectionId.value = null
  onboardingRepositoryRegistered.value = false
}

function openProjectCreate() {
  onboardingMessage.value = ''
  showProjectOnboarding.value = true
}

function closeProjectCreate() {
  if (onboardingBusy.value) return
  showProjectOnboarding.value = false
  resetOnboarding()
}

function normalizeGitHubRepository(value: string) {
  const trimmed = value.trim().replace(/\/+$/, '').replace(/\.git$/, '')
  const slug = trimmed.replace(/^https?:\/\/github\.com\//i, '')
  if (!/^[^/\s]+\/[^/\s]+$/.test(slug)) throw new Error('请填写 GitHub 仓库地址，例如 https://github.com/owner/repository。')
  return { slug, displayUrl: `https://github.com/${slug}.git` }
}

provide('openProjectCreate', openProjectCreate)

async function submitProjectOnboarding() {
  const name = onboardingForm.value.name.trim()
  if (!name) return
  let repository: { slug: string; displayUrl: string }
  try { repository = normalizeGitHubRepository(onboardingForm.value.repositoryUrl) } catch (error) { onboardingMessage.value = error instanceof Error ? error.message : '仓库地址无效'; return }

  onboardingBusy.value = true
  onboardingMessage.value = ''
  try {
    if (!onboardingProjectId.value) {
      onboardingStep.value = '正在创建项目'
      const project = await createProject(name, onboardingForm.value.description.trim())
      onboardingProjectId.value = project.id
    }
    const projectId = onboardingProjectId.value
    if (!projectId) throw new Error('项目创建结果无效，请重新开始。')

    if (!onboardingConnectionId.value) {
      onboardingStep.value = '正在接入 GitHub'
      const connection = await apiRequest<ExternalConnection>(`/projects/${projectId}/external-connections`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${sessionStorage.getItem('accessToken') ?? ''}`, 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ provider: 'GITHUB', name: repository.slug, repository_slug: repository.slug, secret_ref: onboardingForm.value.credentialRef.trim() || null }),
      })
      onboardingConnectionId.value = connection.id
    }

    if (!onboardingRepositoryRegistered.value) {
      onboardingStep.value = '正在登记只读代码仓库'
      await apiRequest(`/projects/${projectId}/git-repositories`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${sessionStorage.getItem('accessToken') ?? ''}`, 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
        body: JSON.stringify({ display_url: repository.displayUrl, credential_ref: onboardingForm.value.credentialRef.trim() || null }),
      })
      onboardingRepositoryRegistered.value = true
    }

    onboardingStep.value = '正在同步 GitHub PR'
    const run = await apiRequest<SyncRun>(`/projects/${projectId}/external-connections/${onboardingConnectionId.value}/sync`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${sessionStorage.getItem('accessToken') ?? ''}`, 'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID() },
    })
    if (run.status !== 'SUCCEEDED') throw new Error(`${run.error_code ?? 'SOURCE_SYNC_FAILED'}：${run.error_message ?? 'GitHub 同步未完成'}`)

    showProjectOnboarding.value = false
    resetOnboarding()
    await router.push('/tasks')
  } catch (error) {
    onboardingMessage.value = `项目已创建，但${onboardingStep.value || '接入'}失败：${error instanceof Error ? error.message : '未知错误'}。请修正后在此重试。`
  } finally {
    onboardingBusy.value = false
  }
}

onMounted(() => { void loadProjects() })
</script>

<template>
  <div class="workbench-shell">
    <aside class="global-nav" aria-label="主导航">
      <RouterLink class="brand-lockup" to="/workbench" aria-label="AI-CodeReview 主页"><span class="brand-symbol" aria-hidden="true">AC</span><strong>AI-CodeReview</strong></RouterLink>
      <nav class="primary-navigation"><RouterLink v-for="item in navigationItems" :key="item.to" class="nav-item" :to="item.to">{{ item.label }}</RouterLink></nav>
      <p class="nav-footer">可信交付核验</p>
      <div class="demo-user-card" aria-label="当前用户：张伟，交付核验负责人"><span class="demo-user-avatar" aria-hidden="true">张</span><span class="demo-user-copy"><strong>张伟</strong><small>交付核验负责人</small></span><span class="demo-user-action">账户</span></div>
    </aside>
    <div class="workbench-content">
      <header class="global-topbar">
        <div class="topbar-page-title"><h1>{{ title }}</h1></div>
        <div class="topbar-project-actions"><label class="project-switch"><span>项目</span><select :value="selectedProjectId" :disabled="projectContextLoading" aria-label="选择当前项目" @change="changeProject"><option v-if="projectContextLoading" value="">加载项目中…</option><option v-else-if="!projects.length" value="">暂无项目</option><option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option></select></label><button class="topbar-create-project" type="button" @click="openProjectCreate">创建并接入</button></div>
        <div class="topbar-spacer" aria-hidden="true"></div>
        <div class="topbar-actions"><button type="button" @click="logout" aria-label="退出登录">退出</button></div>
      </header>
      <section v-if="showProjectOnboarding" class="project-onboarding" aria-label="创建并接入项目">
        <form class="project-onboarding-form" @submit.prevent="submitProjectOnboarding">
          <div class="project-onboarding-copy"><h2>创建并接入项目</h2><p>填写一次 GitHub 仓库地址，系统会登记只读代码源并同步 Pull Request；完成后即可选择一次代码交付开始审查。</p></div>
          <label>项目名称<input v-model="onboardingForm.name" maxlength="200" required autofocus placeholder="例如：支付平台重构" /></label>
          <label>项目说明（可选）<input v-model="onboardingForm.description" maxlength="4000" placeholder="用来区分这次开发工作的范围" /></label>
          <label class="project-onboarding-repository">GitHub 仓库地址<input v-model="onboardingForm.repositoryUrl" required placeholder="https://github.com/owner/repository" /></label>
          <label>私有仓库凭据引用（可选）<input v-model="onboardingForm.credentialRef" maxlength="160" placeholder="例如：GITHUB_SOURCE_TOKEN" /></label>
          <div class="project-onboarding-actions"><button class="primary-button" type="submit" :disabled="onboardingBusy || !onboardingForm.name.trim() || !onboardingForm.repositoryUrl.trim()">{{ onboardingBusy ? onboardingStep : '创建并同步 PR' }}</button><button type="button" :disabled="onboardingBusy" @click="closeProjectCreate">取消</button></div>
        </form>
        <p class="project-onboarding-note">公开仓库无需 Token。当前只支持 GitHub；不会写入仓库、执行代码或运行构建。</p>
        <p v-if="onboardingMessage" class="project-create-error" role="alert">{{ onboardingMessage }}</p>
      </section>
      <main class="workbench-main" :aria-label="title">
        <section v-if="requiresProjectContext" class="project-context-empty"><div><h2>{{ projects.length ? '先选择一个项目' : '先创建并接入一个项目' }}</h2><p>{{ projects.length ? '代码交付、资料、审批和交付记录都属于某个项目。请从顶部选择项目，或创建并接入一个新项目。' : '先接入 GitHub 仓库并同步 Pull Request。完成后，即可从一次代码交付开始审查。' }}</p><button class="primary-button" type="button" @click="openProjectCreate">创建并接入项目</button></div></section>
        <RouterView v-else />
      </main>
    </div>
  </div>
</template>
