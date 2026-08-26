<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { apiRequest, projectHeaders, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface ProjectReport { id: string; task_title: string; requirement_key: string; sequence_no: number; status: string; snapshot_hash: string; content_hash: string; editorial_note: string; submitted_by_name: string | null; submitted_at: string | null; latest_approval_action: string | null; latest_approval_reason: string | null; latest_approval_at: string | null }
const route = useRoute()
const report = ref<ProjectReport | null>(null)
const reason = ref('')
const busy = ref(false)
const message = ref('读取审批所绑定的报告版本与输入快照。')

function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—' }
function statusLabel(value: string) { return ({ SUBMITTED: '待审批', APPROVED: '已批准', PUBLISHED: '已固化', REJECTED: '已驳回', CHANGES_REQUESTED: '已要求补证', DRAFT: '草稿' } as Record<string, string>)[value] ?? value }

async function load() {
  const projectId = selectedProjectId.value
  const reportId = String(route.params.approvalId ?? '')
  if (!projectId || !reportId) { report.value = null; return }
  busy.value = true
  try {
    report.value = await apiRequest<ProjectReport>(`/projects/${projectId}/report-versions/${reportId}`, { headers: projectHeaders() })
    message.value = '审批只能改变当前报告版本的状态；它不会修改项目计划状态，也不会替代对冻结 Diff 的核验。'
  } catch (error) { report.value = null; message.value = error instanceof Error ? error.message : '审批详情加载失败' } finally { busy.value = false }
}

async function act(action: 'approve' | 'request-changes' | 'reject') {
  if (!report.value || !reason.value.trim()) { message.value = '请先填写审批依据。'; return }
  busy.value = true
  try {
    await apiRequest(`/report-versions/${report.value.id}/${action}`, { method: 'POST', headers: projectHeaders(true), body: JSON.stringify({ reason: reason.value.trim() }) })
    reason.value = ''
    message.value = '审批动作已记录并绑定当前报告哈希与输入快照。'
    await load()
  } catch (error) { message.value = error instanceof Error ? error.message : '审批动作失败' } finally { busy.value = false }
}

async function publishRecord() {
  if (!report.value || report.value.status !== 'APPROVED') return
  busy.value = true
  try {
    const record = await apiRequest<{ recordNo: string }>(`/report-versions/${report.value.id}/publish`, { method: 'POST', headers: projectHeaders(true) })
    message.value = `已固化正式记录 ${record.recordNo}。该轮次和报告版本现为不可写历史。`
    await load()
  } catch (error) { message.value = error instanceof Error ? error.message : '正式记录固化失败' } finally { busy.value = false }
}

watch([selectedProjectId, () => route.params.approvalId], () => { void load() }, { immediate: true })
</script>

<template>
  <section class="page page-detail"><RouterLink class="back-link" to="/approvals">返回待审批队列</RouterLink><header class="page-heading detail-heading"><div><h1>审批详情</h1><p v-if="report">{{ report.task_title }} · 报告版本 v{{ report.sequence_no }}</p><p v-else>读取当前项目中的报告版本。</p></div><span v-if="report" class="status-mark attention">{{ statusLabel(report.status) }}</span></header><p class="page-context-note">{{ message }}</p>
    <section v-if="report && selectedProject" class="surface formal-document"><div class="record-meta"><span>需求标识：{{ report.requirement_key }}</span><span>提交人：{{ report.submitted_by_name || '—' }}</span><span>提交时间：{{ formatDate(report.submitted_at) }}</span></div><div class="document-section"><h2>报告与输入绑定</h2><dl class="run-details"><div><dt>报告内容哈希</dt><dd>{{ report.content_hash }}</dd></div><div><dt>输入快照哈希</dt><dd>{{ report.snapshot_hash }}</dd></div><div><dt>上一审批动作</dt><dd>{{ report.latest_approval_action || '尚无' }}</dd></div></dl><p v-if="report.editorial_note">提交说明：{{ report.editorial_note }}</p></div><div class="document-section"><h2>审批依据</h2><label class="form-label" for="approval-comment">说明你依据哪些已冻结事实作出决定</label><textarea id="approval-comment" v-model="reason" :disabled="busy || report.status !== 'SUBMITTED'" placeholder="例如：引用完整，接受条件与 Diff 证据一致。"></textarea><p v-if="report.latest_approval_reason" class="history-note">最近审批说明：{{ report.latest_approval_reason }}</p></div><div class="document-actions"><div><strong>审批不会替代交付核验</strong><p>要求补证会复制为新的草稿；批准后仅管理员可固化正式记录。</p></div><div class="action-buttons"><button type="button" :disabled="busy || report.status !== 'SUBMITTED'" @click="act('request-changes')">要求补证</button><button type="button" :disabled="busy || report.status !== 'SUBMITTED'" @click="act('reject')">驳回</button><button class="primary-button" type="button" :disabled="busy || report.status !== 'SUBMITTED'" @click="act('approve')">批准</button><button v-if="report.status === 'APPROVED'" class="primary-button" type="button" :disabled="busy" @click="publishRecord">管理员固化正式记录</button></div></div></section>
  </section>
</template>
