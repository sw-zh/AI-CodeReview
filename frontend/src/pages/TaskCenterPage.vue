<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface DeliveryItem { id: string; external_key: string; title: string; planning_status: string; verification_status: string; provider: string; web_url: string; source_updated_at: string | null }
interface VerificationTask { id: string; delivery_item_id: string | null; title: string; requirement_key: string; cycle_status: string; formal_snapshot_hash: string | null; report_status: string | null; published_record_id: string | null; updated_at: string }
type Filter = 'ALL' | 'UNASSIGNED' | 'VERIFYING' | 'NEEDS_CONFIRMATION' | 'FORMALIZED'

const items = ref<DeliveryItem[]>([])
const tasks = ref<VerificationTask[]>([])
const busy = ref(false)
const message = ref('从已同步的研发事项创建交付核验，不以 PR 关联或提交说明替代 Diff 证据。')
const activeFilter = ref<Filter>('ALL')
const query = ref('')
const showCreate = ref(false)
const createForm = ref({ deliveryItemId: '', title: '', requirementKey: '' })

const taskByItem = computed(() => new Map(tasks.value.filter((task) => task.delivery_item_id).map((task) => [task.delivery_item_id as string, task])))
const visibleItems = computed(() => items.value.filter((item) => {
  const task = taskByItem.value.get(item.id)
  const q = query.value.trim().toLowerCase()
  if (q && !`${item.title} ${item.external_key}`.toLowerCase().includes(q)) return false
  if (activeFilter.value === 'UNASSIGNED') return !task
  if (activeFilter.value === 'VERIFYING') return Boolean(task && ['DRAFT', 'ANALYZING', 'DRAFT_READY', 'NEEDS_EVIDENCE'].includes(task.cycle_status))
  if (activeFilter.value === 'NEEDS_CONFIRMATION') return Boolean(task && ['NEEDS_CONFIRMATION', 'PENDING_REVIEW', 'REJECTED'].includes(task.cycle_status))
  if (activeFilter.value === 'FORMALIZED') return Boolean(task?.published_record_id)
  return true
}))

function stateLabel(value: string) { return ({ OPEN: '未开始', IN_PROGRESS: '进行中', DECLARED_DONE: '外部已声明完成', CANCELLED: '已取消', NOT_ASSESSED: '未核验', PARTIALLY_SUPPORTED: '部分支持', CONFIRMED: '已确认', CONFLICT: '存在冲突', INSUFFICIENT_EVIDENCE: '证据不足', DRAFT: '准备中', ANALYZING: '核验中', DRAFT_READY: '待提交报告', NEEDS_EVIDENCE: '待补证', NEEDS_CONFIRMATION: '待人工确认', PENDING_REVIEW: '待审批', APPROVED: '已批准', PUBLISHED: '已固化', REJECTED: '已驳回' } as Record<string, string>)[value] ?? value }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—' }

async function load() {
  const projectId = selectedProjectId.value
  if (!projectId) { items.value = []; tasks.value = []; return }
  busy.value = true
  try {
    const [deliveryItems, taskList] = await Promise.all([
      apiRequest<DeliveryItem[]>(`/projects/${projectId}/delivery-items`, { headers: projectHeaders() }),
      apiRequest<VerificationTask[]>(`/projects/${projectId}/verification-tasks`, { headers: projectHeaders() }),
    ])
    if (projectId !== selectedProjectId.value) return
    items.value = deliveryItems; tasks.value = taskList
    message.value = deliveryItems.length ? '计划状态与交付核验状态分开呈现；只有核验实际读取冻结 Diff 后才会更新核验结论。' : '暂无同步的研发事项。请先接入并同步外部来源。'
  } catch (error) {
    if (projectId === selectedProjectId.value) message.value = error instanceof Error ? error.message : '研发事项加载失败'
  } finally { if (projectId === selectedProjectId.value) busy.value = false }
}

function openCreate(item?: DeliveryItem) {
  createForm.value = { deliveryItemId: item?.id ?? items.value[0]?.id ?? '', title: item?.title ?? '', requirementKey: item?.external_key ?? '' }
  showCreate.value = true
}

