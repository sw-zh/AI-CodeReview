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
  <section class="notebook-pane notebook-verification"><header class="notebook-pane-header"><div><h2>交付核验</h2><p>{{ live ? '当前真实运行结果' : '报告草稿 v1.3.2' }}</p></div><button class="primary-button" type="button">提交审批</button></header><section class="conclusion-banner"><span>当前结论</span><strong>{{ summary.p0 ? `存在 ${summary.p0} 项 P0 风险，暂不建议发布。` : '当前没有 P0 风险。' }}</strong><p>已确认 {{ summary.confirmed }} 项，部分支持 {{ summary.partial }} 项，待人工确认 {{ summary.pending }} 项。</p></section><div class="verification-toolbar"><button class="active" type="button">核验结论</button><button type="button">追问记录</button><button type="button">报告草稿</button></div><ol class="conclusion-list"><li v-for="item in conclusions" :key="item.id" :class="{ selected: selectedId === item.id }"><button type="button" @click="emit('select', item.id)"><div class="conclusion-top"><strong>{{ item.requirement }}</strong><span :class="['conclusion-status', item.status]">{{ item.status }}</span></div><p>{{ item.summary }}</p><small><span v-if="item.risk" :class="['risk-chip', item.risk]">{{ item.risk }}</span>{{ item.needsHumanDecision ? '需要人工确认' : '证据已形成闭环' }}</small></button></li></ol><section class="follow-up"><h3>继续追问</h3><p>问题只读取当前快照内已授权证据，不会修改正式结论或审批状态。</p><div><input aria-label="追问内容" placeholder="基于本次证据继续追问" /><button type="button">发送</button></div></section></section>
</template>
