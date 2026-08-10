<script setup lang="ts">
import type { EvidenceReference } from '../../types/workbench'
defineProps<{ evidence: EvidenceReference[]; snapshotLabel?: string | null; live?: boolean }>()
</script>
<template>
  <aside class="notebook-pane notebook-sources"><header class="notebook-pane-header"><div><h2>来源与证据</h2><p>{{ live ? '真实运行输入快照' : '本次输入快照' }}</p></div><button type="button">管理来源</button></header><section class="snapshot-summary"><span>冻结快照</span><strong>{{ snapshotLabel ?? 'snap_a1b2c3d4' }}</strong><small>{{ live ? `当前结论已引用 ${evidence.length} 条证据` : '需求 2 份 · 代码 1 个提交 · 测试 1 份' }}</small></section><div class="source-toolbar"><button class="active" type="button">全部</button><button type="button">已引用</button><button type="button">待补证</button></div><div class="source-list"><article v-for="item in evidence" :key="item.id" class="source-item"><div><span class="source-kind">{{ item.kind }}</span><strong>{{ item.title }}</strong><small>{{ item.locator }}</small></div><span :class="['source-state', item.state === '待补充' ? 'pending' : 'cited']">{{ item.state }}</span></article></div><button class="outline-wide" type="button">添加人工补证</button></aside>
</template>
