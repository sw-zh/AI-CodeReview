<script setup lang="ts">
import { verificationTasks } from '../features/workbench/workbench-fixtures'
</script>

<template>
  <section class="page page-history"><header class="page-heading"><div><h1>交付历史</h1><p>已发布的正式交付记录可追溯至唯一输入快照与审批动作。</p></div></header><div class="filter-row"><select aria-label="项目"><option>全部项目</option></select><input placeholder="开始日期 - 结束日期" /><select aria-label="发布状态"><option>全部发布状态</option></select><input placeholder="需求标识" /><input placeholder="搜索交付记录名称" /></div><section class="surface history-list"><div class="history-month">2025 年 6 月</div><div class="data-table history-table"><div class="table-row table-header"><span>已发布交付记录</span><span>报告版本</span><span>关联任务</span><span>输入快照</span><span>审批结果</span><span>审批人</span><span>发布时间</span></div><RouterLink v-for="task in verificationTasks" :key="task.id" class="table-row table-button" :to="`/deliveries/${task.id}`"><strong>{{ task.title }}交付记录</strong><span>v1.2.0</span><span>{{ task.id }}</span><span>{{ task.snapshot }}</span><span>通过</span><span>{{ task.owner }}</span><time>{{ task.updatedAt }}</time></RouterLink></div></section></section>
</template>
