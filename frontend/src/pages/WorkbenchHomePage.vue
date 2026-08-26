<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface DeliveryItem { id: string; external_key: string; title: string; planning_status: string; verification_status: string; source_updated_at: string | null }
interface VerificationTask { id: string; delivery_item_id: string | null; title: string; cycle_status: string; published_record_id: string | null }
interface ProjectReport { id: string; task_title: string; status: string; submitted_at: string | null; latest_approval_action: string | null }
interface PublishedRecord { id: string; task_title: string; record_no: string; published_at: string; approval_by_name: string | null }

type WorkAction = { title: string; description: string; to: string; label: string }

const deliveryItems = ref<DeliveryItem[]>([])
const tasks = ref<VerificationTask[]>([])
const reports = ref<ProjectReport[]>([])
const records = ref<PublishedRecord[]>([])
const busy = ref(false)
const message = ref('选择项目后，将显示当前工作和已留档的交付。')
const openProjectCreate = inject<() => void>('openProjectCreate', () => undefined)

const taskByItemId = computed(() => new Map(tasks.value.filter((task) => task.delivery_item_id).map((task) => [task.delivery_item_id as string, task])))
const unreviewedItems = computed(() => deliveryItems.value.filter((item) => !taskByItemId.value.has(item.id)))

const primaryAction = computed<WorkAction>(() => {
  if (!deliveryItems.value.length) return { title: '接入代码交付', description: '先同步 GitHub Pull Request，再开始审查一次实际代码变更。', to: '/settings', label: '接入 GitHub 仓库' }
  if (unreviewedItems.value.length) return { title: '开始代码审查', description: `有 ${unreviewedItems.value.length} 个 Pull Request 尚未建立审查。`, to: '/tasks', label: '查看待审 PR' }
  if (reports.value.length) return { title: '处理人工确认', description: `有 ${reports.value.length} 份报告已提交，等待不同成员确认。`, to: '/approvals', label: '前往确认' }
  return { title: '继续代码审查', description: '已建立审查任务；选择一项 PR 可继续冻结 Diff、运行审查并提交结论。', to: '/tasks', label: '查看代码交付' }
})

const recentWork = computed(() => deliveryItems.value.slice(0, 4))
const progressStages = computed(() => [
  { label: '代码交付已接入', value: deliveryItems.value.length, detail: deliveryItems.value.length ? `已同步 ${deliveryItems.value.length} 个 PR` : '尚未接入 PR' },
  { label: '交付已审查', value: tasks.value.length, detail: tasks.value.length ? `已建立 ${tasks.value.length} 个审查任务` : '尚未建立审查任务' },
  { label: '等待人工确认', value: reports.value.length, detail: reports.value.length ? `${reports.value.length} 份报告待确认` : '当前没有待确认报告' },
  { label: '交付已留档', value: records.value.length, detail: records.value.length ? `已保留 ${records.value.length} 条记录` : '尚未形成留档记录' },
])

function formatDate(value: string | null) {
  return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'
}

function planningLabel(value: string) {
  return ({ OPEN: '未开始', IN_PROGRESS: '进行中', DECLARED_DONE: '已声明完成', CANCELLED: '已取消' } as Record<string, string>)[value] ?? value
}

function verificationLabel(value: string) {
  return ({ NOT_ASSESSED: '尚未审查', PARTIALLY_SUPPORTED: '部分有依据', CONFIRMED: '已确认', CONFLICT: '需要核对', INSUFFICIENT_EVIDENCE: '依据不足' } as Record<string, string>)[value] ?? value
}

async function loadDashboard() {
  const projectId = selectedProjectId.value
  if (!projectId) {
    deliveryItems.value = []; tasks.value = []; reports.value = []; records.value = []
    return
  }
  busy.value = true
  message.value = '正在读取当前项目的事项、审查和留档记录。'
  try {
    const [items, taskList, reportList, recordList] = await Promise.all([
      apiRequest<DeliveryItem[]>(`/projects/${projectId}/delivery-items`, { headers: projectHeaders() }),
      apiRequest<VerificationTask[]>(`/projects/${projectId}/verification-tasks`, { headers: projectHeaders() }),
      apiRequest<ProjectReport[]>(`/projects/${projectId}/report-versions?status_filter=SUBMITTED`, { headers: projectHeaders() }),
      apiRequest<PublishedRecord[]>(`/projects/${projectId}/published-records`, { headers: projectHeaders() }),
    ])
    if (projectId !== selectedProjectId.value) return
    deliveryItems.value = items; tasks.value = taskList; reports.value = reportList; records.value = recordList
    message.value = '这里只呈现已接入的事项、已建立的审查和已留档的交付；它不把外部计划当作完成结论。'
  } catch (error) {
    if (projectId !== selectedProjectId.value) return
    message.value = error instanceof Error ? error.message : '项目工作台加载失败'
  } finally {
    if (projectId === selectedProjectId.value) busy.value = false
  }
}

