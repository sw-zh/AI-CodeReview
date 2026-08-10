<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import ReviewDetailPane from '../features/notebook/ReviewDetailPane.vue'
import SourceEvidencePane from '../features/notebook/SourceEvidencePane.vue'
import VerificationPane from '../features/notebook/VerificationPane.vue'
import { notebookConclusions, notebookEvidence } from '../features/workbench/workbench-fixtures'

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

const route = useRoute()
const selectedId = ref(notebookConclusions[0].id)
const selectedConclusion = computed(() => notebookConclusions.find((item) => item.id === selectedId.value) ?? notebookConclusions[0])
const liveRun = ref<AnalysisRun | null>(null)
const liveOrchestration = ref<RunOrchestration | null>(null)
const liveLoadError = ref('')

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
  liveLoadError.value = ''
  if (!isUuid(taskId)) return
  try {
    const run = await request<AnalysisRun>(`/verification-tasks/${taskId}/latest-analysis-run`)
    liveRun.value = run
    liveOrchestration.value = await request<RunOrchestration>(`/analysis-runs/${run.id}/orchestration`)
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
    <main class="notebook-grid"><SourceEvidencePane :evidence="notebookEvidence" /><VerificationPane :conclusions="notebookConclusions" :selected-id="selectedId" @select="selectedId = $event" /><ReviewDetailPane :conclusion="selectedConclusion" :evidence="notebookEvidence" :orchestration="liveOrchestration" :run-status="liveRun?.run_status" :run-snapshot-id="liveRun?.snapshot_id" /></main>
  </section>
</template>
