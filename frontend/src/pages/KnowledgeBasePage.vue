<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { apiRequest as request, projectHeaders as headers, selectedProject, selectedProjectId } from '../features/projects/project-context'

interface SourceItem {
  id: string
  project_id: string
  logical_name: string
  source_role: string
  revision_no: number
  content_hash: string
  media_type: string
  processing_status: string
  parser_version: string | null
  in_snapshot: boolean
  created_at: string
  updated_at: string
}

const projectId = selectedProjectId
const sources = ref<SourceItem[]>([])
const selectedType = ref('全部')
const busy = ref(false)
const message = ref('选择项目后加载可被核验的资料版本。')

const viewingSource = ref<SourceItem | null>(null)
const viewingContent = ref('')

const typeOptions = computed(() => {
  const types = [...new Set(sources.value.map((s) => s.source_role))]
  return ['全部', ...types.sort()]
})

const visibleSources = computed(() =>
  selectedType.value === '全部'
    ? sources.value
    : sources.value.filter((s) => s.source_role === selectedType.value),
)

async function fetchSources() {
  if (!projectId.value) return
  busy.value = true
  try {
    sources.value = await request<SourceItem[]>(`/projects/${projectId.value}/sources`, { headers: headers() })
    message.value = sources.value.length ? `共 ${sources.value.length} 份资料` : '该项目下暂无已上传的资料。'
  } catch (error) {
    message.value = error instanceof Error ? error.message : '加载失败'
  } finally {
    busy.value = false
  }
}

async function viewContent(source: SourceItem) {
  viewingSource.value = source
  busy.value = true
  try {
    const result = await request<{ content: string }>(`/projects/${projectId.value}/sources/${source.id}`, { headers: headers() })
    viewingContent.value = result.content
  } catch (error) {
    viewingContent.value = '加载原文失败：' + (error instanceof Error ? error.message : '未知错误')
  } finally {
    busy.value = false
  }
}

function closeViewer() {
  viewingSource.value = null
  viewingContent.value = ''
}

watch(projectId, () => { void fetchSources() }, { immediate: true })
</script>

<template>
  <section class="page page-knowledge">
    <header class="page-heading">
      <div>
        <h1>项目知识库</h1>
        <p v-if="selectedProject">{{ selectedProject.name }}：按资料类型、版本与快照引用关系管理可被核验的输入。</p>
        <p v-else>请先在项目概览创建或选择项目。</p>
      </div>
      <button class="primary-button" type="button" :disabled="busy || !projectId" @click="fetchSources">刷新资料</button>
    </header>

    <div class="knowledge-layout">
      <aside class="surface type-rail">
        <h2>资料类型</h2>
        <button
          v-for="type in typeOptions"
          :key="type"
          type="button"
          :class="{ active: selectedType === type }"
          @click="selectedType = type"
        >{{ type }}</button>
      </aside>

      <section class="surface knowledge-list">
        <div class="filter-row">
          <span>{{ message }}</span>
        </div>
        <div class="data-table knowledge-table">
          <div class="table-row table-header">
            <span>文档名称</span><span>类型</span><span>版本</span><span>处理状态</span><span>快照引用</span><span>更新时间</span>
          </div>
          <button
            v-for="source in visibleSources"
            :key="source.id"
            class="table-row table-button"
            type="button"
            @click="viewContent(source)"
          >
            <strong>{{ source.logical_name }}</strong>
            <span>{{ source.source_role }}</span>
            <span>v{{ source.revision_no }}</span>
            <span>{{ source.processing_status }}</span>
            <span>{{ source.in_snapshot ? '是' : '否' }}</span>
            <time>{{ new Date(source.updated_at).toLocaleString('zh-CN') }}</time>
          </button>
        </div>
      </section>
    </div>

    <!-- content viewer overlay -->
    <Teleport to="body">
      <div v-if="viewingSource" class="content-overlay" @click.self="closeViewer">
        <div class="content-modal">
          <header class="content-modal-header">
            <div>
              <strong>{{ viewingSource.logical_name }}</strong>
              <small>v{{ viewingSource.revision_no }} · {{ viewingSource.source_role }} · {{ viewingSource.processing_status }}</small>
            </div>
            <button type="button" @click="closeViewer" aria-label="关闭">✕</button>
          </header>
          <pre class="content-modal-body">{{ viewingContent }}</pre>
        </div>
      </div>
    </Teleport>
  </section>
</template>