watch(selectedProjectId, () => { void loadDashboard() }, { immediate: true })
</script>

<template>
  <section class="page page-home">
    <header class="page-heading">
      <div>
        <h1>工作台</h1>
        <p v-if="selectedProject">{{ selectedProject.description || '从一次 Pull Request 出发，审查每次代码交付是否有可追溯的实现依据。' }}</p>
        <p v-else>帮助开发者审查需求进度和交付依据，而不只是汇报一个完成状态。</p>
      </div>
    </header>

    <section v-if="!selectedProject" class="home-hero home-empty-hero">
      <div class="home-hero-copy">
        <h2>审清楚每一次需求交付</h2>
        <p>连接 Pull Request、可选资料和实际代码变更，帮助开发者判断本次交付做了什么、有什么风险、还缺什么。</p>
      </div>
      <div class="home-empty-action"><p>填写一次 GitHub 仓库地址，即可同步 Pull Request 并登记只读代码源。</p><button class="primary-button" type="button" @click="openProjectCreate">创建并接入项目</button></div>
    </section>

    <template v-else>
      <section class="home-hero">
        <div class="home-hero-copy">
          <h2>审清楚每一次需求交付</h2>
          <p>从一个 Pull Request 的真实 Diff 开始，辅助开发者定位代码问题、补充必要资料并保留可回放的审查记录。</p>
          <div class="home-workflow" aria-label="审查工作方式">
            <span>Pull Request</span><i aria-hidden="true">→</i><span>冻结 Diff</span><i aria-hidden="true">→</i><span>代码审查</span><i aria-hidden="true">→</i><span>人工确认</span>
          </div>
        </div>
        <RouterLink class="hero-action" :to="primaryAction.to">
          <span>{{ primaryAction.title }}</span>
          <strong>{{ primaryAction.label }}</strong>
          <small>{{ primaryAction.description }}</small>
        </RouterLink>
      </section>

      <p v-if="message" class="home-data-note" :class="{ loading: busy }">{{ message }}</p>

      <div class="home-priority-grid">
        <section class="home-priority-card">
          <div class="home-card-heading">
            <div><h2>当前需要处理</h2><p>从下一项真实工作开始，不显示推测性的完成率。</p></div>
            <RouterLink :to="primaryAction.to">{{ primaryAction.label }}</RouterLink>
          </div>
          <div class="home-priority-main">
            <span class="home-priority-marker" aria-hidden="true"></span>
            <div><strong>{{ primaryAction.title }}</strong><p>{{ primaryAction.description }}</p></div>
          </div>
          <RouterLink class="home-priority-link" :to="primaryAction.to">{{ primaryAction.label }} <span aria-hidden="true">→</span></RouterLink>
        </section>

        <section class="home-recent-card">
          <div class="home-card-heading"><div><h2>最近审查</h2><p>已接入 Pull Request 的当前状态</p></div><RouterLink to="/tasks">全部 PR</RouterLink></div>
          <div v-if="recentWork.length" class="home-recent-list">
            <RouterLink v-for="item in recentWork" :key="item.id" :to="taskByItemId.get(item.id) ? `/tasks/${taskByItemId.get(item.id)?.id}/notebook` : '/tasks'">
              <div><strong>{{ item.title }}</strong><small>{{ item.external_key }}</small></div>
              <span>{{ verificationLabel(item.verification_status) }}</span>
            </RouterLink>
          </div>
          <p v-else class="home-empty-copy">还没有接入 Pull Request。先连接 GitHub 仓库，才能开始代码审查。</p>
        </section>
      </div>

      <section class="home-progress-card">
        <div class="home-card-heading"><div><h2>项目工作进展</h2><p>用于定位工作处在什么环节，不作为项目完成度结论。</p></div></div>
        <div class="home-progress-stages">
          <div v-for="stage in progressStages" :key="stage.label">
            <span>{{ stage.label }}</span><strong>{{ stage.value }}</strong><small>{{ stage.detail }}</small>
          </div>
        </div>
      </section>

      <section class="home-records-card">
        <div class="home-card-heading"><div><h2>已留档的交付</h2><p>通过人工确认后形成的不可变记录。</p></div><RouterLink to="/deliveries">查看全部记录</RouterLink></div>
        <div v-if="records.length" class="data-table delivery-table home-record-table">
          <div class="table-row table-header"><span>记录编号</span><span>关联工作</span><span>确认人</span><span>留档时间</span></div>
          <RouterLink v-for="record in records.slice(0, 6)" :key="record.id" class="table-row table-button" :to="`/deliveries/${record.id}`"><strong>{{ record.record_no }}</strong><span>{{ record.task_title }}</span><span>{{ record.approval_by_name || '—' }}</span><time>{{ formatDate(record.published_at) }}</time></RouterLink>
        </div>
        <p v-else class="home-empty-copy home-record-empty">暂无已留档的交付。完成审查并经过不同成员确认后，记录会保留在这里。</p>
      </section>
    </template>
  </section>
</template>
