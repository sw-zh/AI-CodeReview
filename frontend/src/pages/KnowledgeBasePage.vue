<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { apiRequest as request, projectHeaders as headers, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface SourceItem {
  id: string
  project_id: string
  logical_name: string
  source_role: string
  revision_no: number
  content_hash: string
  media_type: string
  original_filename: string
  processing_status: string
  parser_version: string | null
  failure_code: string | null
  ocr_confidence: number | null
  extraction_metadata: Record<string, unknown>
  ingestion_job_status: string | null
  in_snapshot: boolean
  created_at: string
  updated_at: string
}

const projectId = selectedProjectId
const sources = ref<SourceItem[]>([])
const selectedType = ref('全部')
const busy = ref(false)
const message = ref('选择项目后加载可被核验的知识版本。')
const viewingSource = ref<SourceItem | null>(null)
const viewingContent = ref('')
const uploadFiles = ref<File[]>([])
const uploadRole = ref('验收资料')
const uploadName = ref('')
let pollTimer: number | undefined

const acceptedFormats = '.txt,.md,.csv,.json,.yaml,.yml,.xml,.html,.htm,.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.odt,.ods,.odp,.png,.jpg,.jpeg,.webp,.tif,.tiff'
const pendingStatuses = new Set(['UPLOADED', 'PARSING', 'OCR_CHECKING', 'CHUNKING', 'INDEXING'])

const typeOptions = computed(() => ['全部', ...new Set(sources.value.map((source) => source.source_role))].sort())
const visibleSources = computed(() => selectedType.value === '全部' ? sources.value : sources.value.filter((source) => source.source_role === selectedType.value))

function formatName(source: SourceItem) {
  return source.media_type.split('/').at(-1)?.replace('vnd.', '') || source.media_type
}

function sourceStatus(source: SourceItem) {
  if (source.processing_status === 'FAILED') return `${source.failure_code ?? '导入失败'}：请查看失败原因后重新导入或补充人工证据`
  if (source.ingestion_job_status === 'QUEUED' && source.failure_code) return `正在重试（${source.failure_code}）；仍不可进入正式快照`
  if (source.processing_status === 'READY' && source.extraction_metadata.indexing && typeof source.extraction_metadata.indexing === 'object' && (source.extraction_metadata.indexing as { status?: string }).status === 'UNAVAILABLE') {
    return 'READY · 已提取并可冻结；向量索引暂不可用，将按关键词检索'
  }
  if (source.ocr_confidence != null) return `${source.processing_status} · OCR ${source.ocr_confidence.toFixed(1)}%`
  return source.processing_status
}

function schedulePolling() {
  window.clearInterval(pollTimer)
  if (sources.value.some((source) => pendingStatuses.has(source.processing_status))) pollTimer = window.setInterval(() => void fetchSources(), 3000)
}

async function fetchSources() {
  if (!projectId.value) return
  busy.value = true
  try {
    sources.value = await request<SourceItem[]>(`/projects/${projectId.value}/sources`, { headers: headers() })
    message.value = sources.value.length ? `共 ${sources.value.length} 条项目知识；仅 READY 版本可进入 Notebook 正式快照。` : '该项目下暂无知识内容。可通过“导入知识”补充文档、表格、演示稿、PDF 或图片。'
  } catch (error) {
    message.value = error instanceof Error ? error.message : '加载知识库失败'
  } finally {
    busy.value = false
    schedulePolling()
  }
}

async function viewContent(source: SourceItem) {
  viewingSource.value = source
  if (source.processing_status !== 'READY') {
    viewingContent.value = source.processing_status === 'FAILED' ? `${source.failure_code ?? 'SOURCE_INGESTION_FAILED'}：该知识未能可靠提取，不能用于正式快照。` : '知识仍在处理，完成到 READY 后可查看提取文本与证据定位。'
    return
  }
  busy.value = true
  try {
    const result = await request<{ content: string }>(`/projects/${projectId.value}/sources/${source.id}`, { headers: headers() })
    viewingContent.value = result.content
  } catch (error) {
    viewingContent.value = '加载提取文本失败：' + (error instanceof Error ? error.message : '未知错误')
  } finally {
    busy.value = false
  }
}

function closeViewer() {
  viewingSource.value = null
  viewingContent.value = ''
}

function selectFiles(event: Event) {
  uploadFiles.value = Array.from((event.target as HTMLInputElement).files ?? [])
  if (uploadFiles.value.length === 1 && !uploadName.value) uploadName.value = uploadFiles.value[0].name.replace(/\.[^.]+$/, '')
}

async function uploadSources() {
  if (!projectId.value || !uploadFiles.value.length) return
  busy.value = true
  const failures: string[] = []
  try {
    for (const file of uploadFiles.value) {
      const form = new FormData()
      form.append('file', file)
      form.append('source_role', uploadRole.value.trim() || '验收资料')
      form.append('logical_name', uploadFiles.value.length === 1 ? uploadName.value.trim() || file.name : file.name)
      try {
        await request(`/projects/${projectId.value}/sources`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${sessionStorage.getItem('accessToken') ?? ''}`, 'Idempotency-Key': crypto.randomUUID() },
          body: form,
        })
      } catch (error) {
        failures.push(`${file.name}：${error instanceof Error ? error.message : '导入请求失败'}`)
      }
    }
    uploadFiles.value = []
    uploadName.value = ''
    message.value = failures.length ? failures.join('；') : '知识已进入受控解析队列；处理、OCR 与索引成功后才会显示为 READY。'
    await fetchSources()
  } finally {
    busy.value = false
  }
}

watch(projectId, () => void fetchSources(), { immediate: true })
onUnmounted(() => window.clearInterval(pollTimer))
</script>

<template>
  <section class="page page-knowledge">
    <header class="page-heading">
      <div>
        <h1>项目知识库</h1>
        <p v-if="selectedProject">{{ selectedProject.name }}：按知识类型、来源、版本与快照引用关系管理可被核验的输入。</p>
        <p v-else>请先在项目概览创建或选择项目。</p>
      </div>
      <button class="primary-button" type="button" :disabled="busy || !projectId" @click="fetchSources">刷新知识</button>
    </header>

    <div class="knowledge-layout">
      <aside class="surface type-rail">
        <h2>知识分类</h2>
        <button v-for="type in typeOptions" :key="type" type="button" :class="{ active: selectedType === type }" @click="selectedType = type">{{ type }}</button>
      </aside>

      <section class="surface knowledge-list">
        <p class="knowledge-source-message">{{ message }}</p>
        <details class="knowledge-import">
          <summary>导入知识 <small>支持常见文档、表格、演示稿、PDF 与图片 OCR</small></summary>
          <form class="agent-form" @submit.prevent="uploadSources">
            <p class="agent-form-note">不会执行宏、脚本或外部链接；加密文件、压缩包、音视频不支持。OCR 置信度不足的内容不能进入正式快照。</p>
            <div class="agent-form-grid"><label>知识分类<input v-model="uploadRole" maxlength="64" placeholder="例如：验收资料" /></label><label>显示名称<input v-model="uploadName" :disabled="uploadFiles.length !== 1" maxlength="255" placeholder="单文件可自定义，批量使用文件名" /></label><label>选择文件<input type="file" :accept="acceptedFormats" multiple :disabled="busy" @change="selectFiles" /></label></div>
            <button class="primary-button" type="submit" :disabled="busy || !projectId || !uploadFiles.length">导入 {{ uploadFiles.length ? `${uploadFiles.length} 份知识` : '知识' }}</button>
          </form>
        </details>
        <div class="data-table knowledge-table knowledge-table-expanded">
          <div class="table-row table-header"><span>知识名称</span><span>分类 / 格式</span><span>版本</span><span>处理状态</span><span>快照引用</span><span>更新时间</span></div>
          <button v-for="source in visibleSources" :key="source.id" class="table-row table-button" type="button" @click="viewContent(source)">
            <strong>{{ source.logical_name }}<small>{{ source.original_filename }}</small></strong>
            <span>{{ source.source_role }}<small>{{ formatName(source) }}</small></span>
            <span>v{{ source.revision_no }}</span>
            <span :class="{ 'source-failed': source.processing_status === 'FAILED' }">{{ sourceStatus(source) }}</span>
            <span>{{ source.in_snapshot ? '已冻结' : '未冻结' }}</span>
            <time>{{ new Date(source.updated_at).toLocaleString('zh-CN') }}</time>
          </button>
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="viewingSource" class="content-overlay" @click.self="closeViewer">
        <div class="content-modal">
          <header class="content-modal-header"><div><strong>{{ viewingSource.logical_name }}</strong><small>v{{ viewingSource.revision_no }} · {{ viewingSource.processing_status }} · {{ viewingSource.parser_version ?? '等待提取' }}</small></div><button type="button" @click="closeViewer" aria-label="关闭">✕</button></header>
          <p v-if="viewingSource.ocr_confidence != null" class="content-modal-meta">OCR 置信度：{{ viewingSource.ocr_confidence.toFixed(1) }}%</p>
          <pre class="content-modal-body">{{ viewingContent }}</pre>
        </div>
      </div>
    </Teleport>
  </section>
</template>
