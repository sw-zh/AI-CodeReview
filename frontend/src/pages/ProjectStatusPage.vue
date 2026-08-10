<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface HealthSnapshot { id: string; as_of: string; snapshot_hash: string; scope: Record<string, unknown>; summary: Record<string, unknown>; coverage: { dataGaps?: string[] } }
interface SummaryDraft { id: string; period_type: string; title: string; draft_status: string; updated_at: string }
interface SummaryRecord { id: string; record_no: string; confirmation_type: string; published_at: string }

const snapshots = ref<HealthSnapshot[]>([])
const drafts = ref<SummaryDraft[]>([])
const records = ref<SummaryRecord[]>([])
const busy = ref(false)
const message = ref('项目态势从事项、记录和覆盖范围生成，不从 Git 提交数量推断完成度。')
const latest = computed(() => snapshots.value[0] ?? null)

function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function count(value: unknown) { return typeof value === 'number' ? value : '—' }
function mapCount(summary: Record<string, unknown>, key: string) { const value = summary[key]; return value && typeof value === 'object' ? Object.entries(value as Record<string, unknown>) : [] }

async function load() {
  const projectId = selectedProjectId.value
  if (!projectId) { snapshots.value = []; drafts.value = []; records.value = []; return }
  busy.value = true
  try {
    const [health, draftList, recordList] = await Promise.all([
      apiRequest<HealthSnapshot[]>(`/projects/${projectId}/health-snapshots`, { headers: projectHeaders() }),
      apiRequest<SummaryDraft[]>(`/projects/${projectId}/project-summary-drafts`, { headers: projectHeaders() }),
      apiRequest<SummaryRecord[]>(`/projects/${projectId}/project-summary-records`, { headers: projectHeaders() }),
    ])
    if (projectId !== selectedProjectId.value) return
    snapshots.value = health; drafts.value = draftList; records.value = recordList
    message.value = health.length ? '态势快照保留当时纳入的数据、缺口与计算口径；外部声明完成不等于已核验完成。' : '当前项目尚未生成态势快照，因此不会显示虚假的完成率。'
  } catch (error) { if (projectId === selectedProjectId.value) message.value = error instanceof Error ? error.message : '项目态势加载失败' } finally { if (projectId === selectedProjectId.value) busy.value = false }
}

watch(selectedProjectId, () => { void load() }, { immediate: true })
</script>

<template>
  <section class="page page-status"><header class="page-heading"><div><h1>项目态势</h1><p v-if="selectedProject">{{ selectedProject.name }}：把计划、开发活动、核验与正式记录放在同一时点说明。</p><p v-else>请先选择项目。</p></div></header><p class="page-context-note">{{ message }}</p>
    <template v-if="selectedProject && latest"><section class="surface status-summary"><div class="surface-heading"><h2>最新态势快照</h2><time>{{ formatDate(latest.as_of) }}</time></div><div class="state-brief-grid"><div><strong>纳入事项</strong><p>{{ count(latest.summary.plannedItemCount) }} 项未取消的计划事项；已声明完成与已核验确认分别计算。</p></div><div><strong>正式记录覆盖</strong><p>{{ count(latest.summary.formalRecordItemCount) }} 项已有正式记录；{{ count(latest.summary.confirmedChangeLinkedItemCount) }} 项已确认变更归属。</p></div><div><strong>待归属开发活动</strong><p>{{ count((latest.summary.unattributedActivity as Record<string, unknown> | undefined)?.gitSnapshotCount) }} 个冻结 Git 范围尚未归属到事项。</p></div></div><div class="status-breakdown"><section><h3>外部计划状态</h3><p v-for="[status, value] in mapCount(latest.summary, 'planningStatusCounts')" :key="status"><span>{{ status }}</span><strong>{{ value }}</strong></p></section><section><h3>本系统核验状态</h3><p v-for="[status, value] in mapCount(latest.summary, 'verificationStatusCounts')" :key="status"><span>{{ status }}</span><strong>{{ value }}</strong></p></section><section><h3>数据缺口</h3><p v-if="latest.coverage.dataGaps?.length" v-for="gap in latest.coverage.dataGaps" :key="gap">{{ gap }}</p><p v-else>当前快照未记录数据缺口。</p></section></div><p class="immutable-note">快照哈希：{{ latest.snapshot_hash }}。它说明的是此刻已纳入的数据与缺口，不替代任何交付核验结论。</p></section>
      <section class="surface"><div class="surface-heading"><h2>总结草稿与已确认记录</h2></div><div class="data-table"><div class="table-row table-header"><span>类型</span><span>标题或记录号</span><span>状态</span><span>更新时间</span></div><div v-for="draft in drafts" :key="draft.id" class="table-row"><span>{{ draft.period_type }}</span><strong>{{ draft.title }}</strong><span>{{ draft.draft_status }}</span><time>{{ formatDate(draft.updated_at) }}</time></div><div v-for="record in records" :key="record.id" class="table-row"><span>已确认总结</span><strong>{{ record.record_no }}</strong><span>{{ record.confirmation_type }}</span><time>{{ formatDate(record.published_at) }}</time></div></div><p v-if="!drafts.length && !records.length" class="empty-row">暂无项目总结草稿或已确认的总结记录。</p></section>
    </template>
  </section>
</template>
