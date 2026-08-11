<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface ScanArtifact { id: string; repository_id: string; target_sha: string; scan_type: string; scanner_name: string; scanner_version: string; rule_set_version: string; coverage: Record<string, unknown>; content_hash: string; finding_count: number; created_at: string }
interface SecurityBaseline { id: string; target_sha: string; snapshot_hash: string; summary: Record<string, unknown>; coverage: Record<string, unknown>; created_at: string }
interface BaselineRecord { id: string; record_no: string; confirmation_reason: string; confirmed_at: string }
interface SecurityExplanation { scope: Record<string, unknown>; summary: Record<string, unknown>; observations: string[]; limitations: string[] }
interface QualityTrendPoint { artifact_id: string; target_sha: string; created_at: string; content_hash: string; finding_count: number; severity_counts: Record<string, number>; status_counts: Record<string, number>; coverage: Record<string, unknown> }
interface QualityTrendSeries { series_key: string; repository_id: string; scan_type: string; scanner_name: string; scanner_version: string; rule_set_version: string; points: QualityTrendPoint[] }
interface QualityTrend { series: QualityTrendSeries[]; limitations: string[] }

const artifacts = ref<ScanArtifact[]>([])
const baselines = ref<SecurityBaseline[]>([])
const records = ref<BaselineRecord[]>([])
const qualityTrend = ref<QualityTrend>({ series: [], limitations: [] })
const selectedArtifact = ref<ScanArtifact | null>(null)
const explanation = ref<SecurityExplanation | null>(null)
const busy = ref(false)
const message = ref('安全基线仅汇总指定 SHA 的已导入扫描结果，并明确其覆盖边界。')
const latest = computed(() => baselines.value[0] ?? null)

function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function serialise(value: unknown) { return JSON.stringify(value ?? {}, null, 2) }

async function load() {
  const projectId = selectedProjectId.value
  if (!projectId) { artifacts.value = []; baselines.value = []; records.value = []; qualityTrend.value = { series: [], limitations: [] }; selectedArtifact.value = null; explanation.value = null; return }
  busy.value = true
  try {
    const [artifactList, baselineList, recordList, trend] = await Promise.all([
      apiRequest<ScanArtifact[]>(`/projects/${projectId}/security-scan-artifacts`, { headers: projectHeaders() }),
      apiRequest<SecurityBaseline[]>(`/projects/${projectId}/security-baselines`, { headers: projectHeaders() }),
      apiRequest<BaselineRecord[]>(`/projects/${projectId}/security-baseline-records`, { headers: projectHeaders() }),
      apiRequest<QualityTrend>(`/projects/${projectId}/quality-trend`, { headers: projectHeaders() }),
    ])
    if (projectId !== selectedProjectId.value) return
    artifacts.value = artifactList; baselines.value = baselineList; records.value = recordList; qualityTrend.value = trend
    message.value = baselineList.length ? '风险是否关闭仍需新的扫描结果或人工确认；“已声明修复”不会自动变为已解决。' : '尚未固化安全基线。可先导入带扫描器、规则版本和目标 SHA 的结果。'
  } catch (error) { if (projectId === selectedProjectId.value) message.value = error instanceof Error ? error.message : '安全基线加载失败' } finally { if (projectId === selectedProjectId.value) busy.value = false }
}

async function showExplanation(artifact: ScanArtifact) {
  const projectId = selectedProjectId.value
  if (!projectId) return
  selectedArtifact.value = artifact
  explanation.value = null
  busy.value = true
  try {
    explanation.value = await apiRequest<SecurityExplanation>(`/projects/${projectId}/security-scan-artifacts/${artifact.id}/explanation`, { headers: projectHeaders() })
  } catch (error) {
    message.value = error instanceof Error ? error.message : '安全解释加载失败'
  } finally { busy.value = false }
}

function closeExplanation() { selectedArtifact.value = null; explanation.value = null }

watch(selectedProjectId, () => { void load() }, { immediate: true })
</script>

