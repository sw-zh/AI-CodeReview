<script setup lang="ts">
import { projectTodos, verificationTasks } from '../features/workbench/workbench-fixtures'
</script>

<template>
  <section class="page page-home">
    <header class="page-heading"><div><h1>工作台</h1><p>聚焦当前需要你处理的事项，优先处理高风险与临近截止的任务。</p></div></header>
    <div class="home-grid">
      <section class="surface queue-surface"><div class="surface-heading"><h2>按项目归类的待办</h2><RouterLink to="/tasks">查看任务中心</RouterLink></div><div class="project-table"><div class="project-table-head"><span>项目</span><span>我的待办</span><span>待审批</span><span>P0 风险</span><span>最近需要我处理的事项</span></div><RouterLink v-for="item in projectTodos" :key="item.id" class="project-row" :to="`/tasks/${item.id}/notebook`"><strong>{{ item.name }}</strong><span>{{ item.pendingCount }}</span><span>{{ item.approvalCount }}</span><span :class="{ 'risk-text': item.p0Count > 0 }">{{ item.p0Count }}</span><span>{{ item.nextAction }}</span></RouterLink></div></section>
      <section class="surface approvals-brief"><div class="surface-heading"><h2>待审批队列</h2><RouterLink to="/approvals">查看全部待审批</RouterLink></div><RouterLink v-for="task in verificationTasks" :key="task.id" class="approval-brief-row" :to="`/approvals/${task.id}`"><strong>{{ task.title }}</strong><span>{{ task.reportStatus }} · {{ task.owner }}</span><time>{{ task.updatedAt }}</time></RouterLink></section>
    </div>
    <section class="surface recent-deliveries"><div class="surface-heading"><h2>最近交付</h2><RouterLink to="/deliveries">查看交付历史</RouterLink></div><div class="data-table delivery-table"><div class="table-row table-header"><span>项目</span><span>交付内容</span><span>记录版本</span><span>审批人</span><span>发布时间</span></div><RouterLink v-for="task in verificationTasks" :key="task.id" class="table-row table-button" :to="`/deliveries/${task.id}`"><strong>{{ task.title }}</strong><span>交付核验记录</span><span>v1.2</span><span>{{ task.owner }}</span><time>{{ task.updatedAt }}</time></RouterLink></div></section>
  </section>
</template>
