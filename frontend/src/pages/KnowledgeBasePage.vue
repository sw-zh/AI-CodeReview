<script setup lang="ts">
import { computed, ref } from 'vue'

const selectedType = ref('需求')
const types = ['需求', '设计', '验收', '会议纪要', '测试', '补证']
const documents = [
  ['需求规格说明书 v1.2', '需求', '上传', 'v1.2', '已完成', '是', '2025-05-20 14:32'],
  ['需求变更记录 20250515', '需求', '文档导入', 'v1.3', '已完成', '是', '2025-05-18 09:15'],
  ['总体设计说明书 v2.0', '设计', '上传', 'v2.0', '已完成', '是', '2025-05-14 11:05'],
  ['接口设计文档 v1.1', '设计', '文档导入', 'v1.1', '处理中', '否', '2025-05-13 18:20'],
]
const visibleDocuments = computed(() => documents.filter((item) => selectedType.value === '需求' ? true : item[1] === selectedType.value))
</script>

<template>
  <section class="page page-knowledge"><header class="page-heading"><div><h1>项目知识库</h1><p>按资料类型、版本与快照引用关系管理可被核验的输入。</p></div><button class="primary-button" type="button">导入资料</button></header>
    <div class="knowledge-layout"><aside class="surface type-rail"><h2>资料类型</h2><button v-for="type in types" :key="type" type="button" :class="{ active: selectedType === type }" @click="selectedType = type">{{ type }}</button></aside><section class="surface knowledge-list"><div class="filter-row"><select aria-label="项目"><option>全部项目</option></select><select aria-label="来源方式"><option>全部来源方式</option></select><select aria-label="处理状态"><option>全部处理状态</option></select><select aria-label="快照引用"><option>全部快照引用</option></select><input placeholder="搜索文档名称" /></div><div class="data-table knowledge-table"><div class="table-row table-header"><span>文档名称</span><span>类型</span><span>来源方式</span><span>版本</span><span>处理状态</span><span>快照引用</span><span>更新时间</span></div><button v-for="(row, index) in visibleDocuments" :key="row[0]" class="table-row table-button" :class="{ selected: index === 1 }" type="button"><strong>{{ row[0] }}</strong><span>{{ row[1] }}</span><span>{{ row[2] }}</span><span>{{ row[3] }}</span><span>{{ row[4] }}</span><span>{{ row[5] }}</span><time>{{ row[6] }}</time></button></div></section></div>
  </section>
</template>
