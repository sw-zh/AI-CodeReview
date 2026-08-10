<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface ScanArtifact { id: string; target_sha: string; scan_type: string; scanner_name: string; scanner_version: string; rule_set_version: string; finding_count: number; created_at: string }
interface SecurityBaseline { id: string; target_sha: string; snapshot_hash: string; summary: Record<string, unknown>; coverage: Record<string, unknown>; created_at: string }
interface BaselineRecord { id: string; record_no: string; confirmation_reason: string; confirmed_at: string }

const artifacts = ref<ScanArtifact[]>([])
const baselines = ref<SecurityBaseline[]>([])
const records = ref<BaselineRecord[]>([])
const busy = ref(false)
const message = ref('安全基线仅汇总指定 SHA 的已导入扫描结果，并明确其覆盖边界。')
const latest = computed(() => baselines.value[0] ?? null)

function formatDate(value: string) { return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) }
function serialise(value: unknown) { return JSON.stringify(value ?? {}, null, 2) }

async function load() {
  const projectId = selectedProjectId.value
  if (!projectId) { artifacts.value = []; baselines.value = []; records.value = []; return }
  busy.value = true
  try {
    const [artifactList, baselineList, recordList] = await Promise.all([
      apiRequest<ScanArtifact[]>(`/projects/${projectId}/security-scan-artifacts`, { headers: projectHeaders() }),
      apiRequest<SecurityBaseline[]>(`/projects/${projectId}/security-baselines`, { headers: projectHeaders() }),
      apiRequest<BaselineRecord[]>(`/projects/${projectId}/security-baseline-records`, { headers: projectHeaders() }),
    ])
    if (projectId !== selectedProjectId.value) return
    artifacts.value = artifactList; baselines.value = baselineList; records.value = recordList
    message.value = baselineList.length ? '风险是否关闭仍需新的扫描结果或人工确认；“已声明修复”不会自动变为已解决。' : '尚未固化安全基线。可先导入带扫描器、规则版本和目标 SHA 的结果。'
  } catch (error) { if (projectId === selectedProjectId.value) message.value = error instanceof Error ? error.message : '安全基线加载失败' } finally { if (projectId === selectedProjectId.value) busy.value = false }
}

watch(selectedProjectId, () => { void load() }, { immediate: true })
</script>

<template>
  <section class="page page-security"><header class="page-heading"><div><h1>安全与质量</h1><p v-if="selectedProject">{{ selectedProject.name }}：展示已导入扫描与其对应的安全基线，不声称全项目绝对安全。</p><p v-else>请先选择项目。</p></div></header><p class="page-context-note">{{ message }}</p>
    <template v-if="selectedProject"><section v-if="latest" class="surface status-summary"><div class="surface-heading"><h2>最新安全基线</h2><time>{{ formatDate(latest.created_at) }}</time></div><div class="state-brief-grid"><div><strong>目标 SHA</strong><p>{{ latest.target_sha }}</p></div><div><strong>基线哈希</strong><p>{{ latest.snapshot_hash }}</p></div><div><strong>覆盖说明</strong><p>只对应基线中引用的扫描工件、扫描器版本与规则版本。</p></div></div><div class="security-json"><section><h3>风险汇总</h3><pre>{{ serialise(latest.summary) }}</pre></section><section><h3>覆盖范围与缺口</h3><pre>{{ serialise(latest.coverage) }}</pre></section></div></section>
      <section class="surface"><div class="surface-heading"><h2>导入的扫描工件</h2></div><div v-if="artifacts.length" class="data-table"><div class="table-row table-header"><span>扫描类型</span><span>扫描器 / 规则</span><span>目标 SHA</span><span>发现数</span><span>导入时间</span></div><div v-for="artifact in artifacts" :key="artifact.id" class="table-row"><strong>{{ artifact.scan_type }}</strong><span>{{ artifact.scanner_name }} {{ artifact.scanner_version }} · {{ artifact.rule_set_version }}</span><span>{{ artifact.target_sha.slice(0, 12) }}…</span><span>{{ artifact.finding_count }}</span><time>{{ formatDate(artifact.created_at) }}</time></div></div><p v-else class="empty-row">暂无导入的扫描工件。</p></section>
      <section class="surface"><div class="surface-heading"><h2>已确认的基线记录</h2></div><div v-if="records.length" class="data-table"><div class="table-row table-header"><span>记录号</span><span>确认说明</span><span>确认时间</span></div><div v-for="record in records" :key="record.id" class="table-row"><strong>{{ record.record_no }}</strong><span>{{ record.confirmation_reason }}</span><time>{{ formatDate(record.confirmed_at) }}</time></div></div><p v-else class="empty-row">暂无已确认的安全基线记录。</p></section>
    </template>
  </section>
</template>
