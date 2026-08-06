<script setup lang="ts">
import { ref } from 'vue'
const active = ref('仓库连接')
const items = ['项目成员', '仓库连接', '资料处理', '模型配置', '通知', '审计']
</script>
<template>
  <section class="page page-integrations"><header class="page-heading"><div><h1>集成与设置</h1><p>低频配置集中管理，不干扰日常核验与审批流程。</p></div></header><div class="settings-layout"><aside class="surface settings-rail"><button v-for="item in items" :key="item" type="button" :class="{ active: active === item }" @click="active = item">{{ item }}</button></aside><section class="surface settings-content"><h2>{{ active }}</h2><p class="section-description">管理只读仓库、资料处理、模型调用与通知连接。</p><div class="settings-group"><h3>代码仓库</h3><div class="setting-row"><div><strong>Git 仓库</strong><p>只读获取提交、Diff 与历史记录。</p></div><span class="state-success">已连接</span><time>2025-05-26 10:24</time><button type="button">管理连接</button></div></div><div class="settings-group"><h3>资料处理</h3><div class="setting-row"><div><strong>文档解析服务</strong><p>解析 PDF、Word、Markdown，构建可检索资料。</p></div><span class="state-success">运行中</span><time>2025-05-26 09:58</time><button type="button">配置</button></div><div class="setting-row"><div><strong>数据文件处理</strong><p>处理 CSV、Excel 等结构化资料。</p></div><span class="state-attention">部分启用</span><time>2025-05-25 18:42</time><button type="button">配置</button></div></div><div class="danger-row"><div><strong>断开并重新连接 Git 仓库</strong><p>历史快照与交付记录不会被修改。</p></div><button type="button">断开连接</button></div></section></div></section>
</template>
