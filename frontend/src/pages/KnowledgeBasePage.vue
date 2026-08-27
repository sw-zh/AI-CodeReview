<script setup lang="ts">
import { computed, ref } from 'vue'

interface KbDocument {
  id: string
  name: string
  kind: string
  source: string
  version: string
  status: '已完成' | '处理中' | '待处理'
  snapshot: string
  updatedAt: string
  excerpt: string
}

interface KbLibrary {
  id: string
  name: string
  description: string
  tone: string
  docCount: number
  updatedBy: string
  updatedAt: string
  documents: KbDocument[]
}

const libraries: KbLibrary[] = [
  {
    id: 'req',
    name: '需求知识库',
    description: '需求规格、需求变更记录，作为交付验收的输入依据',
    tone: 'linear-gradient(135deg, #1f5d8e, #5b93c0)',
    docCount: 3,
    updatedBy: '张伟',
    updatedAt: '2025-05-20',
    documents: [
      { id: 'r1', name: '需求规格说明书 v1.2', kind: '需求', source: '上传', version: 'v1.2', status: '已完成', snapshot: '是', updatedAt: '2025-05-20 14:32', excerpt: '覆盖支付、退款与对账三块核心流程的完整需求规格说明，已通过评审冻结为本次交付的验收依据。' },
      { id: 'r2', name: '需求变更记录 20250515', kind: '需求', source: '文档导入', version: 'v1.3', status: '已完成', snapshot: '是', updatedAt: '2025-05-18 09:15', excerpt: '记录 5 月 15 日批次需求变更：新增对账报表导出字段，调整超时重试策略。' },
      { id: 'r3', name: '需求追踪矩阵', kind: '需求', source: '上传', version: 'v1.0', status: '处理中', snapshot: '否', updatedAt: '2025-05-17 16:40', excerpt: '需求编号与验收用例的逐项映射表，部分条目待补充关联。' },
    ],
  },
  {
    id: 'design',
    name: '设计知识库',
    description: '总体设计、接口设计与数据库设计文档',
    tone: 'linear-gradient(135deg, #5b4a8e, #8f7fc4)',
    docCount: 2,
    updatedBy: '李倩',
    updatedAt: '2025-05-14',
    documents: [
      { id: 'd1', name: '总体设计说明书 v2.0', kind: '设计', source: '上传', version: 'v2.0', status: '已完成', snapshot: '是', updatedAt: '2025-05-14 11:05', excerpt: '模块划分、依赖关系与部署拓扑的总设计说明，与需求规格 v1.2 关联。' },
      { id: 'd2', name: '接口设计文档 v1.1', kind: '设计', source: '文档导入', version: 'v1.1', status: '处理中', snapshot: '否', updatedAt: '2025-05-13 18:20', excerpt: '对外 REST 接口契约与字段定义，正在补充错误码枚举说明。' },
    ],
  },
  {
    id: 'accept',
    name: '验收知识库',
    description: '验收标准、验收用例与验收记录',
    tone: 'linear-gradient(135deg, #527360, #7ea98c)',
    docCount: 2,
    updatedBy: '王芳',
    updatedAt: '2025-05-16',
    documents: [
      { id: 'a1', name: '验收标准 V3.0', kind: '验收', source: '上传', version: 'v3.0', status: '已完成', snapshot: '是', updatedAt: '2025-05-16 10:22', excerpt: '明确功能、性能与安全三类验收标准及通过条件，作为人工裁决依据。' },
      { id: 'a2', name: '验收用例集', kind: '验收', source: '文档导入', version: 'v2.4', status: '待处理', snapshot: '否', updatedAt: '2025-05-12 15:08', excerpt: '覆盖主流程与异常路径的验收用例集合，待补充回归结果。' },
    ],
  },
  {
    id: 'meeting',
    name: '会议纪要知识库',
    description: '评审会、周会与专项讨论纪要',
    tone: 'linear-gradient(135deg, #98661a, #c99a4a)',
    docCount: 1,
    updatedBy: '赵磊',
    updatedAt: '2025-05-19',
    documents: [
      { id: 'm1', name: '交付评审会议纪要 20250519', kind: '会议纪要', source: '上传', version: 'v1.0', status: '已完成', snapshot: '否', updatedAt: '2025-05-19 17:30', excerpt: '本次交付评审结论与遗留问题清单，含 2 项待补证风险项。' },
    ],
  },
  {
    id: 'test',
    name: '测试知识库',
    description: '测试报告、缺陷记录与回归结果',
    tone: 'linear-gradient(135deg, #a24435, #cc6f5e)',
    docCount: 1,
    updatedBy: '测试组',
    updatedAt: '2025-05-15',
    documents: [
      { id: 't1', name: '系统测试报告 20250515', kind: '测试', source: '文档导入', version: 'v1.1', status: '已完成', snapshot: '是', updatedAt: '2025-05-15 20:02', excerpt: '核心流程自动化与手工测试结果汇总，缺陷已全部闭环。' },
    ],
  },
  {
    id: 'supp',
    name: '补证知识库',
    description: '针对证据不足项的补充材料',
    tone: 'linear-gradient(135deg, #6b6f7a, #9aa0ad)',
    docCount: 1,
    updatedBy: '张伟',
    updatedAt: '2025-05-21',
    documents: [
      { id: 's1', name: '补证材料：限流压测报告', kind: '补证', source: '上传', version: 'v1.0', status: '处理中', snapshot: '否', updatedAt: '2025-05-21 09:41', excerpt: '针对高并发限流风险项的补充压测证据，待核验确认。' },
    ],
  },
]

