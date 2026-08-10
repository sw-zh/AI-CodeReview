<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { apiRequest, createProject, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface DeliveryItem { id: string; external_key: string; title: string; planning_status: string; verification_status: string; source_updated_at: string | null }
interface VerificationTask { id: string; delivery_item_id: string | null; title: string; cycle_status: string; published_record_id: string | null }
interface ProjectReport { id: string; task_title: string; status: string; submitted_at: string | null; latest_approval_action: string | null }
interface PublishedRecord { id: string; task_title: string; record_no: string; published_at: string; approval_by_name: string | null }
interface HealthSnapshot { id: string; as_of: string; summary: Record<string, unknown>; coverage: { dataGaps?: string[] } }
interface SecurityBaseline { id: string; target_sha: string; summary: Record<string, unknown>; coverage: Record<string, unknown>; created_at: string }

const deliveryItems = ref<DeliveryItem[]>([])
const tasks = ref<VerificationTask[]>([])
const reports = ref<ProjectReport[]>([])
const records = ref<PublishedRecord[]>([])
const healthSnapshots = ref<HealthSnapshot[]>([])
const securityBaselines = ref<SecurityBaseline[]>([])
const busy = ref(false)
const message = ref('选择项目后展示当前可追溯的研发事项、审批和正式记录。')
const projectName = ref('')
const projectDescription = ref('')
const creatingProject = ref(false)

const taskByItemId = computed(() => new Map(tasks.value.filter((task) => task.delivery_item_id).map((task) => [task.delivery_item_id as string, task])))
const latestHealth = computed(() => healthSnapshots.value[0] ?? null)
const latestSecurityBaseline = computed(() => securityBaselines.value[0] ?? null)

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
}

function planningLabel(value: string) {
  return ({ OPEN: '未开始', IN_PROGRESS: '进行中', DECLARED_DONE: '外部已声明完成', CANCELLED: '已取消' } as Record<string, string>)[value] ?? value
}

function verificationLabel(value: string) {
  return ({ NOT_ASSESSED: '未核验', PARTIALLY_SUPPORTED: '部分支持', CONFIRMED: '已确认', CONFLICT: '存在冲突', INSUFFICIENT_EVIDENCE: '证据不足' } as Record<string, string>)[value] ?? value
}

async function loadDashboard() {
  const projectId = selectedProjectId.value
  if (!projectId) {
    deliveryItems.value = []; tasks.value = []; reports.value = []; records.value = []; healthSnapshots.value = []; securityBaselines.value = []
    return
  }
  busy.value = true
  message.value = '正在读取项目事实与已固化记录…'
  try {
    const [items, taskList, reportList, recordList, healthList, baselineList] = await Promise.all([
      apiRequest<DeliveryItem[]>(`/projects/${projectId}/delivery-items`, { headers: projectHeaders() }),
      apiRequest<VerificationTask[]>(`/projects/${projectId}/verification-tasks`, { headers: projectHeaders() }),
      apiRequest<ProjectReport[]>(`/projects/${projectId}/report-versions?status_filter=SUBMITTED`, { headers: projectHeaders() }),
      apiRequest<PublishedRecord[]>(`/projects/${projectId}/published-records`, { headers: projectHeaders() }),
      apiRequest<HealthSnapshot[]>(`/projects/${projectId}/health-snapshots`, { headers: projectHeaders() }),
      apiRequest<SecurityBaseline[]>(`/projects/${projectId}/security-baselines`, { headers: projectHeaders() }),
    ])
    if (projectId !== selectedProjectId.value) return
    deliveryItems.value = items; tasks.value = taskList; reports.value = reportList; records.value = recordList; healthSnapshots.value = healthList; securityBaselines.value = baselineList
    message.value = '数据只呈现已同步、已核验或已固化的事实；未归属变更不会被计入项目完成情况。'
  } catch (error) {
    if (projectId !== selectedProjectId.value) return
    message.value = error instanceof Error ? error.message : '项目概览加载失败'
  } finally {
    if (projectId === selectedProjectId.value) busy.value = false
  }
}

async function submitProject() {
  const name = projectName.value.trim()
  if (!name) return
  creatingProject.value = true
  try {
    await createProject(name, projectDescription.value.trim())
    projectName.value = ''; projectDescription.value = ''
    message.value = '项目已创建，并已设为当前项目。接下来可接入外部事项和只读 Git 仓库。'
  } catch (error) {
    message.value = error instanceof Error ? error.message : '项目创建失败'
  } finally {
    creatingProject.value = false
  }
}

