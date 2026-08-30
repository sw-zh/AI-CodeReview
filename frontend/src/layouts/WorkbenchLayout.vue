<script setup lang="ts">
import { computed, onMounted, provide, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { loadProjects, projectContextLoading, projects, selectProject, selectedProject, selectedProjectId, createProject } from '../features/projects/project-context'

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
const onboardingForm = ref({ name: '', description: '', repositoryUrl: '' })
const onboardingBusy = ref(false)
const onboardingStep = ref('')
const onboardingMessage = ref('')
const requiresProjectContext = computed(() => route.path !== '/workbench' && !projectContextLoading.value && !selectedProject.value)

function logout() {
  sessionStorage.removeItem('accessToken')
  router.replace('/login')
}

function changeProject(event: Event) {
  selectProject((event.target as HTMLSelectElement).value)
}

function resetOnboarding() {
  onboardingForm.value = { name: '', description: '', repositoryUrl: '' }
  onboardingMessage.value = ''
  onboardingStep.value = ''
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

provide('openProjectCreate', openProjectCreate)

async function submitProjectOnboarding() {
  const name = onboardingForm.value.name.trim()
  if (!name) return
  const repositoryUrl = onboardingForm.value.repositoryUrl.trim()
  if (!repositoryUrl) {
    onboardingMessage.value = '请填写 GitHub 仓库地址。'
    return
  }

  onboardingBusy.value = true
  onboardingMessage.value = ''
  onboardingStep.value = '正在创建项目'
  try {
    // One request creates the project and registers + queues a GitHub source
    // sync in a single transaction; the actual PR sync runs in the background.
    await createProject(name, onboardingForm.value.description.trim(), repositoryUrl)
    showProjectOnboarding.value = false
    resetOnboarding()
    await router.push('/tasks')
  } catch (error) {
    onboardingMessage.value = `创建项目失败：${error instanceof Error ? error.message : '未知错误'}。请修正后重试。`
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
      <div v-if="showProjectOnboarding" class="project-onboarding-overlay" @click.self="closeProjectCreate">
        <section class="project-onboarding" aria-label="创建并接入项目" role="dialog" aria-modal="true">
          <form class="project-onboarding-form" @submit.prevent="submitProjectOnboarding">
            <div class="project-onboarding-copy"><h2>创建并接入项目</h2><p>填写一次 GitHub 仓库地址，系统会登记只读代码源并在后台同步 Pull Request；完成后即可选择一次代码交付开始审查。</p></div>
            <label>项目名称<input v-model="onboardingForm.name" maxlength="200" required autofocus placeholder="例如：支付平台重构" /></label>
            <label>项目说明（可选）<input v-model="onboardingForm.description" maxlength="4000" placeholder="用来区分这次开发工作的范围" /></label>
            <label class="project-onboarding-repository">GitHub 仓库地址<input v-model="onboardingForm.repositoryUrl" required placeholder="https://github.com/owner/repository" /></label>
            <div class="project-onboarding-actions"><button class="primary-button" type="submit" :disabled="onboardingBusy || !onboardingForm.name.trim() || !onboardingForm.repositoryUrl.trim()">{{ onboardingBusy ? onboardingStep : '创建项目' }}</button><button type="button" :disabled="onboardingBusy" @click="closeProjectCreate">取消</button></div>
          </form>
          <p class="project-onboarding-note">当前只支持 GitHub；不会写入仓库、执行代码或运行构建。Pull Request 将在后台同步。</p>
          <p v-if="onboardingMessage" class="project-create-error" role="alert">{{ onboardingMessage }}</p>
        </section>
      </div>
      <main class="workbench-main" :aria-label="title">
        <section v-if="requiresProjectContext" class="project-context-empty"><div><h2>{{ projects.length ? '先选择一个项目' : '先创建并接入一个项目' }}</h2><p>{{ projects.length ? '代码交付、资料、审批和交付记录都属于某个项目。请从顶部选择项目，或创建并接入一个新项目。' : '先接入 GitHub 仓库并同步 Pull Request。完成后，即可从一次代码交付开始审查。' }}</p><button class="primary-button" type="button" @click="openProjectCreate">创建并接入项目</button></div></section>
        <RouterView v-else />
      </main>
    </div>
  </div>
</template>