const activeLibrary = ref<KbLibrary | null>(null)
const selectedDoc = ref<KbDocument | null>(null)
const searchQuery = ref('')

const visibleLibraries = computed(() =>
  libraries.filter((lib) => lib.name.includes(searchQuery.value.trim()) || lib.description.includes(searchQuery.value.trim())),
)

function openLibrary(lib: KbLibrary) {
  activeLibrary.value = lib
  selectedDoc.value = lib.documents[0] ?? null
}

function closeLibrary() {
  activeLibrary.value = null
  selectedDoc.value = null
}
</script>

<template>
  <section class="page page-knowledge">
    <header class="page-heading">
      <div><h1>项目知识库</h1><p>按知识库与文档组织可被核验的输入资料，支持检索与版本追踪。</p></div>
      <button class="primary-button" type="button">导入资料</button>
    </header>

    <!-- 知识库首页：封面卡片网格 -->
    <div v-if="!activeLibrary" class="kb-home">
      <div class="kb-search">
        <input v-model="searchQuery" placeholder="搜索知识库、文档或内容" />
      </div>
      <div v-if="visibleLibraries.length" class="kb-grid">
        <button v-for="lib in visibleLibraries" :key="lib.id" class="kb-card" type="button" @click="openLibrary(lib)">
          <span class="kb-card-cover" :style="{ background: lib.tone }">{{ lib.name.slice(0, 1) }}</span>
          <span class="kb-card-body">
            <strong>{{ lib.name }}</strong>
            <small>{{ lib.description }}</small>
            <em>{{ lib.docCount }} 篇文档 · {{ lib.updatedBy }} 更新 · {{ lib.updatedAt }}</em>
          </span>
        </button>
      </div>
      <p v-else class="kb-empty">没有匹配的知识库，换个关键词试试。</p>
    </div>

    <!-- 知识库详情：左侧目录树 + 右侧文档画布 -->
    <div v-else class="kb-workspace">
      <aside class="kb-sidebar">
        <button class="kb-back" type="button" @click="closeLibrary">← 全部知识库</button>
        <h2>{{ activeLibrary.name }}</h2>
        <nav class="kb-tree">
          <div class="kb-tree-group">
            <span class="kb-tree-group-title">全部文档</span>
            <button
              v-for="doc in activeLibrary.documents"
              :key="doc.id"
              class="kb-tree-item"
              :class="{ active: selectedDoc?.id === doc.id }"
              type="button"
              @click="selectedDoc = doc"
            >
              <i :class="['kb-status-dot', doc.status]"></i>{{ doc.name }}
            </button>
          </div>
        </nav>
      </aside>
      <section class="kb-detail">
        <template v-if="selectedDoc">
          <header class="kb-doc-header">
            <div><h2>{{ selectedDoc.name }}</h2><span :class="['kb-badge', selectedDoc.status]">{{ selectedDoc.status }}</span></div>
            <time>更新于 {{ selectedDoc.updatedAt }}</time>
          </header>
          <dl class="kb-meta">
            <div><dt>类型</dt><dd>{{ selectedDoc.kind }}</dd></div>
            <div><dt>来源方式</dt><dd>{{ selectedDoc.source }}</dd></div>
            <div><dt>版本</dt><dd>{{ selectedDoc.version }}</dd></div>
            <div><dt>快照引用</dt><dd>{{ selectedDoc.snapshot }}</dd></div>
          </dl>
          <div class="kb-preview"><h3>文档预览</h3><p>{{ selectedDoc.excerpt }}</p></div>
        </template>
        <div v-else class="kb-empty">从左侧选择一个文档查看详情。</div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.kb-home {
  display: grid;
  gap: 22px;
}

