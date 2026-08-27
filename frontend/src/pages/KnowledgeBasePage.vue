<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  apiRequest,
  projectHeaders,
  selectedProjectId,
} from '../features/projects/project-context'

interface Folder {
  id: string
  project_id: string
  name: string
  parent_folder_id: string | null
  created_at: string
  updated_at: string
}

interface SourceDoc {
  id: string
  project_id: string
  logical_name: string
  source_role: string
  revision_no: number
  media_type: string
  original_filename: string
  processing_status: string
  parser_version: string | null
  failure_code: string | null
  ingestion_job_status: string | null
  folder_id: string | null
  force_ocr: boolean
  created_at: string
  updated_at: string
}

const folders = ref<Folder[]>([])
const sources = ref<SourceDoc[]>([])
const loading = ref(false)
const error = ref('')
const selectedFolderId = ref<string | null>(null)
const selectedDocId = ref<string | null>(null)

const expandedFolders = ref<Set<string>>(new Set())

const uploadModal = ref<{ file: File } | null>(null)
const uploadTargetFolderId = ref<string | null>(null)
const uploadForceOcr = ref(true)
const createFolderModal = ref(false)
const createFolderName = ref('')
const uploading = ref(false)

async function loadKnowledgeBase() {
  const projectId = selectedProjectId.value
  if (!projectId) {
    error.value = '请先在顶部选择项目'
    return
  }
  loading.value = true
  error.value = ''
  try {
    const [folderList, sourceList] = await Promise.all([
      apiRequest<Folder[]>(`/projects/${projectId}/knowledge-folders`, { headers: projectHeaders() }),
      apiRequest<SourceDoc[]>(`/projects/${projectId}/sources`, { headers: projectHeaders() }),
    ])
    folders.value = folderList
    sources.value = sourceList
  } catch (err) {
    error.value = err instanceof Error ? err.message : '知识库加载失败'
  } finally {
    loading.value = false
  }
}

function rootFolders(): Folder[] {
  return folders.value.filter((folder) => folder.parent_folder_id === null)
}

function childFolders(parentId: string | null): Folder[] {
  return folders.value.filter((folder) => folder.parent_folder_id === parentId)
}

function docsInFolder(folderId: string | null): SourceDoc[] {
  return sources.value.filter((source) => source.folder_id === folderId)
}

/** 判断一个文件夹是否应默认展开（有子内容且未被收起） */
function isExpanded(folderId: string) {
  return expandedFolders.value.has(folderId)
}

function selectFolder(id: string) {
  selectedFolderId.value = id
  selectedDocId.value = null
  expandedFolders.value.add(id)
}

function selectDoc(id: string) {
  selectedDocId.value = id
  selectedFolderId.value = null
}

const activeFolder = computed(() => folders.value.find((folder) => folder.id === selectedFolderId.value) ?? null)
const activeDoc = computed(() => sources.value.find((source) => source.id === selectedDocId.value) ?? null)

const folderPath = computed(() => {
  if (!activeFolder.value) return []
  const path: Folder[] = []
  let current: Folder | undefined = activeFolder.value
  let guard = 0
  while (current && guard < 50) {
    path.unshift(current)
    current = folders.value.find((folder) => folder.id === current?.parent_folder_id)
    guard += 1
  }
  return path.map((folder) => folder.name)
})

function extOf(name: string) {
  const match = name.match(/\.(\w+)$/)
  return (match?.[1] ?? 'PDF').toUpperCase()
}

const statusBadge: Record<string, string> = {
  UPLOADED: '待处理',
  PARSING: '处理中',
  OCR_CHECKING: '处理中',
  CHUNKING: '处理中',
  INDEXING: '处理中',
  READY: '已完成',
  FAILED: '失败',
}

function statusText(status: string) {
  return statusBadge[status] ?? status
}

function openUploadDialog() {
  const input = document.createElement('input')
  input.type = 'file'
  input.onchange = () => {
    const file = input.files?.[0]
    if (file) {
      uploadTargetFolderId.value = selectedFolderId.value
      uploadForceOcr.value = true
      uploadModal.value = { file }
    }
  }
  input.click()
}

