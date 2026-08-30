import { computed, ref } from 'vue'

export interface ProjectContextItem {
  id: string
  name: string
  description: string | null
  version: number
  created_at: string
}

const projectStorageKey = 'workbenchProjectId'

export const projects = ref<ProjectContextItem[]>([])
export const selectedProjectId = ref(sessionStorage.getItem(projectStorageKey) ?? '')
export const projectContextLoading = ref(false)
export const projectContextError = ref('')
export const selectedProject = computed(() => projects.value.find((project) => project.id === selectedProjectId.value) ?? null)

export function projectHeaders(write = false): HeadersInit {
  const headers: Record<string, string> = { Authorization: `Bearer ${sessionStorage.getItem('accessToken') ?? ''}` }
  if (write) {
    headers['Content-Type'] = 'application/json'
    headers['Idempotency-Key'] = crypto.randomUUID()
  }
  return headers
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, init)
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = typeof body.detail === 'string' ? body.detail : body.detail?.message
    throw new Error(body.message ?? detail ?? `请求失败 (${response.status})`)
  }
  return body as T
}

export function selectProject(projectId: string) {
  selectedProjectId.value = projectId
  if (projectId) sessionStorage.setItem(projectStorageKey, projectId)
  else sessionStorage.removeItem(projectStorageKey)
}

export async function loadProjects() {
  if (!sessionStorage.getItem('accessToken')) return
  projectContextLoading.value = true
  projectContextError.value = ''
  try {
    projects.value = await apiRequest<ProjectContextItem[]>('/projects', { headers: projectHeaders() })
    if (!projects.value.some((project) => project.id === selectedProjectId.value)) {
      selectProject(projects.value[0]?.id ?? '')
    }
  } catch (error) {
    projectContextError.value = error instanceof Error ? error.message : '项目列表加载失败'
    projects.value = []
    selectProject('')
  } finally {
    projectContextLoading.value = false
  }
}

export async function createProject(name: string, description = '', repositoryUrl = '', knowledgeBaseIds: string[] = []): Promise<ProjectContextItem> {
  const project = await apiRequest<ProjectContextItem>('/projects', {
    method: 'POST',
    headers: projectHeaders(true),
    body: JSON.stringify({ name, description: description || null, repository_url: repositoryUrl || null, knowledge_base_ids: knowledgeBaseIds }),
  })
  projects.value = [project, ...projects.value]
  selectProject(project.id)
  return project
}

export function resetProjectContext() {
  projects.value = []
  projectContextError.value = ''
  selectProject('')
}
