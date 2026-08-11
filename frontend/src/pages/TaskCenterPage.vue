<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface DeliveryItem { id: string; external_key: string; title: string; planning_status: string; verification_status: string; provider: string; web_url: string; source_updated_at: string | null }
interface VerificationTask { id: string; delivery_item_id: string | null; title: string; requirement_key: string; cycle_status: string; formal_snapshot_hash: string | null; report_status: string | null; published_record_id: string | null; updated_at: string }
interface ChangeLink { id: string; target_kind: 'PULL_REQUEST' | 'GIT_SNAPSHOT'; target_id: string; target_label: string; target_url: string | null; link_status: 'CANDIDATE' | 'CONFIRMED'; link_source: 'PLATFORM' | 'USER' | 'AGENT'; confidence: number | null; reason: string; agent_proposal_run_id: string | null; confirmed_at: string | null }
interface AgentCandidateTarget { target_kind: 'PULL_REQUEST' | 'GIT_SNAPSHOT'; target_id: string; target_label: string; input_ref: Record<string, string> }
interface AgentProposalResponse { created_candidate_count: number; skipped_existing_count: number; skipped_no_overlap_count: number }
type Filter = 'ALL' | 'UNASSIGNED' | 'VERIFYING' | 'NEEDS_CONFIRMATION' | 'FORMALIZED'

const items = ref<DeliveryItem[]>([])
const tasks = ref<VerificationTask[]>([])
const busy = ref(false)
const message = ref('从已同步的研发事项创建交付核验，不以 PR 关联或提交说明替代 Diff 证据。')
const activeFilter = ref<Filter>('ALL')
const query = ref('')
const showCreate = ref(false)
const createForm = ref({ deliveryItemId: '', title: '', requirementKey: '' })
const associationItem = ref<DeliveryItem | null>(null)
const candidateTargets = ref<AgentCandidateTarget[]>([])
const selectedCandidateTargetKeys = ref<string[]>([])
const changeLinks = ref<ChangeLink[]>([])
const associationMessage = ref('选择同一项目内已同步的 PR 或已绑定该事项的冻结 Git 范围，再让受控候选 Agent 提出关联建议。')

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
const selectedCandidateTargets = computed(() => candidateTargets.value.filter((target) => selectedCandidateTargetKeys.value.includes(targetKey(target))))

function stateLabel(value: string) { return ({ OPEN: '未开始', IN_PROGRESS: '进行中', DECLARED_DONE: '外部已声明完成', CANCELLED: '已取消', NOT_ASSESSED: '未核验', PARTIALLY_SUPPORTED: '部分支持', CONFIRMED: '已确认', CONFLICT: '存在冲突', INSUFFICIENT_EVIDENCE: '证据不足', DRAFT: '准备中', ANALYZING: '核验中', DRAFT_READY: '待提交报告', NEEDS_EVIDENCE: '待补证', NEEDS_CONFIRMATION: '待人工确认', PENDING_REVIEW: '待审批', APPROVED: '已批准', PUBLISHED: '已固化', REJECTED: '已驳回', CANDIDATE: '候选待确认' } as Record<string, string>)[value] ?? value }
function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—' }
function targetKey(target: AgentCandidateTarget) { return `${target.target_kind}:${target.target_id}` }
function linkSourceLabel(value: ChangeLink['link_source']) { return ({ AGENT: '受控候选 Agent', PLATFORM: '平台关系', USER: '人工确认' } as Record<ChangeLink['link_source'], string>)[value] }

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

async function loadAssociationData(item: DeliveryItem) {
  const projectId = selectedProjectId.value
  if (!projectId) return
  const [targets, links] = await Promise.all([
    apiRequest<AgentCandidateTarget[]>(`/projects/${projectId}/delivery-items/${item.id}/agent-change-candidate-targets`, { headers: projectHeaders() }),
    apiRequest<ChangeLink[]>(`/projects/${projectId}/delivery-items/${item.id}/change-links`, { headers: projectHeaders() }),
  ])
  if (associationItem.value?.id !== item.id || projectId !== selectedProjectId.value) return
  candidateTargets.value = targets
  changeLinks.value = links
}

