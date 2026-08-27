<script setup lang="ts">
import { computed, ref } from 'vue'

interface KbDoc {
  id: string
  name: string
  ext: string
  size: string
  status: '已完成' | '处理中' | '待处理'
  updatedAt: string
  author: string
  version: string
  excerpt: string
}

interface KbFolder {
  id: string
  name: string
  updatedAt: string
  docs: KbDoc[]
}

interface KbLibrary {
  id: string
  name: string
  description: string
  tone: string
  updatedAt: string
  folders: KbFolder[]
  docs: KbDoc[]
}

const libraries = ref<KbLibrary[]>([
  {
    id: 'kb1',
    name: '支付系统交付资料',
    description: '一期交付所需的全部输入依据',
    tone: 'linear-gradient(135deg, #1f5d8e, #5b93c0)',
    updatedAt: '05-20',
    folders: [
      {
        id: 'f1',
        name: '需求文档',
        updatedAt: '05-20',
        docs: [
          { id: 'd1', name: '需求规格说明书.pdf', ext: 'PDF', size: '2.4 MB', status: '已完成', updatedAt: '2025-05-20 14:32', author: '张伟', version: 'v1.2', excerpt: '覆盖支付、退款与对账三块核心流程的完整需求规格说明，已评审冻结为本次交付的验收依据。' },
          { id: 'd2', name: '需求变更记录.docx', ext: 'DOC', size: '820 KB', status: '已完成', updatedAt: '2025-05-18 09:15', author: '张伟', version: 'v1.3', excerpt: '记录 5 月 15 日批次需求变更：新增对账报表导出字段，调整超时重试策略。' },
        ],
      },
      {
        id: 'f2',
        name: '验收材料',
        updatedAt: '05-16',
        docs: [
          { id: 'd3', name: '验收标准.docx', ext: 'DOC', size: '1.1 MB', status: '已完成', updatedAt: '2025-05-16 10:22', author: '王芳', version: 'v3.0', excerpt: '明确功能、性能与安全三类验收标准及通过条件，作为人工裁决依据。' },
          { id: 'd4', name: '验收用例集.xlsx', ext: 'XLS', size: '640 KB', status: '处理中', updatedAt: '2025-05-12 15:08', author: '王芳', version: 'v2.4', excerpt: '覆盖主流程与异常路径的验收用例集合，待补充回归结果。' },
        ],
      },
    ],
    docs: [{ id: 'd5', name: '项目说明.md', ext: 'MD', size: '12 KB', status: '已完成', updatedAt: '2025-05-14 11:05', author: '李倩', version: 'v1.0', excerpt: '项目背景、目标与交付范围说明。' }],
  },
  {
    id: 'kb2',
    name: '项目协作记录',
    description: '会议纪要、决策与任务记录',
    tone: 'linear-gradient(135deg, #98661a, #c99a4a)',
    updatedAt: '05-19',
    folders: [
      {
        id: 'f3',
        name: '会议纪要',
        updatedAt: '05-19',
        docs: [
          { id: 'd6', name: '交付评审纪要.docx', ext: 'DOC', size: '360 KB', status: '已完成', updatedAt: '2025-05-19 17:30', author: '赵磊', version: 'v1.0', excerpt: '本次交付评审结论与遗留问题清单，含 2 项待补证风险项。' },
          { id: 'd7', name: '周会纪要.docx', ext: 'DOC', size: '280 KB', status: '待处理', updatedAt: '2025-05-12 09:00', author: '赵磊', version: 'v1.0', excerpt: '本周例会讨论事项与待办。' },
        ],
      },
    ],
    docs: [{ id: 'd8', name: '任务清单.md', ext: 'MD', size: '8 KB', status: '已完成', updatedAt: '2025-05-10 16:40', author: '测试组', version: 'v1.0', excerpt: '团队任务清单与责任人分工。' }],
  },
  {
    id: 'kb3',
    name: '对外合同',
    description: '合同文件与补充证明材料',
    tone: 'linear-gradient(135deg, #6b6f7a, #9aa0ad)',
    updatedAt: '05-21',
    folders: [
      {
        id: 'f4',
        name: '合同',
        updatedAt: '05-21',
        docs: [{ id: 'd9', name: '合同扫描件.pdf', ext: 'PDF', size: '4.8 MB', status: '处理中', updatedAt: '2025-05-21 09:41', author: '张伟', version: 'v1.0', excerpt: '双方签署的正式合同扫描件，扫描版待 OCR 核验。' }],
      },
      {
        id: 'f5',
        name: '补充材料',
        updatedAt: '05-17',
        docs: [{ id: 'd10', name: '补证材料.pdf', ext: 'PDF', size: '1.9 MB', status: '已完成', updatedAt: '2025-05-17 09:10', author: '张伟', version: 'v1.0', excerpt: '针对高并发限流风险项的补充压测报告，已核验确认。' }],
      },
    ],
    docs: [],
  },
])

