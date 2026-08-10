<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { loadProjects, projectContextLoading, projects, selectProject, selectedProjectId } from '../features/projects/project-context'

const route = useRoute()
const router = useRouter()
const projectTabs = [
  { label: '项目概览', to: '/workbench' },
  { label: '项目知识库', to: '/knowledge-base' },
  { label: '研发事项 / 交付项', to: '/tasks' },
  { label: '项目态势', to: '/project-status' },
  { label: '安全与质量', to: '/security-baselines' },
  { label: '正式记录', to: '/deliveries' },
  { label: 'Agent 功能块', to: '/agent-blocks' },
]
const title = computed(() => String(route.meta.title ?? 'AI-CodeReview'))
const isProjectArea = computed(() => route.meta.area === 'project')

function logout() {
  sessionStorage.removeItem('accessToken')
  router.replace('/login')
}

function changeProject(event: Event) {
  selectProject((event.target as HTMLSelectElement).value)
}

onMounted(() => { void loadProjects() })
</script>

<template>
  <div class="workbench-shell">
    <aside class="global-nav" aria-label="主导航">
      <RouterLink class="brand-lockup" to="/workbench" aria-label="AI-CodeReview 工作台"><span class="brand-symbol" aria-hidden="true">AC</span><strong>AI-CodeReview</strong></RouterLink>
      <nav class="primary-navigation">
        <RouterLink class="nav-item nav-project" :class="{ active: isProjectArea }" to="/workbench">项目空间</RouterLink>
        <div class="project-navigation" :class="{ active: isProjectArea }"><RouterLink v-for="item in projectTabs" :key="item.to" :to="item.to">{{ item.label }}</RouterLink></div>
        <RouterLink class="nav-item" :class="{ active: route.meta.area === 'approval' }" to="/approvals">待审批队列</RouterLink>
        <RouterLink class="nav-item" :class="{ active: route.meta.area === 'settings' }" to="/settings">集成与设置</RouterLink>
      </nav>
      <p class="nav-footer">可信交付核验</p>
      <button class="demo-user-card" type="button" aria-label="当前用户：张伟，交付核验负责人">
        <span class="demo-user-avatar" aria-hidden="true">张</span>
        <span class="demo-user-copy"><strong>张伟</strong><small>交付核验负责人</small></span>
        <span class="demo-user-action">账户</span>
      </button>
    </aside>
    <div class="workbench-content">
      <header class="global-topbar"><div class="topbar-page-title"><h1>{{ title }}</h1></div><label v-if="projects.length || projectContextLoading" class="project-switch">项目：<select :value="selectedProjectId" :disabled="projectContextLoading" aria-label="切换项目" @change="changeProject"><option v-if="projectContextLoading" value="">加载项目中…</option><option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option></select></label><label class="global-search"><span class="sr-only">全局搜索</span><input type="search" placeholder="搜索任务、报告、知识库" /></label><div class="topbar-actions"><button type="button" aria-label="通知">通知</button><button type="button" @click="logout" aria-label="退出登录">退出</button></div></header>
      <main class="workbench-main" :aria-label="title"><RouterView /></main>
    </div>
  </div>
</template>