async function confirmUpload() {
  if (!uploadModal.value || uploading.value) return
  const file = uploadModal.value.file
  const projectId = selectedProjectId.value
  if (!projectId) return
  uploading.value = true
  error.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('source_role', '知识库')
    formData.append('logical_name', file.name)
    if (uploadTargetFolderId.value) formData.append('folder_id', uploadTargetFolderId.value)
    formData.append('force_ocr', uploadForceOcr.value ? 'true' : 'false')
    await apiRequest(`/projects/${projectId}/sources`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${sessionStorage.getItem('accessToken') ?? ''}`,
        'Idempotency-Key': crypto.randomUUID(),
      },
      body: formData,
    })
    await loadKnowledgeBase()
    uploadModal.value = null
  } catch (err) {
    error.value = err instanceof Error ? err.message : `上传失败 (${file.name})`
  } finally {
    uploading.value = false
  }
}

async function confirmCreateFolder() {
  const projectId = selectedProjectId.value
  if (!projectId) return
  const name = createFolderName.value.trim()
  if (!name) return
  try {
    await apiRequest(`/projects/${projectId}/knowledge-folders`, {
      method: 'POST',
      headers: projectHeaders(true),
      body: JSON.stringify({
        name,
        parent_folder_id: selectedFolderId.value,
      }),
    })
    createFolderName.value = ''
    createFolderModal.value = false
    await loadKnowledgeBase()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '新建文件夹失败'
  }
}

async function deleteDoc(doc: SourceDoc) {
  const projectId = selectedProjectId.value
  if (!projectId) return
  if (!confirm(`确定删除「${doc.logical_name}」？`)) return
  try {
    await apiRequest(`/projects/${projectId}/sources/${doc.id}`, {
      method: 'DELETE',
      headers: projectHeaders(true),
    })
    if (selectedDocId.value === doc.id) selectedDocId.value = null
    await loadKnowledgeBase()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败'
  }
}

async function deleteFolder(folder: Folder) {
  const projectId = selectedProjectId.value
  if (!projectId) return
  if (!confirm(`确定删除文件夹「${folder.name}」及其全部内容？`)) return
  try {
    await apiRequest(`/projects/${projectId}/knowledge-folders/${folder.id}`, {
      method: 'DELETE',
      headers: projectHeaders(true),
    })
    selectedFolderId.value = null
    await loadKnowledgeBase()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '删除失败'
  }
}

onMounted(loadKnowledgeBase)
</script>

<template>
  <section class="page page-knowledge">
    <header class="page-heading">
      <div><h1>项目知识库</h1><p>上传资料、按文件夹组织知识文档，MinerU 解析并建立可核验索引。</p></div>
      <button v-if="error" class="kb-retry" type="button" @click="loadKnowledgeBase">重试</button>
    </header>

    <div v-if="error && !loading" class="kb-error">{{ error }}</div>

    <div class="kb-layout">
      <!-- 左侧：文件夹树 -->
      <aside class="kb-sidebar">
        <button class="kb-create" type="button" @click="createFolderModal = true">＋ 新建文件夹</button>
        <div class="kb-tree-label">文件夹</div>
        <nav class="kb-tree">
          <div v-for="folder in rootFolders()" :key="folder.id" class="kb-node">
            <button class="kb-node-row" :class="{ active: selectedFolderId === folder.id && !selectedDocId }" type="button" @click="selectFolder(folder.id)">
              <span :class="['kb-caret', !isExpanded(folder.id) ? 'collapsed' : '']">▾</span>
              <i class="kb-folder-ico plain">▤</i>
              <span class="kb-node-name">{{ folder.name }}</span>
              <button class="kb-del-mini" type="button" @click.stop="deleteFolder(folder)">×</button>
            </button>
            <div v-if="isExpanded(folder.id)" class="kb-node-children">
              <div v-for="child in childFolders(folder.id)" :key="child.id" class="kb-node">
                <button class="kb-node-row" :class="{ active: selectedFolderId === child.id && !selectedDocId }" type="button" @click="selectFolder(child.id)">
                  <span :class="['kb-caret', !isExpanded(child.id) ? 'collapsed' : '']">▾</span>
                  <i class="kb-folder-ico plain">▤</i>
                  <span class="kb-node-name">{{ child.name }}</span>
                  <button class="kb-del-mini" type="button" @click.stop="deleteFolder(child)">×</button>
                </button>
                <div v-if="isExpanded(child.id)" class="kb-node-children">
                  <button
                    v-for="doc in docsInFolder(child.id)"
                    :key="doc.id"
                    class="kb-node-row kb-node-doc"
                    :class="{ active: selectedDocId === doc.id }"
                    type="button"
                    @click="selectDoc(doc.id)"
                  >
                    <i class="kb-doc-dot">{{ extOf(doc.logical_name) }}</i>
                    <span class="kb-node-name">{{ doc.logical_name }}</span>
                  </button>
                </div>
              </div>
              <button
                v-for="doc in docsInFolder(folder.id)"
                :key="doc.id"
                class="kb-node-row kb-node-doc"
                :class="{ active: selectedDocId === doc.id }"
                type="button"
                @click="selectDoc(doc.id)"
              >
                <i class="kb-doc-dot">{{ extOf(doc.logical_name) }}</i>
                <span class="kb-node-name">{{ doc.logical_name }}</span>
              </button>
            </div>
          </div>
          <!-- 未分组（根级）文档 -->
          <div v-if="docsInFolder(null).length && !rootFolders().length" class="kb-tree-label">未分组文档</div>
          <button
            v-for="doc in docsInFolder(null)"
            v-show="rootFolders().length === 0"
            :key="doc.id"
            class="kb-node-row kb-node-doc"
            :class="{ active: selectedDocId === doc.id }"
            type="button"
            @click="selectDoc(doc.id)"
          >
            <i class="kb-doc-dot">{{ extOf(doc.logical_name) }}</i>
            <span class="kb-node-name">{{ doc.logical_name }}</span>
          </button>
        </nav>
      </aside>

      <!-- 右侧：内容区 -->
      <section class="kb-main">
        <div class="kb-toolbar">
          <nav class="kb-crumbs">
            <template v-for="(crumb, index) in folderPath" :key="index">
              <i v-if="index > 0" class="kb-crumb-sep">/</i>{{ crumb }}
            </template>
          </nav>
          <div class="kb-toolbar-actions">
            <button class="kb-btn" type="button" @click="createFolderModal = true">＋ 新建文件夹</button>
            <button class="kb-btn kb-btn-primary" type="button" @click="openUploadDialog">＋ 上传文档</button>
          </div>
        </div>

        <!-- 选中文件夹：文档卡片 -->
        <template v-if="selectedFolderId && activeFolder">
          <div class="kb-section-head"><h2>{{ activeFolder.name }}</h2></div>
          <div v-if="docsInFolder(activeFolder.id).length" class="kb-card-grid">
            <div v-for="doc in docsInFolder(activeFolder.id)" :key="doc.id" class="kb-card kb-card-doc" :class="{ selected: selectedDocId === doc.id }" role="button" tabindex="0" @click="selectDoc(doc.id)" @keyup.enter="selectDoc(doc.id)">
              <i class="kb-file-ico">{{ extOf(doc.logical_name) }}</i>
              <span class="kb-card-doc-name">{{ doc.logical_name }}</span>
              <span class="kb-card-doc-excerpt">{{ doc.media_type }}</span>
              <span class="kb-card-doc-meta">{{ doc.parser_version || '—' }} · {{ doc.force_ocr ? 'OCR' : '文本' }}</span>
              <span class="kb-card-doc-foot">
                <span :class="['kb-badge', doc.processing_status]">{{ statusText(doc.processing_status) }}</span>
                <button class="kb-del" type="button" @click.stop="deleteDoc(doc)">删除</button>
              </span>
            </div>
          </div>
          <div v-else class="kb-empty">该文件夹为空，点击右上「上传文档」添加。</div>
        </template>

        <!-- 未选中文件夹：根级文档 -->
        <template v-else>
          <div class="kb-section-head"><h2>当前项目</h2></div>
          <div v-if="docsInFolder(null).length" class="kb-card-grid">
            <div v-for="doc in docsInFolder(null)" :key="doc.id" class="kb-card kb-card-doc" :class="{ selected: selectedDocId === doc.id }" role="button" tabindex="0" @click="selectDoc(doc.id)" @keyup.enter="selectDoc(doc.id)">
              <i class="kb-file-ico">{{ extOf(doc.logical_name) }}</i>
              <span class="kb-card-doc-name">{{ doc.logical_name }}</span>
              <span class="kb-card-doc-excerpt">{{ doc.media_type }}</span>
              <span class="kb-card-doc-meta">{{ doc.parser_version || '—' }} · {{ doc.force_ocr ? 'OCR' : '文本' }}</span>
              <span class="kb-card-doc-foot">
                <span :class="['kb-badge', doc.processing_status]">{{ statusText(doc.processing_status) }}</span>
                <button class="kb-del" type="button" @click.stop="deleteDoc(doc)">删除</button>
              </span>
            </div>
          </div>
          <div v-else class="kb-empty">还没有文档。点击右上「上传文档」开始建立知识库。</div>
        </template>
      </section>
    </div>

    <!-- 上传弹窗 -->
    <div v-if="uploadModal" class="kb-modal-overlay" @click.self="uploadModal = null">
      <div class="kb-modal" role="dialog" aria-label="上传文档">
        <h3>上传文档</h3>
        <p class="kb-modal-file">{{ uploadModal.file.name }}</p>
        <p class="kb-modal-target">目标文件夹：{{ activeFolder?.name ?? '项目根级' }}</p>
        <label class="kb-upload-option">
          <input v-model="uploadForceOcr" type="checkbox" />
          <span>OCR 识别（扫描件/图片 PDF 建议开启）</span>
        </label>
        <div class="kb-modal-actions">
          <button class="kb-btn" type="button" @click="uploadModal = null">取消</button>
          <button class="kb-btn kb-btn-primary" type="button" :disabled="uploading" @click="confirmUpload">{{ uploading ? '上传中…' : '上传' }}</button>
        </div>
      </div>
    </div>

    <!-- 新建文件夹弹窗 -->
    <div v-if="createFolderModal" class="kb-modal-overlay" @click.self="createFolderModal = false">
      <div class="kb-modal" role="dialog" aria-label="新建文件夹">
        <h3>新建文件夹</h3>
        <input v-model="createFolderName" placeholder="输入文件夹名称" @keyup.enter="confirmCreateFolder" />
        <div class="kb-modal-actions">
          <button class="kb-btn" type="button" @click="createFolderModal = false">取消</button>
          <button class="kb-btn kb-btn-primary" type="button" :disabled="!createFolderName.trim()" @click="confirmCreateFolder">创建</button>
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
.kb-folder-ico.plain {
  background: rgb(118 110 104 / 0.22);
  color: var(--muted);
  font-size: 0.72rem;
}
.kb-node-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1 1 auto;
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
  background: rgb(118 110 104 / 0.16);
  color: var(--muted);
  font-size: 0.52rem;
  font-style: normal;
  font-weight: 800;
}
.kb-del-mini {
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: 0.85rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0;
}
.kb-node-row:hover .kb-del-mini {
  opacity: 1;
}
.kb-del-mini:hover {
  color: #a33;
}
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
.kb-card-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
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
.kb-card.selected {
  border-color: var(--brand);
}
.kb-file-ico {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  border-radius: 10px;
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 0.62rem;
  font-style: normal;
  font-weight: 800;
  letter-spacing: -0.01em;
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
.kb-badge.READY {
  background: rgb(82 115 96 / 0.14);
  color: var(--success);
}
.kb-badge.FAILED {
  background: rgb(162 68 53 / 0.14);
  color: #a33;
}
.kb-badge.UPLOADED,
.kb-badge.PARSING,
.kb-badge.OCR_CHECKING,
.kb-badge.CHUNKING,
.kb-badge.INDEXING {
  background: rgb(152 102 26 / 0.14);
  color: var(--warning);
}
.kb-del {
  margin-left: auto;
  border: 1px solid var(--line);
  border-radius: 7px;
  background: transparent;
  color: var(--muted);
  padding: 2px 10px;
  font: inherit;
  font-size: 0.68rem;
  cursor: pointer;
}
.kb-del:hover {
  border-color: #a33;
  color: #a33;
}
.kb-empty {
  color: var(--muted);
  font-size: 0.82rem;
  padding: 40px 0;
  text-align: center;
}
.kb-error {
  margin-bottom: 12px;
  border: 1px solid rgb(162 68 53 / 0.3);
  border-radius: 10px;
  background: rgb(162 68 53 / 0.08);
  color: #a33;
  padding: 10px 14px;
  font-size: 0.8rem;
}
.kb-retry {
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: var(--ink);
  padding: 4px 12px;
  font: inherit;
  font-size: 0.75rem;
  cursor: pointer;
}
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
.kb-modal input[type="text"],
.kb-modal > input {
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
.kb-modal > input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgb(31 93 142 / 0.12);
}
.kb-modal-file {
  margin: 0;
  color: var(--ink);
  font-size: 0.84rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.kb-modal-target {
  margin: 0;
  color: var(--muted);
  font-size: 0.78rem;
}
.kb-upload-option {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink);
  font-size: 0.82rem;
  cursor: pointer;
}
.kb-upload-option input {
  width: 16px;
  height: 16px;
}
.kb-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
}
</style>