type NodeKind = 'kb' | 'folder' | 'doc'

interface SelectedNode {
  kind: NodeKind
  id: string
}

const expandedKbs = ref<Set<string>>(new Set(libraries.value.map((lib) => lib.id)))
const expandedFolders = ref<Set<string>>(new Set(['f1']))
const selected = ref<SelectedNode>({ kind: 'kb', id: 'kb1' })

const createModal = ref<{ kind: NodeKind; title: string; placeholder: string } | null>(null)
const createName = ref('')
const createDesc = ref('')
const searchQuery = ref('')

function findKb(kbId: string) {
  return libraries.value.find((lib) => lib.id === kbId) ?? null
}

const selectedKb = computed(() => selected.value.kind === 'kb' ? findKb(selected.value.id) : null)
const selectedFolder = computed(() => {
  if (selected.value.kind !== 'folder') return null
  for (const lib of libraries.value) {
    const folder = lib.folders.find((folder) => folder.id === selected.value.id)
    if (folder) return folder
  }
  return null
})
const selectedDoc = computed(() => {
  if (selected.value.kind !== 'doc') return null
  for (const lib of libraries.value) {
    for (const folder of lib.folders) {
      const doc = folder.docs.find((doc) => doc.id === selected.value.id)
      if (doc) return { doc, kb: lib, folder }
    }
    const doc = lib.docs.find((doc) => doc.id === selected.value.id)
    if (doc) return { doc, kb: lib, folder: null }
  }
  return null
})

/** 当前选中的知识库对象（含父链定位） */
const activeKb = computed(() => {
  if (selected.value.kind === 'kb') return findKb(selected.value.id)
  if (selected.value.kind === 'folder') {
    for (const lib of libraries.value) if (lib.folders.some((folder) => folder.id === selected.value.id)) return lib
  }
  if (selected.value.kind === 'doc') return selectedDoc.value?.kb ?? null
  return null
})

/** 选中知识库根级直接文档 */
const rootDocs = computed(() => {
  if (selected.value.kind !== 'kb') return []
  return findKb(selected.value.id)?.docs ?? []
})

/** 选中文件夹下的文档 */
const folderDocs = computed(() => {
  if (selected.value.kind !== 'folder') return []
  return selectedFolder.value?.docs ?? []
})

const breadcrumb = computed(() => {
  if (selected.value.kind === 'kb') return [activeKb.value?.name ?? '']
  if (selected.value.kind === 'folder') return [activeKb.value?.name ?? '', selectedFolder.value?.name ?? '']
  const ctx = selectedDoc.value
  return [ctx?.kb.name ?? '', ctx?.folder?.name ?? '', ctx?.doc.name ?? ''].filter(Boolean)
})

function toggleKb(kbId: string) {
  const next = new Set(expandedKbs.value)
  if (next.has(kbId)) next.delete(kbId)
  else next.add(kbId)
  expandedKbs.value = next
}

function toggleFolder(folderId: string) {
  const next = new Set(expandedFolders.value)
  if (next.has(folderId)) next.delete(folderId)
  else next.add(folderId)
  expandedFolders.value = next
}

function select(kind: NodeKind, id: string) {
  selected.value = { kind, id }
}

/** 点击知识库/文件夹行：选中 + 展开/收起 */
function clickKb(lib: KbLibrary) {
  select('kb', lib.id)
  toggleKb(lib.id)
}

function clickFolder(folder: KbFolder) {
  select('folder', folder.id)
  toggleFolder(folder.id)
}

function openCreate(kind: NodeKind) {
  createName.value = ''
  createDesc.value = ''
  const titles: Record<NodeKind, string> = { kb: '新建知识库', folder: '新建文件夹', doc: '新建文档' }
  const placeholders: Record<NodeKind, string> = { kb: '输入知识库名称', folder: '输入文件夹名称', doc: '输入文档名称（含扩展名，如 report.pdf）' }
  createModal.value = { kind, title: titles[kind], placeholder: placeholders[kind] }
}