<template>
  <section class="page page-security"><header class="page-heading"><div><h1>安全与质量</h1><p v-if="selectedProject">{{ selectedProject.name }}：解释已导入扫描事实与可比序列，不声称全项目绝对安全。</p><p v-else>请先选择项目。</p></div></header><p class="page-context-note">{{ message }}</p>
    <template v-if="selectedProject"><section v-if="latest" class="surface status-summary"><div class="surface-heading"><h2>最新安全基线</h2><time>{{ formatDate(latest.created_at) }}</time></div><div class="state-brief-grid"><div><strong>目标 SHA</strong><p>{{ latest.target_sha }}</p></div><div><strong>基线哈希</strong><p>{{ latest.snapshot_hash }}</p></div><div><strong>覆盖说明</strong><p>只对应基线中引用的扫描工件、扫描器版本与规则版本。</p></div></div><div class="security-json"><section><h3>风险汇总</h3><pre>{{ serialise(latest.summary) }}</pre></section><section><h3>覆盖范围与缺口</h3><pre>{{ serialise(latest.coverage) }}</pre></section></div></section>
      <section v-if="selectedArtifact" class="surface security-explanation"><div class="surface-heading"><div><h2>安全解释</h2><p>{{ selectedArtifact.scan_type }} · {{ selectedArtifact.target_sha.slice(0, 12) }}…</p></div><button type="button" @click="closeExplanation">关闭</button></div><template v-if="explanation"><div class="security-json"><section><h3>已导入事实汇总</h3><pre>{{ serialise(explanation.summary) }}</pre></section><section><h3>范围与定位</h3><pre>{{ serialise(explanation.scope) }}</pre></section></div><div class="security-explanation-copy"><section><h3>解释</h3><p v-for="item in explanation.observations" :key="item">{{ item }}</p></section><section><h3>限制</h3><p v-for="item in explanation.limitations" :key="item">{{ item }}</p></section></div></template><p v-else class="empty-row">正在读取选定扫描工件的已导入事实。</p></section>
      <section class="surface"><div class="surface-heading"><h2>导入的扫描工件</h2></div><div v-if="artifacts.length" class="data-table security-artifact-table"><div class="table-row table-header"><span>扫描类型</span><span>扫描器 / 规则</span><span>目标 SHA</span><span>发现数</span><span>导入时间</span><span>操作</span></div><div v-for="artifact in artifacts" :key="artifact.id" class="table-row"><strong>{{ artifact.scan_type }}</strong><span>{{ artifact.scanner_name }} {{ artifact.scanner_version }} · {{ artifact.rule_set_version }}</span><span>{{ artifact.target_sha.slice(0, 12) }}…</span><span>{{ artifact.finding_count }}</span><time>{{ formatDate(artifact.created_at) }}</time><button type="button" :disabled="busy" @click="showExplanation(artifact)">解释范围</button></div></div><p v-else class="empty-row">暂无导入的扫描工件。</p></section>
      <section class="surface quality-trend"><div class="surface-heading"><h2>质量趋势</h2></div><p class="table-note">只比较同一仓库、扫描类型、扫描器版本与规则版本的导入结果；规则变更会形成新序列。</p><div v-for="series in qualityTrend.series" :key="series.series_key" class="quality-series"><header><strong>{{ series.scan_type }} · {{ series.scanner_name }} {{ series.scanner_version }}</strong><small>规则 {{ series.rule_set_version }} · {{ series.points.length }} 个可比工件</small></header><div v-for="point in series.points" :key="point.artifact_id" class="quality-point"><time>{{ formatDate(point.created_at) }}</time><span>{{ point.target_sha.slice(0, 12) }}…</span><strong>{{ point.finding_count }} 项发现</strong><small>严重度 {{ serialise(point.severity_counts) }}</small></div></div><p v-if="!qualityTrend.series.length" class="empty-row">暂无可比较的导入扫描或 CI 工件。</p><div v-if="qualityTrend.limitations.length" class="quality-limitations"><p v-for="item in qualityTrend.limitations" :key="item">{{ item }}</p></div></section>
      <section class="surface"><div class="surface-heading"><h2>已确认的基线记录</h2></div><div v-if="records.length" class="data-table"><div class="table-row table-header"><span>记录号</span><span>确认说明</span><span>确认时间</span></div><div v-for="record in records" :key="record.id" class="table-row"><strong>{{ record.record_no }}</strong><span>{{ record.confirmation_reason }}</span><time>{{ formatDate(record.confirmed_at) }}</time></div></div><p v-else class="empty-row">暂无已确认的安全基线记录。</p></section>
    </template>
  </section>
</template>
