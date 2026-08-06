<script setup lang="ts">
import { verificationTasks } from '../features/workbench/workbench-fixtures'
</script>

<template>
  <section class="page page-approvals"><header class="page-heading"><div><h1>待审批队列</h1><p>审批绑定报告版本与输入快照，只展示需要你作出决定的事项。</p></div></header><div class="filter-row"><select aria-label="项目"><option>全部项目</option></select><select aria-label="截止时间"><option>全部截止时间</option></select><select aria-label="证据状态"><option>全部证据状态</option></select><select aria-label="提交人"><option>全部提交人</option></select><input placeholder="搜索任务、报告或提交人" /></div><section class="surface"><div class="data-table approval-table"><div class="table-row table-header"><span>任务</span><span>报告版本</span><span>提交人</span><span>证据状态</span><span>待确认原因</span><span>提交时间</span><span>截止时间</span></div><RouterLink v-for="task in verificationTasks" :key="task.id" class="table-row table-button" :to="`/approvals/${task.id}`"><strong>{{ task.title }}</strong><span>v1.3.2</span><span>{{ task.owner }}</span><span>部分缺失</span><span>需要核对结论与证据引用</span><time>2025-06-12 10:24</time><time>{{ task.updatedAt }}</time></RouterLink></div><p class="table-note">报告或输入发生变化后，必须重新提交并发起审批。</p></section></section>
</template>
