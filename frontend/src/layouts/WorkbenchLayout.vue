<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const projectTabs = [
  { label: '项目知识库', to: '/knowledge-base' },
  { label: 'Agent 功能块', to: '/agent-blocks' },
  { label: '任务中心', to: '/tasks' },
  { label: '交付历史', to: '/deliveries' },
]
const title = computed(() => String(route.meta.title ?? 'AI-CodeReview'))
const isProjectArea = computed(() => route.meta.area === 'project')

function logout() {
  sessionStorage.removeItem('accessToken')
  router.replace('/login')
}
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
      <header class="global-topbar"><div class="topbar-page-title"><h1>{{ title }}</h1></div><label class="project-switch">项目：<select aria-label="切换项目"><option>全部项目</option><option>支付平台重构</option><option>风控引擎升级</option></select></label><label class="global-search"><span class="sr-only">全局搜索</span><input type="search" placeholder="搜索任务、报告、知识库" /></label><div class="topbar-actions"><button type="button" aria-label="通知">通知</button><button type="button" @click="logout" aria-label="退出登录">退出</button></div></header>
      <main class="workbench-main" :aria-label="title"><RouterView /></main>
    </div>
  </div>
</template>