function confirmCreate() {
  if (!createModal.value || !createName.value.trim()) return
  const kind = createModal.value.kind
  const name = createName.value.trim()
  if (kind === 'kb') {
    const kb: KbLibrary = { id: `kb${Date.now()}`, name, description: createDesc.value.trim() || '新建知识库', tone: 'linear-gradient(135deg, #5b4a8e, #8f7fc4)', updatedAt: '刚刚', folders: [], docs: [] }
    libraries.value = [kb, ...libraries.value]
    expandedKbs.value.add(kb.id)
    selected.value = { kind: 'kb', id: kb.id }
  } else if (kind === 'folder') {
    const kb = activeKb.value
    if (!kb) return
    const folder: KbFolder = { id: `f${Date.now()}`, name, updatedAt: '刚刚', docs: [] }
    kb.folders = [...kb.folders, folder]
    expandedFolders.value.add(folder.id)
    selected.value = { kind: 'folder', id: folder.id }
  } else {
    const kb = activeKb.value
    if (!kb) return
    const match = name.match(/\.(\w+)$/)
    const doc: KbDoc = { id: `d${Date.now()}`, name, ext: (match?.[1] ?? 'PDF').toUpperCase(), size: '—', status: '待处理', updatedAt: '刚刚', excerpt: '新建文档，待补充内容。' }
    if (selected.value.kind === 'folder' && selectedFolder.value) {
      selectedFolder.value.docs = [...selectedFolder.value.docs, doc]
    } else {
      kb.docs = [...kb.docs, doc]
    }
    selected.value = { kind: 'doc', id: doc.id }
  }
  createModal.value = null
}

const extTone: Record<string, string> = {
  PDF: 'rgb(162 68 53 / 0.14)',
  DOC: 'rgb(31 93 142 / 0.14)',
  XLS: 'rgb(82 115 96 / 0.14)',
  MD: 'rgb(118 110 104 / 0.16)',
  PNG: 'rgb(91 74 142 / 0.14)',
  JPG: 'rgb(91 74 142 / 0.14)',
}

function toneOf(ext: string) {
  return extTone[ext] ?? 'rgb(118 110 104 / 0.14)'
}
</script>

