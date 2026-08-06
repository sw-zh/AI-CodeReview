import { createRouter, createWebHistory } from 'vue-router'
import WorkbenchLayout from '../layouts/WorkbenchLayout.vue'
import ApprovalDetailPage from '../pages/ApprovalDetailPage.vue'
import ApprovalQueuePage from '../pages/ApprovalQueuePage.vue'
import DeliveryDetailPage from '../pages/DeliveryDetailPage.vue'
import DeliveryHistoryPage from '../pages/DeliveryHistoryPage.vue'
import IntegrationsSettingsPage from '../pages/IntegrationsSettingsPage.vue'
import KnowledgeBasePage from '../pages/KnowledgeBasePage.vue'
import NotebookWorkspacePage from '../pages/NotebookWorkspacePage.vue'
import TaskCenterPage from '../pages/TaskCenterPage.vue'
import WorkbenchHomePage from '../pages/WorkbenchHomePage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [{ path: '/', component: WorkbenchLayout, children: [
    { path: '', redirect: '/workbench' },
    { path: 'workbench', component: WorkbenchHomePage, meta: { title: '工作台', area: 'project' } },
    { path: 'knowledge-base', component: KnowledgeBasePage, meta: { title: '项目知识库', area: 'project' } },
    { path: 'tasks', component: TaskCenterPage, meta: { title: '任务中心', area: 'project' } },
    { path: 'tasks/:taskId/notebook', component: NotebookWorkspacePage, meta: { title: 'Notebook 审查', area: 'project', section: 'notebook' } },
    { path: 'approvals', component: ApprovalQueuePage, meta: { title: '待审批队列', area: 'approval' } },
    { path: 'approvals/:approvalId', component: ApprovalDetailPage, meta: { title: '审批详情', area: 'approval' } },
    { path: 'deliveries', component: DeliveryHistoryPage, meta: { title: '交付历史', area: 'project' } },
    { path: 'deliveries/:deliveryId', component: DeliveryDetailPage, meta: { title: '交付详情', area: 'project' } },
    { path: 'settings', component: IntegrationsSettingsPage, meta: { title: '集成与设置', area: 'settings' } },
  ] }],
})
