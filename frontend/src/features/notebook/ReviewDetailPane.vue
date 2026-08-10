<script setup lang="ts">
import { computed, ref } from 'vue'
import type { EvidenceReference, VerificationConclusion } from '../../types/workbench'
const props = defineProps<{ conclusion: VerificationConclusion; evidence: EvidenceReference[] }>()
const activeTab = ref<'风险' | '引用' | '运行' | '差异'>('风险')
const relatedEvidence = computed(() => props.evidence.filter((item) => props.conclusion.evidenceIds.includes(item.id)))
</script>
<template>
  <aside class="notebook-pane notebook-detail"><header class="notebook-pane-header"><div><h2>核验详情</h2><p>查看结论依据</p></div></header><div class="detail-tabs"><button v-for="tab in ['风险', '引用', '运行', '差异'] as const" :key="tab" type="button" :class="{ active: activeTab === tab }" @click="activeTab = tab">{{ tab }}</button></div><section v-if="activeTab === '风险'" class="detail-section"><span class="detail-kicker">当前结论</span><h3>{{ conclusion.requirement }}</h3><p>{{ conclusion.summary }}</p><div v-if="conclusion.risk" class="risk-callout"><strong>{{ conclusion.risk }} 风险</strong><p>建议在补齐跨网关超时场景的验证证据前，保持该结论为待人工确认。</p></div><p v-else class="quiet-note">未发现需要升级的交付风险。</p></section><section v-else-if="activeTab === '引用'" class="detail-section"><span class="detail-kicker">已授权引用</span><article v-for="item in relatedEvidence" :key="item.id" class="citation-item"><span>{{ item.kind }}</span><strong>{{ item.title }}</strong><small>{{ item.locator }}</small><p>{{ item.excerpt }}</p></article></section><section v-else-if="activeTab === '运行'" class="detail-section"><span class="detail-kicker">最新分析运行</span><dl class="run-details"><div><dt>运行状态</dt><dd>已完成</dd></div><div><dt>输入快照</dt><dd>snap_a1b2c3d4</dd></div><div><dt>编排模板</dt><dd>默认交付核验 · v1</dd></div><div><dt>需求 / 验收核心</dt><dd>已执行</dd></div><div><dt>交付证据核心</dt><dd>Git Diff 已锁定执行</dd></div><div><dt>证据裁决与 Coverage</dt><dd>已执行</dd></div><div><dt>模型输出</dt><dd>仅作为建议，需人工确认</dd></div></dl><p class="run-orchestration-note">本次运行的能力块、Prompt 版本和工具授权均以启动时冻结的编排快照为准。</p></section><section v-else class="detail-section"><span class="detail-kicker">版本差异</span><p>当前展示的 Diff 与输入快照绑定。变更输入范围后必须创建新的正式快照。</p><pre class="diff-preview"><code>services/auth/login.ts
+ return unauthorizedResponse()
- throw internalError()</code></pre></section></aside>
</template>