<template>
  <section class="page page-knowledge">
    <header class="page-heading">
      <div><h1>项目知识库</h1><p>按文件夹分级组织知识库与文档，左侧选择层级，右侧卡片展示。</p></div>
    </header>

    <div class="kb-layout">
      <!-- 左侧：文件夹模式分级树 -->
      <aside class="kb-sidebar">
        <button class="kb-create" type="button" @click="openCreate('kb')">＋ 新建知识库</button>
        <div class="kb-tree-label">我的知识库</div>
        <nav class="kb-tree">
          <div v-for="lib in libraries" :key="lib.id" class="kb-node kb-node-kb">
            <button class="kb-node-row" :class="{ active: selected.kind === 'kb' && selected.id === lib.id }" type="button" @click="clickKb(lib)">
              <span :class="['kb-caret', !expandedKbs.has(lib.id) ? 'collapsed' : '']">▾</span>
              <i class="kb-folder-ico"><svg class="kb-folder-svg" viewBox="0 0 24 24" aria-hidden="true"><path fill="#f2b636" d="M3 6a2 2 0 0 1 2-2h4.2c.3 0 .58.13.76.36L11.5 6H19a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6z"></path><path fill="#d99a2b" d="M3 8V6a2 2 0 0 1 2-2h4.2c.3 0 .58.13.76.36L11.5 6H19a2 2 0 0 1 2 2V8H3z"></path></svg></i>
              <span class="kb-node-name">{{ lib.name }}</span>
            </button>
            <div v-if="expandedKbs.has(lib.id)" class="kb-node-children">
              <div v-for="folder in lib.folders" :key="folder.id" class="kb-node kb-node-folder">
                <button class="kb-node-row" :class="{ active: selected.kind === 'folder' && selected.id === folder.id }" type="button" @click="clickFolder(folder)">
                  <span :class="['kb-caret', !expandedFolders.has(folder.id) ? 'collapsed' : '']">▾</span>
                  <i class="kb-folder-ico plain">▤</i>
                  <span class="kb-node-name">{{ folder.name }}</span>
                </button>
                <div v-if="expandedFolders.has(folder.id)" class="kb-node-children">
                  <button
                    v-for="doc in folder.docs"
                    :key="doc.id"
                    class="kb-node-row kb-node-doc"
                    :class="{ active: selected.kind === 'doc' && selected.id === doc.id }"
                    type="button"
                    @click="select('doc', doc.id)"
                  >
                    <i class="kb-doc-dot" :style="{ background: toneOf(doc.ext) }">{{ doc.ext }}</i>
                    <span class="kb-node-name">{{ doc.name }}</span>
                  </button>
                </div>
              </div>
              <button
                v-for="doc in lib.docs"
                :key="doc.id"
                class="kb-node-row kb-node-doc"
                :class="{ active: selected.kind === 'doc' && selected.id === doc.id }"
                type="button"
                @click="select('doc', doc.id)"
              >
                <i class="kb-doc-dot" :style="{ background: toneOf(doc.ext) }">{{ doc.ext }}</i>
                <span class="kb-node-name">{{ doc.name }}</span>
              </button>
            </div>
          </div>
        </nav>
      </aside>

      <!-- 右侧：按层级卡片展示 -->
      <section class="kb-main">
        <div class="kb-toolbar">
          <nav class="kb-crumbs">
            <span v-for="(crumb, index) in breadcrumb" :key="index">
              <i v-if="index > 0" class="kb-crumb-sep">/</i>{{ crumb }}
            </span>
          </nav>
          <div class="kb-toolbar-actions">
            <button v-if="selected.kind !== 'doc'" class="kb-btn" type="button" @click="openCreate('folder')">＋ 新建文件夹</button>
            <button class="kb-btn kb-btn-primary" type="button" @click="openCreate('doc')">＋ 新建文档</button>
          </div>
        </div>

        <!-- 选中知识库：文件夹卡片 + 根级文档卡片 同一行排布 -->
        <template v-if="selected.kind === 'kb' && selectedKb">
          <div class="kb-section-head"><h2>{{ selectedKb.name }}</h2><span>{{ selectedKb.description }}</span></div>
          <div v-if="selectedKb.folders.length || rootDocs.length" class="kb-card-grid">
            <button v-for="folder in selectedKb.folders" :key="folder.id" class="kb-card kb-card-folder" type="button" @click="clickFolder(folder)">
              <i class="kb-card-folder-ico">▤</i>
              <strong>{{ folder.name }}</strong>
              <em>{{ folder.docs.length }} 篇文档 · 更新于 {{ folder.updatedAt }}</em>
            </button>
            <button v-for="doc in rootDocs" :key="doc.id" class="kb-card kb-card-doc" type="button" @click="select('doc', doc.id)">
              <i class="kb-file-ico" :style="{ background: toneOf(doc.ext) }">{{ doc.ext }}</i>
              <span class="kb-card-doc-name">{{ doc.name }}</span>
              <span class="kb-card-doc-excerpt">{{ doc.excerpt }}</span>
              <span class="kb-card-doc-meta">{{ doc.version }} · {{ doc.size }} · {{ doc.author }}</span>
              <span class="kb-card-doc-foot">
                <span :class="['kb-badge', doc.status]">{{ doc.status }}</span>
                <time>{{ doc.updatedAt }}</time>
              </span>
            </button>
          </div>
        </template>

        <!-- 选中文件夹：文档卡片 -->
        <template v-else-if="selected.kind === 'folder' && selectedFolder">
          <div class="kb-section-head"><h2>{{ selectedFolder.name }}</h2><span>{{ activeKb?.name }}</span></div>
          <div v-if="folderDocs.length" class="kb-card-grid">
            <button v-for="doc in folderDocs" :key="doc.id" class="kb-card kb-card-doc" type="button" @click="select('doc', doc.id)">
              <i class="kb-file-ico" :style="{ background: toneOf(doc.ext) }">{{ doc.ext }}</i>
              <span class="kb-card-doc-name">{{ doc.name }}</span>
              <span class="kb-card-doc-excerpt">{{ doc.excerpt }}</span>
              <span class="kb-card-doc-meta">{{ doc.version }} · {{ doc.size }} · {{ doc.author }}</span>
              <span class="kb-card-doc-foot">
                <span :class="['kb-badge', doc.status]">{{ doc.status }}</span>
                <time>{{ doc.updatedAt }}</time>
              </span>
            </button>
          </div>
        </template>

        <!-- 选中文档：详情卡片 -->
        <template v-else-if="selected.kind === 'doc' && selectedDoc">
          <div class="kb-doc-detail">
            <div class="kb-doc-detail-head">
              <i class="kb-file-ico kb-file-ico-lg" :style="{ background: toneOf(selectedDoc.doc.ext) }">{{ selectedDoc.doc.ext }}</i>
              <div>
                <h2>{{ selectedDoc.doc.name }}</h2>
                <span :class="['kb-badge', selectedDoc.doc.status]">{{ selectedDoc.doc.status }}</span>
              </div>
            </div>
            <dl class="kb-meta">
              <div><dt>所属知识库</dt><dd>{{ selectedDoc.kb.name }}</dd></div>
              <div><dt>所在文件夹</dt><dd>{{ selectedDoc.folder?.name ?? '知识库根级' }}</dd></div>
              <div><dt>大小</dt><dd>{{ selectedDoc.doc.size }}</dd></div>
              <div><dt>更新时间</dt><dd>{{ selectedDoc.doc.updatedAt }}</dd></div>
            </dl>
            <div class="kb-preview"><h3>内容摘要</h3><p>{{ selectedDoc.doc.excerpt }}</p></div>
          </div>
        </template>
      </section>
    </div>

    <!-- 新建弹窗 -->
    <div v-if="createModal" class="kb-modal-overlay" @click.self="createModal = null">
      <div class="kb-modal" role="dialog" :aria-label="createModal.title">
        <h3>{{ createModal.title }}</h3>
        <input v-model="createName" :placeholder="createModal.placeholder" @keyup.enter="confirmCreate" />
        <input v-if="createModal.kind === 'kb'" v-model="createDesc" placeholder="输入知识库描述（可选）" />
        <div class="kb-modal-actions">
          <button class="kb-btn" type="button" @click="createModal = null">取消</button>
          <button class="kb-btn kb-btn-primary" type="button" :disabled="!createName.trim()" @click="confirmCreate">创建</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.kb-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

