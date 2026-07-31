<script setup lang="ts">
import { onMounted, ref } from 'vue'

const apiStatus = ref('检查 API 就绪状态…')

onMounted(async () => {
  try {
    const response = await fetch('/api/v1/health/ready')
    apiStatus.value = response.ok ? 'API 与事实存储已就绪' : 'API 已启动，事实存储尚未就绪'
  } catch {
    apiStatus.value = '无法连接 API'
  }
})
</script>

<template>
  <main class="shell">
    <p class="eyebrow">AI-CodeReview</p>
    <h1>多源证据核验与交付记录</h1>
    <p>{{ apiStatus }}</p>
    <p class="hint">首个功能切片将从任务、资料版本与不可变输入快照开始。</p>
  </main>
</template>
