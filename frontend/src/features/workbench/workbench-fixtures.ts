import type { EvidenceReference, ProjectTodo, VerificationConclusion, VerificationTask } from '../../types/workbench'

// Development fixture. Replace each collection with its corresponding list endpoint when the backend contract is available.
export const projectTodos: ProjectTodo[] = [
  { id: 'payment', name: '支付平台重构', pendingCount: 8, approvalCount: 3, p0Count: 2, nextAction: '确认支付网关超时重试逻辑' },
  { id: 'risk', name: '风控引擎升级', pendingCount: 5, approvalCount: 2, p0Count: 1, nextAction: '复核静态扫描的高危发现' },
  { id: 'member', name: '会员中心改造', pendingCount: 3, approvalCount: 1, p0Count: 0, nextAction: '补充单元测试接口证据' },
  { id: 'data', name: '数据平台扩容', pendingCount: 2, approvalCount: 0, p0Count: 0, nextAction: '确认依赖升级的验收范围' },
]

export const verificationTasks: VerificationTask[] = [
  { id: 'task-payment', title: '支付流程重构核验', snapshot: 'snap_a1b2c3d4', analysisRun: '已完成', reportStatus: '待发布', riskSummary: '高风险 3 个', owner: '张伟', updatedAt: '2025-06-12 14:35' },
  { id: 'task-member', title: '用户中心权限核验', snapshot: 'snap_b2c3d4e5', analysisRun: '已完成', reportStatus: '待复核', riskSummary: '中风险 2 个', owner: '李娜', updatedAt: '2025-06-11 18:25' },
  { id: 'task-order', title: '订单服务异常处理检查', snapshot: 'snap_c3d4e5f6', analysisRun: '已完成', reportStatus: '已发布', riskSummary: '低风险 1 个', owner: '王磊', updatedAt: '2025-06-10 17:02' },
]

export const notebookEvidence: EvidenceReference[] = [
  { id: 'req-1', kind: '需求', title: '验收需求 v2.4', locator: '第 3.2 节 / 认证与权限管理', excerpt: '未登录访问应得到统一的未授权响应，且不泄露内部异常细节。', state: '已引用' },
  { id: 'code-1', kind: '代码', title: 'services/auth/login.ts', locator: 'commit 4e7b9c / hunk 18-46', excerpt: '认证失败统一映射为未授权响应，令牌生成逻辑未暴露给匿名请求。', state: '已引用' },
  { id: 'test-1', kind: '测试', title: '权限回归测试', locator: 'auth-regression.xml / case 12', excerpt: '12 个用例通过，退出状态为 0。', state: '已引用' },
  { id: 'manual-1', kind: '人工补证', title: '异常码兼容性说明', locator: '补证 #ME-028', excerpt: '待提交人补充外部客户端对旧异常码的兼容验证。', state: '待补充' },
]

export const notebookConclusions: VerificationConclusion[] = [
  { id: 'claim-1', requirement: '未登录访问应被拒绝且不泄露内部错误', status: '已确认', summary: '需求、代码提交与回归测试在当前输入快照中相互支持。', needsHumanDecision: false, risk: null, evidenceIds: ['req-1', 'code-1', 'test-1'] },
  { id: 'claim-2', requirement: '旧客户端应保持异常码兼容', status: '待人工确认', summary: '现有代码支持新映射，但缺少外部客户端兼容性结果。', needsHumanDecision: true, risk: 'P1', evidenceIds: ['req-1', 'code-1', 'manual-1'] },
  { id: 'claim-3', requirement: '超时重试不得重复扣款', status: '部分支持', summary: '代码路径已覆盖幂等键校验，跨网关超时场景仍需补充证据。', needsHumanDecision: true, risk: 'P0', evidenceIds: ['code-1', 'test-1'] },
]