/* 左侧树 */
.kb-sidebar {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  padding: 12px 10px 16px;
}
.kb-create {
  width: 100%;
  min-height: 38px;
  border: 1px dashed var(--brand);
  border-radius: 9px;
  background: var(--brand-soft);
  color: var(--brand);
  padding: 0 10px;
  font: inherit;
  font-size: 0.8rem;
  font-weight: 750;
  cursor: pointer;
}
.kb-create:hover {
  background: rgb(31 93 142 / 0.16);
}
.kb-tree-label {
  padding: 14px 6px 8px;
  color: var(--muted);
  font-size: 0.7rem;
  font-weight: 800;
}
.kb-tree {
  display: grid;
  gap: 2px;
}
.kb-node-children {
  display: grid;
  gap: 2px;
  margin-left: 16px;
  padding-left: 6px;
  border-left: 1px solid var(--line-soft);
}
.kb-node-row {
  display: flex;
  align-items: center;
  gap: 7px;
  width: 100%;
  min-height: 34px;
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
.kb-node-row:hover {
  background: #f4f0ec;
}
.kb-node-row.active {
  background: var(--brand-soft);
  color: var(--brand);
  font-weight: 750;
}
.kb-caret {
  flex: 0 0 auto;
  font-size: 0.62rem;
  color: var(--muted);
  transition: transform 0.14s ease;
}
.kb-caret.collapsed {
  transform: rotate(-90deg);
}
.kb-folder-ico {
  display: grid;
  place-items: center;
  width: 20px;
  height: 16px;
  font-style: normal;
}
.kb-folder-svg {
  width: 19px;
  height: 15px;
}
.kb-folder-ico.plain {
  background: rgb(118 110 104 / 0.22);
  color: var(--muted);
  font-size: 0.72rem;
}
.kb-node-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-node-doc .kb-node-name {
  color: #615951;
}
.kb-node-doc.active .kb-node-name {
  color: var(--brand);
}
.kb-doc-dot {
  flex: 0 0 auto;
  display: grid;
  place-items: center;
  width: 30px;
  height: 20px;
  border-radius: 4px;
  font-size: 0.52rem;
  font-style: normal;
  font-weight: 800;
}

/* 右侧主区 */
.kb-main {
  min-width: 0;
}
.kb-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 42px;
  margin-bottom: 16px;
}
.kb-crumbs {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--muted);
  font-size: 0.78rem;
}
.kb-crumbs span:last-child {
  color: var(--ink);
  font-weight: 750;
}
.kb-crumb-sep {
  margin: 0 2px;
  color: var(--line);
  font-style: normal;
}
.kb-toolbar-actions {
  display: flex;
  gap: 8px;
}
.kb-btn {
  min-height: 34px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--surface);
  color: var(--ink);
  padding: 0 14px;
  font: inherit;
  font-size: 0.78rem;
  font-weight: 750;
  cursor: pointer;
}
.kb-btn:hover {
  border-color: var(--brand);
  color: var(--brand);
}
.kb-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.kb-btn-primary {
  border-color: var(--brand);
  background: var(--brand);
  color: #fff;
}
.kb-btn-primary:hover {
  background: #174a72;
  color: #fff;
}
.kb-section-head {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 2px 0 14px;
}
.kb-section-head h2 {
  margin: 0;
  color: var(--ink);
  font-size: 1.02rem;
  letter-spacing: -0.018em;
}
.kb-section-head span {
  color: var(--muted);
  font-size: 0.76rem;
}

