<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import ReviewDetailPane from '../features/notebook/ReviewDetailPane.vue'
import SourceEvidencePane from '../features/notebook/SourceEvidencePane.vue'
import VerificationPane from '../features/notebook/VerificationPane.vue'
import { notebookConclusions, notebookEvidence } from '../features/workbench/workbench-fixtures'
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

const route = useRoute()
const selectedId = ref(notebookConclusions[0].id)
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

const displayedEvidence = computed(() => liveRun.value ? liveEvidence.value : notebookEvidence)
const displayedConclusions = computed<VerificationConclusion[]>(() => {
  if (!liveRun.value) return notebookConclusions
  return liveConclusions.value.length ? liveConclusions.value : [{ id: 'pending-result', requirement: '核验运行尚未产生结论', status: '待人工确认', summary: '等待运行完成后加载当前输入快照内的核验结果。', needsHumanDecision: true, risk: null, evidenceIds: [] }]
})
const selectedConclusion = computed(() => displayedConclusions.value.find((item) => item.id === selectedId.value) ?? displayedConclusions.value[0])

function isUuid(value: unknown): value is string {
  return typeof value === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value)
}

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { headers: { Authorization: `Bearer ${sessionStorage.getItem('accessToken') ?? ''}` } })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(body.message ?? body.detail?.message ?? `请求失败 (${response.status})`)
  return body as T
}

async function loadLiveOrchestration(taskId: unknown) {
  liveRun.value = null
  liveOrchestration.value = null
  liveResults.value = []
  liveLoadError.value = ''
  if (!isUuid(taskId)) return
  try {
    const run = await request<AnalysisRun>(`/verification-tasks/${taskId}/latest-analysis-run`)
    liveRun.value = run
    liveOrchestration.value = await request<RunOrchestration>(`/analysis-runs/${run.id}/orchestration`)
    liveResults.value = await request<AnalysisResult[]>(`/analysis-runs/${run.id}/results`)
    selectedId.value = liveResults.value[0]?.id ?? 'pending-result'
  } catch (error) {
    liveLoadError.value = error instanceof Error ? error.message : '真实运行编排加载失败'
  }
}

onMounted(() => loadLiveOrchestration(route.params.taskId))
watch(() => route.params.taskId, (taskId) => loadLiveOrchestration(taskId))
</script>

<template>
  <section class="notebook-page">
    <header class="notebook-topbar">
      <RouterLink to="/tasks">返回任务中心</RouterLink>
      <div><h1>支付流程重构核验</h1><p v-if="liveRun">真实运行 {{ liveRun.id }} · 输入快照 {{ liveRun.snapshot_id }}</p><p v-else>任务 TASK-5240 · 输入快照 snap_a1b2c3d4</p></div>
      <span class="notebook-status">{{ liveRun?.run_status ?? '待人工确认' }}</span>
    </header>
    <p v-if="liveLoadError" class="notebook-live-note">真实运行未加载：{{ liveLoadError }}</p>
    <main class="notebook-grid"><SourceEvidencePane :evidence="displayedEvidence" :snapshot-label="liveRun?.snapshot_id" :live="Boolean(liveRun)" /><VerificationPane :conclusions="displayedConclusions" :selected-id="selectedId" :live="Boolean(liveRun)" @select="selectedId = $event" /><ReviewDetailPane :conclusion="selectedConclusion" :evidence="displayedEvidence" :orchestration="liveOrchestration" :run-status="liveRun?.run_status" :run-snapshot-id="liveRun?.snapshot_id" /></main>
  </section>
</template>
