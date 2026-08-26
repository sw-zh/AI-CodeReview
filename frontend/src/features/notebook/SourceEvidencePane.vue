<script setup lang="ts">
import type { EvidenceReference } from '../../types/workbench'

type GitFile = { path: string; old_path?: string | null; edit_type: string; additions: number; deletions: number; binary: boolean; hunks: Array<{ header: string; payload: string }> }
type GitDiff = { files: GitFile[]; coverage: Record<string, unknown> }
type Challenge = { state: string; verdict: string | null; reason: string | null; evidenceIds: string[] }
type CodeReview = { findings: Array<{ id: string; evidenceId: string; severity: string; findingKind: string; title: string; problem: string; triggerScenario: string; recommendation: string; confidence: number; challenge: Challenge }>; coverage: Array<{ scopeKind: string; state: string; reasonCode: string | null; details: Record<string, unknown> }> }

const props = defineProps<{ evidence: EvidenceReference[]; snapshotLabel?: string | null; live?: boolean; gitDiff?: GitDiff | null; codeReview?: CodeReview | null; selectedFilePath?: string | null }>()
const emit = defineEmits<{ selectFile: [path: string] }>()

function challengeLabel(challenge: Challenge) {
  if (challenge.verdict === 'SUPPORTED') return '证据支持'
  if (challenge.verdict === 'UNSUPPORTED') return '当前证据不足'
  if (challenge.verdict === 'NEEDS_HUMAN') return '需人工确认'
  return '复核未完成'
}

function nextStep(reasonCode: string | null) {
  if (!reasonCode) return ''
  if (reasonCode === 'MODEL_NOT_CONFIGURED') return '下一步：配置 DeepSeek 后重新发起本次核验。'
  if (reasonCode.includes('BUDGET')) return '下一步：缩小 Diff 范围或减少资料后重新核验。'
  if (reasonCode.includes('ARTIFACT')) return '下一步：重新冻结同一来源仓库的 Diff。'
  return `下一步：处理 ${reasonCode} 后重新发起核验。`
}

function editLabel(editType: string) {
  return ({ ADDED: '新增', MODIFIED: '修改', DELETED: '删除', RENAMED: '重命名' } as Record<string, string>)[editType] ?? editType
}

function editMark(editType: string) {
  return ({ ADDED: 'A', MODIFIED: 'M', DELETED: 'D', RENAMED: 'R' } as Record<string, string>)[editType] ?? '•'
}

function selectFile(file: GitFile) { emit('selectFile', file.path) }
</script>

<template>
  <aside class="notebook-pane notebook-sources">
    <header class="notebook-pane-header source-pane-header"><div><h2>审查来源</h2><p>{{ live ? '本轮冻结的代码变更与引用' : '尚未形成真实运行' }}</p></div><span v-if="gitDiff" class="source-file-count">{{ gitDiff.files.length }}</span></header>
    <section class="source-input-overview"><div><span>输入快照</span><strong :title="snapshotLabel ?? ''">{{ snapshotLabel ? `${snapshotLabel.slice(0, 12)}…` : '尚未创建' }}</strong></div><div><span>变更文件</span><strong>{{ gitDiff?.files.length ?? 0 }}</strong></div><div><span>已引用</span><strong>{{ evidence.length }}</strong></div></section>
    <section v-if="gitDiff" class="source-file-section"><header><div><h3>代码变更</h3><p>选择文件，在中间查看 Diff</p></div><span>{{ gitDiff.files.length }} 个文件</span></header><div class="source-file-list"><button v-for="file in gitDiff.files" :key="`${file.path}-${file.edit_type}`" :class="['source-file-item', { selected: props.selectedFilePath === file.path }]" type="button" @click="selectFile(file)"><span :class="['source-file-mark', file.edit_type.toLowerCase()]">{{ editMark(file.edit_type) }}</span><span class="source-file-copy"><strong :title="file.path">{{ file.path }}</strong><small>{{ editLabel(file.edit_type) }} · +{{ file.additions }} / -{{ file.deletions }}<template v-if="file.binary"> · 二进制文件</template></small></span></button></div></section>
    <details v-if="codeReview" class="source-check-details"><summary><span>代码检查</span><strong>{{ codeReview.findings.length }} 项 Finding</strong></summary><p>代码审查、反证复核与范围说明均只读取本次冻结输入。</p><article v-for="finding in codeReview.findings" :key="finding.id" class="source-item"><div><span class="source-kind">{{ finding.severity }}</span><strong>{{ finding.title }}</strong><small>{{ finding.findingKind }} · 置信度 {{ Math.round(finding.confidence * 100) }}% · 复核：{{ challengeLabel(finding.challenge) }}</small><p>{{ finding.problem }}</p><p>触发：{{ finding.triggerScenario }}</p><p>建议：{{ finding.recommendation }}</p><p v-if="finding.challenge.reason">复核依据：{{ finding.challenge.reason }}</p></div></article><small v-for="coverage in codeReview.coverage" :key="coverage.scopeKind">{{ coverage.scopeKind }} · {{ coverage.state }}<template v-if="coverage.reasonCode"> · {{ coverage.reasonCode }}</template><template v-if="nextStep(coverage.reasonCode)"> · {{ nextStep(coverage.reasonCode) }}</template></small></details>
    <section v-if="evidence.length" class="source-citation-section"><header><h3>引用证据</h3><span>{{ evidence.length }}</span></header><div class="source-list"><article v-for="item in evidence" :key="item.id" class="source-item"><div><span class="source-kind">{{ item.kind }}</span><strong>{{ item.title }}</strong><small>{{ item.locator }}</small></div><span :class="['source-state', item.state === '待补充' ? 'pending' : 'cited']">{{ item.state }}</span></article></div></section>
  </aside>
</template>