/* 卡片布局 */
.kb-card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}
.kb-card-grid + .kb-card-grid {
  margin-top: 18px;
}
.kb-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 172px;
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  color: var(--ink);
  padding: 16px;
  text-align: left;
  cursor: pointer;
  font: inherit;
  transition: box-shadow 0.16s ease, transform 0.16s ease;
}
.kb-card:hover {
  box-shadow: 0 10px 24px rgb(43 39 35 / 0.1);
  transform: translateY(-2px);
}
.kb-card-folder {
  align-items: flex-start;
  justify-content: flex-start;
}
.kb-card-folder-ico {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 1.1rem;
  font-style: normal;
}
.kb-card-folder strong {
  font-size: 0.88rem;
  letter-spacing: -0.015em;
}
.kb-card-folder em {
  color: var(--muted);
  font-size: 0.7rem;
  font-style: normal;
}
.kb-file-ico {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 10px;
  font-size: 0.62rem;
  font-style: normal;
  font-weight: 800;
  letter-spacing: -0.01em;
}
.kb-file-ico-lg {
  width: 58px;
  height: 58px;
  font-size: 0.74rem;
}
.kb-card-doc-name {
  overflow: hidden;
  font-size: 0.82rem;
  font-weight: 750;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-card-doc-meta {
  color: var(--muted);
  font-size: 0.68rem;
}
.kb-card-doc-excerpt {
  overflow: hidden;
  color: var(--muted);
  font-size: 0.72rem;
  line-height: 1.55;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.kb-card-doc-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
}
.kb-card-doc-foot .kb-badge {
  margin-top: 0;
}
.kb-card-doc-foot time {
  margin-left: auto;
  color: var(--muted);
  font-size: 0.66rem;
}
.kb-badge {
  align-self: flex-start;
  margin-top: auto;
  border-radius: 999px;
  background: var(--brand-soft);
  color: var(--brand);
  padding: 2px 10px;
  font-size: 0.66rem;
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

/* 文档详情 */
.kb-doc-detail {
  border: 1px solid var(--line);
  border-radius: 12px;
  background: var(--surface);
  padding: 24px;
}
.kb-doc-detail-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--line-soft);
}
.kb-doc-detail-head h2 {
  margin: 0 0 8px;
  color: var(--ink);
  font-size: 1.05rem;
  letter-spacing: -0.02em;
}
.kb-meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0 0;
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

/* 新建弹窗 */
.kb-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: grid;
  place-items: center;
  background: rgb(43 39 35 / 0.35);
}
.kb-modal {
  display: grid;
  gap: 12px;
  width: 380px;
  border-radius: 14px;
  background: var(--surface);
  padding: 20px;
  box-shadow: 0 24px 60px rgb(43 39 35 / 0.25);
}
.kb-modal h3 {
  margin: 0;
  color: var(--ink);
  font-size: 1rem;
  letter-spacing: -0.015em;
}
.kb-modal input {
  min-height: 38px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: #fff;
  color: var(--ink);
  padding: 0 12px;
  font: inherit;
  font-size: 0.82rem;
  outline: none;
}
.kb-modal input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgb(31 93 142 / 0.12);
}
.kb-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}
</style>