async function createVerification() {
  const projectId = selectedProjectId.value
  const title = createForm.value.title.trim()
  const requirementKey = createForm.value.requirementKey.trim()
  if (!projectId || !createForm.value.deliveryItemId || !title || !requirementKey) return
  busy.value = true
  try {
    await apiRequest(`/projects/${projectId}/verification-tasks`, { method: 'POST', headers: projectHeaders(true), body: JSON.stringify({ title, requirement_key: requirementKey, delivery_item_id: createForm.value.deliveryItemId }) })
    showCreate.value = false
    message.value = '已创建交付核验容器。下一步应补齐目标资料、只读 Git 范围与证据，再运行固定双核。'
    await load()
  } catch (error) { message.value = error instanceof Error ? error.message : '交付核验创建失败' } finally { busy.value = false }
}

watch(selectedProjectId, () => { void load() }, { immediate: true })
</script>

<template>
  <section class="page page-tasks"><header class="page-heading"><div><h1>研发事项 / 交付项</h1><p v-if="selectedProject">{{ selectedProject.name }}：从已关联的研发事项进入交付核验、冻结证据与 Notebook。</p><p v-else>请先在项目概览创建或选择项目。</p></div><button class="primary-button" type="button" :disabled="!selectedProject || !items.length" @click="openCreate()">创建交付核验</button></header>
    <p class="page-context-note">{{ message }}</p>
    <template v-if="selectedProject"><div class="filter-row task-filters"><div class="filter-tabs"><button :class="{ active: activeFilter === 'ALL' }" type="button" @click="activeFilter = 'ALL'">全部</button><button :class="{ active: activeFilter === 'UNASSIGNED' }" type="button" @click="activeFilter = 'UNASSIGNED'">待创建</button><button :class="{ active: activeFilter === 'VERIFYING' }" type="button" @click="activeFilter = 'VERIFYING'">核验中</button><button :class="{ active: activeFilter === 'NEEDS_CONFIRMATION' }" type="button" @click="activeFilter = 'NEEDS_CONFIRMATION'">待确认</button><button :class="{ active: activeFilter === 'FORMALIZED' }" type="button" @click="activeFilter = 'FORMALIZED'">已固化</button></div><input v-model="query" placeholder="搜索事项标题 / 外部编号" /></div>
      <form v-if="showCreate" class="inline-create-form" @submit.prevent="createVerification"><strong>创建交付核验</strong><label>研发事项<select v-model="createForm.deliveryItemId"><option v-for="item in items" :key="item.id" :value="item.id">{{ item.external_key }} · {{ item.title }}</option></select></label><label>核验标题<input v-model="createForm.title" maxlength="300" /></label><label>需求标识<input v-model="createForm.requirementKey" maxlength="100" /></label><div><button type="button" @click="showCreate = false">取消</button><button class="primary-button" type="submit" :disabled="busy">创建并进入准备</button></div></form>
      <section class="surface"><div v-if="visibleItems.length" class="data-table task-table"><div class="table-row table-header"><span>研发事项 / 交付项</span><span>外部计划</span><span>本系统核验</span><span>核验容器</span><span>来源更新时间</span><span>操作</span></div><div v-for="item in visibleItems" :key="item.id" class="table-row"><strong><a v-if="item.web_url" :href="item.web_url" target="_blank" rel="noreferrer">{{ item.title }}</a><template v-else>{{ item.title }}</template><small>{{ item.provider }} · {{ item.external_key }}</small></strong><span>{{ stateLabel(item.planning_status) }}</span><span>{{ stateLabel(item.verification_status) }}</span><span>{{ taskByItem.get(item.id) ? stateLabel(taskByItem.get(item.id)?.cycle_status ?? '') : '尚未创建' }}</span><time>{{ formatDate(item.source_updated_at) }}</time><RouterLink v-if="taskByItem.get(item.id)" :to="`/tasks/${taskByItem.get(item.id)?.id}/notebook`">进入核验</RouterLink><button v-else type="button" @click="openCreate(item)">创建核验</button></div></div><p v-else class="empty-row">没有符合当前筛选条件的研发事项。</p></section>
    </template>
  </section>
</template>
