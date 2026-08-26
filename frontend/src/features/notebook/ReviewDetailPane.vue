<script setup lang="ts">
import { computed, ref } from 'vue'
import type { EvidenceReference, VerificationConclusion } from '../../types/workbench'

type RuntimeNode = {
  capabilityKey: string
  capabilityName: string
  capabilityVersion: number
  displayOrder: number
  locked: boolean
  tools: Array<{ key: string }>
}

type RuntimeOrchestration = {
  contentHash: string
  template: { name: string; version: number }
  nodes: RuntimeNode[]
}

const props = defineProps<{
  conclusion: VerificationConclusion
  evidence: EvidenceReference[]
  orchestration?: RuntimeOrchestration | null
  runStatus?: string | null
  runSnapshotId?: string | null
  hasReport?: boolean
}>()

type DetailTab = '风险' | '引用' | '运行' | '差异' | '报告'

const activeTab = ref<DetailTab>('风险')
const relatedEvidence = computed(() => props.evidence.filter((item) => props.conclusion.evidenceIds.includes(item.id)))
const orchestrationNodes = computed(() => [...(props.orchestration?.nodes ?? [])].sort((left, right) => left.displayOrder - right.displayOrder))
const tabs = computed<DetailTab[]>(() => props.hasReport ? ['风险', '引用', '运行', '差异', '报告'] : ['风险', '引用', '运行', '差异'])
</script>

<template>
  <aside class="notebook-pane notebook-detail">
    <header class="notebook-pane-header"><div><h2>核验详情</h2><p>查看结论依据</p></div></header>
    <div class="detail-tabs"><button v-for="tab in tabs" :key="tab" type="button" :class="{ active: activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></div>
    <section v-if="activeTab === '风险'" class="detail-section"><span class="detail-kicker">当前结论</span><h3>{{ conclusion.requirement }}</h3><p>{{ conclusion.summary }}</p><div v-if="conclusion.risk" class="risk-callout"><strong>{{ conclusion.risk }} 风险</strong><p>风险是否可接受需要回到当前结论的冻结引用和人工审批，不能由此处展示自动裁决。</p></div><p v-else class="quiet-note">当前结论没有记录需要升级的交付风险。</p></section>
    <section v-else-if="activeTab === '引用'" class="detail-section"><span class="detail-kicker">已授权引用</span><article v-for="item in relatedEvidence" :key="item.id" class="citation-item"><span>{{ item.kind }}</span><strong>{{ item.title }}</strong><small>{{ item.locator }}</small><p>{{ item.excerpt }}</p></article><p v-if="!relatedEvidence.length" class="quiet-note">当前没有可展示的冻结证据引用。</p></section>
    <section v-else-if="activeTab === '运行'" class="detail-section">
      <template v-if="orchestration">
        <span class="detail-kicker">冻结的真实运行编排</span>
        <dl class="run-details"><div><dt>运行状态</dt><dd>{{ runStatus }}</dd></div><div><dt>输入快照</dt><dd>{{ runSnapshotId }}</dd></div><div><dt>编排模板</dt><dd>{{ orchestration.template.name }} · v{{ orchestration.template.version }}</dd></div></dl>
        <ol class="run-orchestration-list"><li v-for="node in orchestrationNodes" :key="node.capabilityKey"><span>{{ node.displayOrder }}</span><div><strong>{{ node.capabilityName }}</strong><small>v{{ node.capabilityVersion }}<template v-if="node.tools.length"> · {{ node.tools.map((tool) => tool.key).join('、') }}</template></small></div><em v-if="node.locked">系统锁定</em></li></ol>
        <p class="run-orchestration-note">能力块、Prompt 版本、工具授权和顺序以本次启动时的编排快照为准。</p>
      </template>
      <template v-else>
        <span class="detail-kicker">尚未形成运行快照</span>
        <p class="quiet-note">只有任务形成正式输入快照并启动后，才会展示本次冻结的双核、外围 Agent、Prompt 版本、工具授权和运行顺序。</p>
      </template>
    </section>
    <section v-else-if="activeTab === '差异'" class="detail-section"><span class="detail-kicker">版本差异</span><p v-if="runSnapshotId">当前运行的 Diff 与输入快照绑定。变更输入范围后必须创建新的正式快照。</p><p v-else>尚未形成冻结 Git Diff，因此没有可展示的版本差异。</p></section>
    <section v-else class="detail-section detail-report-tab"><slot name="report" /></section>
  </aside>
</template>