/* 搜索条 */
.kb-search {
  max-width: 560px;
}
.kb-search input {
  width: 100%;
  min-height: 42px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: var(--surface);
  color: var(--ink);
  padding: 0 14px;
  font: inherit;
  font-size: 0.86rem;
  outline: none;
}
.kb-search input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgb(31 93 142 / 0.12);
}

/* 封面卡片网格 */
.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(248px, 1fr));
  gap: 16px;
}
.kb-card {
  display: grid;
  grid-template-columns: 56px minmax(0, 1fr);
  gap: 12px;
  min-height: 96px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  color: var(--ink);
  padding: 12px;
  text-align: left;
  cursor: pointer;
  font: inherit;
  transition: box-shadow 0.16s ease, transform 0.16s ease;
}
.kb-card:hover {
  box-shadow: 0 10px 26px rgb(43 39 35 / 0.1);
  transform: translateY(-2px);
}
.kb-card-cover {
  display: grid;
  place-items: center;
  width: 56px;
  height: 56px;
  border-radius: 10px;
  color: #fff;
  font-size: 1.3rem;
  font-weight: 800;
}
.kb-card-body {
  display: grid;
  align-content: start;
  gap: 4px;
  min-width: 0;
}
.kb-card-body strong {
  overflow: hidden;
  font-size: 0.9rem;
  letter-spacing: -0.015em;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-card-body small {
  overflow: hidden;
  color: var(--muted);
  font-size: 0.74rem;
  line-height: 1.5;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.kb-card-body em {
  color: var(--muted);
  font-size: 0.68rem;
  font-style: normal;
}

/* 知识库详情 */
.kb-workspace {
  display: grid;
  grid-template-columns: 236px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}
.kb-sidebar {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  padding: 12px 10px 16px;
}
.kb-back {
  border: 0;
  background: transparent;
  color: var(--brand);
  padding: 4px 6px 10px;
  font: inherit;
  font-size: 0.76rem;
  font-weight: 750;
  cursor: pointer;
}
.kb-sidebar h2 {
  margin: 0;
  padding: 4px 6px 12px;
  color: var(--ink);
  font-size: 0.98rem;
  letter-spacing: -0.018em;
  border-bottom: 1px solid var(--line-soft);
}
.kb-tree {
  padding-top: 10px;
}
.kb-tree-group-title {
  display: block;
  padding: 4px 6px 8px;
  color: var(--muted);
  font-size: 0.7rem;
  font-weight: 800;
}
.kb-tree-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  min-height: 36px;
  border: 0;
  border-radius: 7px;
  background: transparent;
  color: var(--ink);
  padding: 0 8px;
  font: inherit;
  font-size: 0.78rem;
  text-align: left;
  cursor: pointer;
}
.kb-tree-item:hover {
  background: #f4f0ec;
}
.kb-tree-item.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 750;
}
.kb-status-dot {
  flex: 0 0 auto;
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--muted);
}
.kb-status-dot.已完成 {
  background: var(--success);
}
.kb-status-dot.处理中 {
  background: var(--warning);
}
.kb-status-dot.待处理 {
  background: var(--muted);
}

/* 文档画布 */
.kb-detail {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  padding: 22px 24px 28px;
}
.kb-doc-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line-soft);
}
.kb-doc-header h2 {
  margin: 0;
  color: var(--ink);
  font-size: 1.1rem;
  letter-spacing: -0.02em;
}
.kb-doc-header time {
  flex: 0 0 auto;
  color: var(--muted);
  font-size: 0.72rem;
}
.kb-badge {
  display: inline-block;
  margin-top: 8px;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  padding: 2px 10px;
  font-size: 0.7rem;
  font-weight: 800;
}
.kb-badge.已完成 {
  background: rgb(82 115 96 / 0.14);
  color: var(--success);
}
.kb-badge.处理中 {
  background: rgb(152 102 26 / 0.14);
  color: var(--warning);
}
.kb-badge.待处理 {
  background: rgb(118 110 104 / 0.14);
  color: var(--muted);
}
.kb-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 16px 0 0;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--line-soft);
}
.kb-meta dt {
  color: var(--muted);
  font-size: 0.7rem;
}
.kb-meta dd {
  margin: 4px 0 0;
  color: var(--ink);
  font-size: 0.84rem;
  font-weight: 750;
}
.kb-preview h3 {
  margin: 18px 0 8px;
  color: var(--ink);
  font-size: 0.84rem;
}
.kb-preview p {
  margin: 0;
  color: #615951;
  font-size: 0.82rem;
  line-height: 1.75;
}
.kb-empty {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
  text-align: center;
  padding: 48px 0;
}
</style>
