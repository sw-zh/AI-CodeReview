<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import ReviewDetailPane from '../features/notebook/ReviewDetailPane.vue'
import SourceEvidencePane from '../features/notebook/SourceEvidencePane.vue'
import VerificationPane from '../features/notebook/VerificationPane.vue'
import { apiRequest, projectHeaders, selectedProjectId } from '../features/projects/project-context'
import type { EvidenceReference, VerificationConclusion } from '../types/workbench'

type AnalysisRun = { id: string; snapshot_id: string; run_status: string }
type RunOrchestration = {
  contentHash: string
  template: { name: string; version: number }
  nodes: Array<{
    capabilityKey: string
    capabilityName: string
    capabilityVersion: number
    displayOrder: number
    locked: boolean
    tools: Array<{ key: string }>
  }>
}
type ResultEvidence = { id: string; sourceType: string; excerpt: string; locator: Record<string, unknown>; precision: string }
type AnalysisResult = {
  id: string
  claim_text: string
  status: string
  reason: string
  requires_human_confirmation: boolean
  evidence: ResultEvidence[]
  risks: Array<{ severity: string }>
}
type TaskContext = { id: string; title: string; cycle_status: string; formal_snapshot_hash: string | null }

const route = useRoute()
const selectedId = ref('pending-result')
const task = ref<TaskContext | null>(null)
const liveRun = ref<AnalysisRun | null>(null)
const liveOrchestration = ref<RunOrchestration | null>(null)
const liveResults = ref<AnalysisResult[]>([])
const liveLoadError = ref('')

function mapStatus(status: string): VerificationConclusion['status'] {
  if (status === 'CONFIRMED') return '已确认'
  if (status === 'PARTIALLY_SUPPORTED') return '部分支持'
  if (status === 'INSUFFICIENT_EVIDENCE') return '证据不足'
  return '待人工确认'
}

function mapEvidenceKind(sourceType: string): EvidenceReference['kind'] {
  if (sourceType === 'CODE') return '代码'
  if (sourceType === 'TEST' || sourceType === 'BUILD') return '测试'
  if (sourceType === 'MANUAL' || sourceType === 'TOOL') return '人工补证'
  return '需求'
}

function locatorLabel(locator: Record<string, unknown>): string {
  return String(locator.path ?? locator.hunk ?? locator.toolKey ?? locator.sourceRevisionId ?? '冻结快照证据')
}

const liveEvidence = computed<EvidenceReference[]>(() => {
  const byId = new Map<string, EvidenceReference>()
  for (const result of liveResults.value) {
    for (const item of result.evidence) {
      if (!byId.has(item.id)) {
        byId.set(item.id, { id: item.id, kind: mapEvidenceKind(item.sourceType), title: item.sourceType, locator: locatorLabel(item.locator), excerpt: item.excerpt, state: '已引用' })
      }
    }
  }
  return [...byId.values()]
})

const liveConclusions = computed<VerificationConclusion[]>(() => liveResults.value.map((item) => ({
  id: item.id,
  requirement: item.claim_text,
  status: mapStatus(item.status),
  summary: item.reason,
  needsHumanDecision: item.requires_human_confirmation,
  risk: item.risks.some((risk) => risk.severity === 'HIGH') ? 'P0' : item.risks.length ? 'P1' : null,
  evidenceIds: item.evidence.map((evidence) => evidence.id),
})))

const displayedEvidence = computed(() => liveEvidence.value)
const displayedConclusions = computed<VerificationConclusion[]>(() => {
  if (liveRun.value && liveConclusions.value.length) return liveConclusions.value
  return [{ id: 'pending-result', requirement: task.value?.title ?? '尚未加载核验任务', status: '待人工确认', summary: task.value ? `当前轮次状态为 ${task.value.cycle_status}，尚未产生可展示的核验结论。先补齐目标资料与冻结 Git Diff，再运行固定双核。` : '请选择项目并从研发事项进入对应的核验任务。', needsHumanDecision: true, risk: null, evidenceIds: [] }]
})
const selectedConclusion = computed(() => displayedConclusions.value.find((item) => item.id === selectedId.value) ?? displayedConclusions.value[0])

function isUuid(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

async function loadLiveOrchestration(taskId: unknown) {
  liveRun.value = null
  liveOrchestration.value = null
  liveResults.value = []
  liveLoadError.value = ''
  task.value = null
  const projectId = selectedProjectId.value
  if (!projectId || !isUuid(taskId)) return
  try {
    const tasks = await apiRequest<TaskContext[]>(`/projects/${projectId}/verification-tasks`, { headers: projectHeaders() })
    const matchedTask = tasks.find((item) => item.id === taskId)
    if (!matchedTask) throw new Error('该核验任务不属于当前项目，或已无权访问。')
    task.value = matchedTask
    try {
      const run = await apiRequest<AnalysisRun>(`/verification-tasks/${taskId}/latest-analysis-run`, { headers: projectHeaders() })
      liveRun.value = run
      liveOrchestration.value = await apiRequest<RunOrchestration>(`/analysis-runs/${run.id}/orchestration`, { headers: projectHeaders() })
      liveResults.value = await apiRequest<AnalysisResult[]>(`/analysis-runs/${run.id}/results`, { headers: projectHeaders() })
      selectedId.value = liveResults.value[0]?.id ?? 'pending-result'
    } catch (error) {
      liveLoadError.value = error instanceof Error ? `尚未加载到真实运行：${error.message}` : '尚未加载到真实运行。'
    }
  } catch (error) {
    liveLoadError.value = error instanceof Error ? error.message : '核验任务加载失败'
  }
}

watch([selectedProjectId, () => route.params.taskId], () => { void loadLiveOrchestration(route.params.taskId) }, { immediate: true })
</script>

<template>
  <section class="notebook-page">
    <header class="notebook-topbar">
      <RouterLink to="/tasks">返回任务中心</RouterLink>
      <div><h1>{{ task?.title ?? '核验任务' }}</h1><p v-if="liveRun">真实运行 {{ liveRun.id }} · 输入快照 {{ liveRun.snapshot_id }}</p><p v-else-if="task">当前轮次 {{ task.cycle_status }} · 尚未形成可展示的真实运行</p><p v-else>读取当前项目中的核验任务。</p></div>
      <span class="notebook-status">{{ liveRun?.run_status ?? task?.cycle_status ?? '未加载' }}</span>
    </header>
    <p v-if="liveLoadError" class="notebook-live-note">真实运行未加载：{{ liveLoadError }}</p>
    <main class="notebook-grid"><SourceEvidencePane :evidence="displayedEvidence" :snapshot-label="liveRun?.snapshot_id ?? task?.formal_snapshot_hash" :live="Boolean(liveRun)" /><VerificationPane :conclusions="displayedConclusions" :selected-id="selectedId" :live="Boolean(liveRun)" @select="selectedId = $event" /><ReviewDetailPane :conclusion="selectedConclusion" :evidence="displayedEvidence" :orchestration="liveOrchestration" :run-status="liveRun?.run_status" :run-snapshot-id="liveRun?.snapshot_id" /></main>
  </section>
</template>
