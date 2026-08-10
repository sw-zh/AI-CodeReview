<script setup lang="ts">
import { computed } from 'vue'
import type { VerificationConclusion } from '../../types/workbench'
const props = defineProps<{ conclusions: VerificationConclusion[]; selectedId: string; live?: boolean }>()
const emit = defineEmits<{ select: [id: string] }>()
const summary = computed(() => ({
  confirmed: props.conclusions.filter((item) => item.status === '已确认').length,
  partial: props.conclusions.filter((item) => item.status === '部分支持').length,
  pending: props.conclusions.filter((item) => item.needsHumanDecision).length,
  p0: props.conclusions.filter((item) => item.risk === 'P0').length,
}))
</script>
<template>
  <section class="notebook-pane notebook-verification"><header class="notebook-pane-header"><div><h2>交付核验</h2><p>{{ live ? '当前真实运行结果' : '尚未运行固定双核' }}</p></div></header><section class="conclusion-banner"><span>当前结论</span><strong>{{ live && summary.p0 ? `存在 ${summary.p0} 项 P0 风险，暂不建议固化。` : live ? '当前运行没有 P0 风险。' : '尚未形成可审批的交付核验结论。' }}</strong><p>已确认 {{ summary.confirmed }} 项，部分支持 {{ summary.partial }} 项，待人工确认 {{ summary.pending }} 项。</p></section><div class="verification-toolbar"><button class="active" type="button">核验结论</button><button type="button" disabled>追问记录</button><button type="button" disabled>报告草稿</button></div><ol class="conclusion-list"><li v-for="item in conclusions" :key="item.id" :class="{ selected: selectedId === item.id }"><button type="button" @click="emit('select', item.id)"><div class="conclusion-top"><strong>{{ item.requirement }}</strong><span :class="['conclusion-status', item.status]">{{ item.status }}</span></div><p>{{ item.summary }}</p><small><span v-if="item.risk" :class="['risk-chip', item.risk]">{{ item.risk }}</span>{{ item.needsHumanDecision ? '需要人工确认' : '证据已形成闭环' }}</small></button></li></ol><section class="follow-up"><h3>继续追问</h3><p>{{ live ? '问题只读取当前快照内已授权证据，不会修改正式结论或审批状态。' : '形成正式输入快照并运行后，才能基于已冻结的证据追问。' }}</p></section></section>
</template>