async function openAssociationPanel(item: DeliveryItem) {
  associationItem.value = item
  candidateTargets.value = []
  selectedCandidateTargetKeys.value = []
  changeLinks.value = []
  associationMessage.value = '正在加载本事项允许交给候选 Agent 比较的目标范围。'
  busy.value = true
  try {
    await loadAssociationData(item)
    associationMessage.value = candidateTargets.value.length ? '候选 Agent 只读取事项来源版本与这里明确选定的 PR 标题/正文或已归属的冻结 Git 范围；它不会读取整个项目代码。' : '暂无可选的已同步 PR 或属于该事项的冻结 Git 范围。'
  } catch (error) {
    associationMessage.value = error instanceof Error ? error.message : '候选关联数据加载失败'
  } finally { busy.value = false }
}

function closeAssociationPanel() {
  associationItem.value = null
  candidateTargets.value = []
  selectedCandidateTargetKeys.value = []
  changeLinks.value = []
}

async function proposeAgentCandidates() {
  const projectId = selectedProjectId.value
  const item = associationItem.value
  if (!projectId || !item || !selectedCandidateTargets.value.length) return
  busy.value = true
  try {
    const result = await apiRequest<AgentProposalResponse>(`/projects/${projectId}/delivery-items/${item.id}/agent-change-candidates`, {
      method: 'POST', headers: projectHeaders(true), body: JSON.stringify({ targets: selectedCandidateTargets.value.map((target) => ({ target_kind: target.target_kind, target_id: target.target_id })) }),
    })
    associationMessage.value = `本次已创建 ${result.created_candidate_count} 条候选；${result.skipped_existing_count} 条已有关系保持原样，${result.skipped_no_overlap_count} 条未形成候选。`
    await loadAssociationData(item)
  } catch (error) {
    associationMessage.value = error instanceof Error ? error.message : '候选 Agent 运行失败'
  } finally { busy.value = false }
}

async function confirmCandidate(link: ChangeLink) {
  const projectId = selectedProjectId.value
  const item = associationItem.value
  if (!projectId || !item || link.link_status !== 'CANDIDATE') return
  if (!window.confirm(`确认“${link.target_label}”归属当前事项？这只确认事项—变更关系，不代表交付已完成。`)) return
  busy.value = true
  try {
    await apiRequest(`/projects/${projectId}/delivery-items/${item.id}/change-links`, {
      method: 'POST',
      headers: projectHeaders(true),
      body: JSON.stringify({
        pull_request_resource_id: link.target_kind === 'PULL_REQUEST' ? link.target_id : null,
        git_snapshot_id: link.target_kind === 'GIT_SNAPSHOT' ? link.target_id : null,
        reason: `人工确认候选关联：${link.reason}`,
      }),
    })
    associationMessage.value = '已确认事项—变更关系。该操作不会把事项标记为已完成；交付结论仍需固定双核读取冻结 Diff。'
    await loadAssociationData(item)
  } catch (error) {
    associationMessage.value = error instanceof Error ? error.message : '确认候选关联失败'
  } finally { busy.value = false }
}

watch(selectedProjectId, () => { closeAssociationPanel(); void load() }, { immediate: true })
</script>

