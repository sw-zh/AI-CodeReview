<script setup lang="ts">
import type { EvidenceReference } from '../../types/workbench'
defineProps<{ evidence: EvidenceReference[]; snapshotLabel?: string | null; live?: boolean }>()
</script>
<template>
  <aside class="notebook-pane notebook-sources"><header class="notebook-pane-header"><div><h2>来源与证据</h2><p>{{ live ? '真实运行输入快照' : '尚未形成真实运行' }}</p></div></header><section class="snapshot-summary"><span>冻结快照</span><strong>{{ snapshotLabel ?? '尚未创建正式输入快照' }}</strong><small>{{ live ? `当前结论已引用 ${evidence.length} 条证据` : '只有冻结到正式输入快照的资料、Git Diff 与外部证据才能进入这里。' }}</small></section><div class="source-toolbar"><button class="active" type="button">全部</button><button type="button" disabled>已引用</button><button type="button" disabled>待补证</button></div><div v-if="evidence.length" class="source-list"><article v-for="item in evidence" :key="item.id" class="source-item"><div><span class="source-kind">{{ item.kind }}</span><strong>{{ item.title }}</strong><small>{{ item.locator }}</small></div><span :class="['source-state', item.state === '待补充' ? 'pending' : 'cited']">{{ item.state }}</span></article></div><p v-else class="notebook-empty">暂无可展示的冻结证据。</p></aside>
</template>
