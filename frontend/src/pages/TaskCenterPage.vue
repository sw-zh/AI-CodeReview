<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

type PullRequest = { number: string; baseRef: string; baseSha: string; headRef: string; headSha: string; mergedAt: string | null; draft: boolean; changedFiles: number | null }
type DeliveryItem = { id: string; external_key: string; title: string; planning_status: string; verification_status: string; web_url: string; source_updated_at: string | null; pull_request: PullRequest | null }
type VerificationTask = { id: string; delivery_item_id: string; cycle_status: string; published_record_id: string | null }
type CreatedTask = { id: string }
type Filter = 'ALL' | 'READY' | 'REVIEWING' | 'FORMALIZED'

const router = useRouter()
const items = ref<DeliveryItem[]>([])
const tasks = ref<VerificationTask[]>([])
const busyItemId = ref<string | null>(null)
const message = ref('选择一次 Pull Request 创建审查。Issue 仅作为可选的需求背景，不会出现在代码交付列表。')
const activeFilter = ref<Filter>('ALL')
const query = ref('')

const taskByItem = computed(() => new Map(tasks.value.map((task) => [task.delivery_item_id, task])))
const visibleItems = computed(() => items.value.filter((item) => {
  const task = taskByItem.value.get(item.id)
  const text = `${item.title} ${item.pull_request?.number ?? ''} ${item.pull_request?.headRef ?? ''}`.toLowerCase()
  if (query.value.trim() && !text.includes(query.value.trim().toLowerCase())) return false
  if (activeFilter.value === 'READY') return !task
  if (activeFilter.value === 'REVIEWING') return Boolean(task && !task.published_record_id)
  if (activeFilter.value === 'FORMALIZED') return Boolean(task?.published_record_id)
  return true
}))

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
}

function pullRequestState(item: DeliveryItem) {
  if (item.pull_request?.mergedAt) return '已合并'
  if (item.pull_request?.draft) return '草稿'
  return '待合并'
}

function reviewState(task: VerificationTask | undefined) {
  if (!task) return '尚未审查'
  return ({ DRAFT: '待准备', ANALYZING: '审查中', DRAFT_READY: '待提交', NEEDS_EVIDENCE: '待补证', NEEDS_CONFIRMATION: '待确认', PENDING_REVIEW: '待审批', APPROVED: '已批准', PUBLISHED: '已固化' } as Record<string, string>)[task.cycle_status] ?? task.cycle_status
}

async function load() {
  const projectId = selectedProjectId.value
  if (!projectId) { items.value = []; tasks.value = []; return }
  try {
    const [deliveryItems, taskList] = await Promise.all([
      apiRequest<DeliveryItem[]>(`/projects/${projectId}/delivery-items`, { headers: projectHeaders() }),
      apiRequest<VerificationTask[]>(`/projects/${projectId}/verification-tasks`, { headers: projectHeaders() }),
    ])
    if (projectId !== selectedProjectId.value) return
    items.value = deliveryItems.filter((item) => Boolean(item.pull_request))
    tasks.value = taskList
    message.value = items.value.length
      ? '每一行都是一次 GitHub Pull Request。创建审查后，系统会预填这次 PR 的分支范围，再冻结实际 Diff。'
      : '还没有同步到 Pull Request。请到“设置”同步 GitHub 仓库后再返回这里。'
  } catch (error) {
    if (projectId === selectedProjectId.value) message.value = error instanceof Error ? error.message : '代码交付加载失败'
  }
}

async function createReview(item: DeliveryItem) {
  const projectId = selectedProjectId.value
  if (!projectId || taskByItem.value.has(item.id)) return
  busyItemId.value = item.id
  try {
    const task = await apiRequest<CreatedTask>(`/projects/${projectId}/verification-tasks`, {
      method: 'POST',
      headers: projectHeaders(true),
      body: JSON.stringify({
        title: item.title,
        requirement_key: `pr:${item.id}`,
        delivery_item_id: item.id,
      }),
    })
    await router.push(`/tasks/${task.id}/notebook`)
  } catch (error) {
    message.value = error instanceof Error ? `创建审查失败：${error.message}` : '创建审查失败，请稍后重试。'
  } finally {
    busyItemId.value = null
  }
}

watch(selectedProjectId, () => { void load() }, { immediate: true })
</script>

<template>
  <section class="page page-tasks">
    <header class="page-heading">
      <div>
        <h1>代码交付</h1>
        <p v-if="selectedProject">{{ selectedProject.name }}：从一次 Pull Request 开始审查实际代码变更。</p>
        <p v-else>请先创建或选择项目。</p>
      </div>
    </header>
    <p class="page-context-note">{{ message }}</p>

    <template v-if="selectedProject">
      <div class="filter-row task-filters">
        <div class="filter-tabs">
          <button :class="{ active: activeFilter === 'ALL' }" type="button" @click="activeFilter = 'ALL'">全部 PR</button>
          <button :class="{ active: activeFilter === 'READY' }" type="button" @click="activeFilter = 'READY'">待审查</button>
          <button :class="{ active: activeFilter === 'REVIEWING' }" type="button" @click="activeFilter = 'REVIEWING'">审查中</button>
          <button :class="{ active: activeFilter === 'FORMALIZED' }" type="button" @click="activeFilter = 'FORMALIZED'">已固化</button>
        </div>
        <input v-model="query" placeholder="搜索 PR 标题、编号或分支" aria-label="搜索代码交付" />
      </div>

      <section class="surface code-delivery-list">
        <div v-if="visibleItems.length" class="data-table task-table">
          <div class="table-row table-header"><span>代码交付</span><span>分支范围</span><span>合并状态</span><span>审查状态</span><span>同步时间</span><span>操作</span></div>
          <div v-for="item in visibleItems" :key="item.id" class="table-row">
            <strong>
              <a v-if="item.web_url" :href="item.web_url" target="_blank" rel="noreferrer">PR #{{ item.pull_request?.number }} · {{ item.title }}</a>
              <template v-else>PR #{{ item.pull_request?.number }} · {{ item.title }}</template>
              <small>{{ item.pull_request?.changedFiles === null ? '变更文件数将在冻结 Diff 时确认' : `${item.pull_request?.changedFiles} 个变更文件` }}</small>
            </strong>
            <span class="pr-branch-range">{{ item.pull_request?.headRef || '未知来源分支' }} → {{ item.pull_request?.baseRef || '未知目标分支' }}</span>
            <span>{{ pullRequestState(item) }}</span>
            <span>{{ reviewState(taskByItem.get(item.id)) }}</span>
            <time>{{ formatDate(item.source_updated_at) }}</time>
            <div class="task-row-actions">
              <RouterLink v-if="taskByItem.get(item.id)" :to="`/tasks/${taskByItem.get(item.id)?.id}/notebook`">继续审查</RouterLink>
              <button v-else type="button" :disabled="busyItemId !== null" @click="createReview(item)">{{ busyItemId === item.id ? '创建中…' : '创建审查' }}</button>
            </div>
          </div>
        </div>
        <p v-else class="empty-row">没有符合当前筛选条件的 Pull Request。</p>
      </section>
    </template>
  </section>
</template>
