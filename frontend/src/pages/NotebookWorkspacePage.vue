<script setup lang="ts">
import { computed, ref } from 'vue'
import { RouterLink } from 'vue-router'
import ReviewDetailPane from '../features/notebook/ReviewDetailPane.vue'
import SourceEvidencePane from '../features/notebook/SourceEvidencePane.vue'
import VerificationPane from '../features/notebook/VerificationPane.vue'
import { notebookConclusions, notebookEvidence } from '../features/workbench/workbench-fixtures'
const selectedId = ref(notebookConclusions[0].id)
const selectedConclusion = computed(() => notebookConclusions.find((item) => item.id === selectedId.value) ?? notebookConclusions[0])
</script>
<template>
  <section class="notebook-page"><header class="notebook-topbar"><RouterLink to="/tasks">返回任务中心</RouterLink><div><h1>支付流程重构核验</h1><p>任务 TASK-5240 · 输入快照 snap_a1b2c3d4</p></div><span class="notebook-status">待人工确认</span></header><main class="notebook-grid"><SourceEvidencePane :evidence="notebookEvidence" /><VerificationPane :conclusions="notebookConclusions" :selected-id="selectedId" @select="selectedId = $event" /><ReviewDetailPane :conclusion="selectedConclusion" :evidence="notebookEvidence" /></main></section>
</template>