watch(selectedProjectId, () => { void loadDashboard() }, { immediate: true })
</script>

<template>
  <section class="page page-home">
    <header class="page-heading"><div><h1>项目概览</h1><p v-if="selectedProject">{{ selectedProject.description || '围绕可追溯的研发事项、交付核验与正式记录开展工作。' }}</p><p v-else>先创建或加入项目，再接入研发事项与交付证据。</p></div></header>

    <section v-if="!selectedProject" class="surface empty-context">
      <h2>还没有可进入的项目</h2>
      <p>创建项目后，系统会生成固定双核编排；项目事项仍需从外部来源同步或关联，不会由这里手工伪造。</p>
      <form class="context-form" @submit.prevent="submitProject"><label>项目名称<input v-model="projectName" maxlength="200" placeholder="例如：支付平台重构" /></label><label>项目说明（可选）<input v-model="projectDescription" maxlength="4000" placeholder="用于区分项目范围" /></label><button class="primary-button" type="submit" :disabled="creatingProject || !projectName.trim()">{{ creatingProject ? '创建中…' : '创建项目' }}</button></form>
    </section>

    <template v-else>
      <p class="page-context-note">{{ message }}</p>
      <div class="home-grid">
        <section class="surface queue-surface"><div class="surface-heading"><h2>研发事项与交付核验</h2><RouterLink to="/tasks">查看全部事项</RouterLink></div><div v-if="deliveryItems.length" class="project-table"><div class="project-table-head"><span>研发事项</span><span>外部计划</span><span>本系统核验</span><span>下一步</span></div><div v-for="item in deliveryItems.slice(0, 6)" :key="item.id" class="project-row"><strong>{{ item.title }}<small>{{ item.external_key }}</small></strong><span>{{ planningLabel(item.planning_status) }}</span><span>{{ verificationLabel(item.verification_status) }}</span><RouterLink v-if="taskByItemId.get(item.id)" :to="`/tasks/${taskByItemId.get(item.id)?.id}/notebook`">进入核验</RouterLink><RouterLink v-else to="/tasks">创建核验</RouterLink></div></div><p v-else class="empty-row">暂无同步的研发事项。先在“集成与设置”接入外部来源。</p></section>
        <section class="surface approvals-brief"><div class="surface-heading"><h2>待审批报告</h2><RouterLink to="/approvals">查看全部待审批</RouterLink></div><RouterLink v-for="report in reports.slice(0, 5)" :key="report.id" class="approval-brief-row" :to="`/approvals/${report.id}`"><strong>{{ report.task_title }}</strong><span>{{ report.latest_approval_action || '已提交，等待审批' }}</span><time>{{ formatDate(report.submitted_at) }}</time></RouterLink><p v-if="!reports.length" class="empty-row">当前项目没有待审批的交付核验报告。</p></section>
      </div>
      <section class="surface state-brief"><div class="surface-heading"><h2>项目态势与安全基线</h2><div><RouterLink to="/project-status">查看项目态势</RouterLink><RouterLink to="/security-baselines">查看安全与质量</RouterLink></div></div><div class="state-brief-grid"><div><strong>项目态势</strong><p v-if="latestHealth">截至 {{ formatDate(latestHealth.as_of) }} 的态势快照已固化；{{ latestHealth.coverage.dataGaps?.length || 0 }} 项数据缺口待补齐。</p><p v-else>尚未生成项目态势快照，因此不显示完成率或趋势判断。</p></div><div><strong>安全与质量</strong><p v-if="latestSecurityBaseline">最新基线针对 SHA {{ latestSecurityBaseline.target_sha.slice(0, 12) }}…，仅覆盖已导入的扫描范围。</p><p v-else>尚未导入扫描结果或固化安全基线。</p></div></div></section>
      <section class="surface recent-deliveries"><div class="surface-heading"><h2>最近正式记录</h2><RouterLink to="/deliveries">查看正式记录</RouterLink></div><div v-if="records.length" class="data-table delivery-table"><div class="table-row table-header"><span>正式记录</span><span>关联核验任务</span><span>审批人</span><span>固化时间</span></div><RouterLink v-for="record in records.slice(0, 6)" :key="record.id" class="table-row table-button" :to="`/deliveries/${record.id}`"><strong>{{ record.record_no }}</strong><span>{{ record.task_title }}</span><span>{{ record.approval_by_name || '—' }}</span><time>{{ formatDate(record.published_at) }}</time></RouterLink></div><p v-else class="empty-row">暂无正式记录。只有完成审批并固化的交付核验才会出现在这里。</p></section>
    </template>
  </section>
</template>