<template>
  <section class="page page-tasks"><header class="page-heading"><div><h1>研发事项 / 交付项</h1><p v-if="selectedProject">{{ selectedProject.name }}：从已关联的研发事项进入交付核验、冻结证据与 Notebook。</p><p v-else>请先在项目概览创建或选择项目。</p></div><button class="primary-button" type="button" :disabled="!selectedProject || !items.length" @click="openCreate()">创建交付核验</button></header>
    <p class="page-context-note">{{ message }}</p>
    <template v-if="selectedProject"><div class="filter-row task-filters"><div class="filter-tabs"><button :class="{ active: activeFilter === 'ALL' }" type="button" @click="activeFilter = 'ALL'">全部</button><button :class="{ active: activeFilter === 'UNASSIGNED' }" type="button" @click="activeFilter = 'UNASSIGNED'">待创建</button><button :class="{ active: activeFilter === 'VERIFYING' }" type="button" @click="activeFilter = 'VERIFYING'">核验中</button><button :class="{ active: activeFilter === 'NEEDS_CONFIRMATION' }" type="button" @click="activeFilter = 'NEEDS_CONFIRMATION'">待确认</button><button :class="{ active: activeFilter === 'FORMALIZED' }" type="button" @click="activeFilter = 'FORMALIZED'">已固化</button></div><input v-model="query" placeholder="搜索事项标题 / 外部编号" /></div>
      <section v-if="associationItem" class="surface association-panel"><div class="surface-heading"><div><h2>事项—变更候选</h2><p>{{ associationItem.external_key }} · {{ associationItem.title }}</p></div><button type="button" @click="closeAssociationPanel">关闭</button></div><p class="association-note">{{ associationMessage }}</p><div class="association-grid"><section><h3>受控候选范围</h3><p>请选择本次允许比较的目标。未选择的 PR、Git 范围和项目代码不会被读取。</p><label v-for="target in candidateTargets" :key="targetKey(target)" class="check-line"><input v-model="selectedCandidateTargetKeys" type="checkbox" :value="targetKey(target)" :disabled="busy" /><span>{{ target.target_label }}</span><small>{{ target.target_kind === 'PULL_REQUEST' ? '已同步 PR' : '冻结 Git 范围' }}</small></label><p v-if="!candidateTargets.length" class="empty-row">没有可供本事项比较的目标。</p><button class="primary-button" type="button" :disabled="busy || !selectedCandidateTargets.length" @click="proposeAgentCandidates">生成候选关联</button></section><section><h3>关联结果</h3><p>候选只供人工确认；确认后仍只表示事项—变更归属，不是交付完成。</p><article v-for="link in changeLinks" :key="link.id" class="association-link"><div><strong>{{ link.target_label }}</strong><p>{{ linkSourceLabel(link.link_source) }} · {{ stateLabel(link.link_status) }}<template v-if="link.confidence !== null"> · 置信度 {{ link.confidence }}</template></p><small>{{ link.reason }}</small></div><a v-if="link.target_url" :href="link.target_url" target="_blank" rel="noreferrer">查看 PR</a><button v-if="link.link_status === 'CANDIDATE'" type="button" :disabled="busy" @click="confirmCandidate(link)">确认归属</button></article><p v-if="!changeLinks.length" class="empty-row">尚未形成任何事项—变更关联。</p></section></div></section>
      <form v-if="showCreate" class="inline-create-form" @submit.prevent="createVerification"><strong>创建交付核验</strong><label>研发事项<select v-model="createForm.deliveryItemId"><option v-for="item in items" :key="item.id" :value="item.id">{{ item.external_key }} · {{ item.title }}</option></select></label><label>核验标题<input v-model="createForm.title" maxlength="300" /></label><label>需求标识<input v-model="createForm.requirementKey" maxlength="100" /></label><div><button type="button" @click="showCreate = false">取消</button><button class="primary-button" type="submit" :disabled="busy">创建并进入准备</button></div></form>
      <section class="surface"><div v-if="visibleItems.length" class="data-table task-table"><div class="table-row table-header"><span>研发事项 / 交付项</span><span>外部计划</span><span>本系统核验</span><span>核验容器</span><span>来源更新时间</span><span>操作</span></div><div v-for="item in visibleItems" :key="item.id" class="table-row"><strong><a v-if="item.web_url" :href="item.web_url" target="_blank" rel="noreferrer">{{ item.title }}</a><template v-else>{{ item.title }}</template><small>{{ item.provider }} · {{ item.external_key }}</small></strong><span>{{ stateLabel(item.planning_status) }}</span><span>{{ stateLabel(item.verification_status) }}</span><span>{{ taskByItem.get(item.id) ? stateLabel(taskByItem.get(item.id)?.cycle_status ?? '') : '尚未创建' }}</span><time>{{ formatDate(item.source_updated_at) }}</time><div class="task-row-actions"><RouterLink v-if="taskByItem.get(item.id)" :to="`/tasks/${taskByItem.get(item.id)?.id}/notebook`">进入核验</RouterLink><button v-else type="button" @click="openCreate(item)">创建核验</button><button type="button" :disabled="busy" @click="openAssociationPanel(item)">关联变更</button></div></div></div><p v-else class="empty-row">没有符合当前筛选条件的研发事项。</p></section>
    </template>
  </section>
</template>
