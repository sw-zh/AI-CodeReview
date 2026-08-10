# 架构设计发现

## 2026-08-10 总体方向规划发现

- 已确认的新方向文档将产品拆为交付核验、项目态势与研发总结、安全与质量治理三条业务线，共用项目、来源、快照、证据与正式记录。
- 当前实现已经具备固定双核、交付核验 Git Diff、冻结编排、外围 Agent 的受控 Prompt/只读工具、报告草稿、人工审批链和真实运行详情。
- 目标架构要求后续新增运行配置类型、外部来源镜像、研发事项/交付项、关联关系、项目态势快照、安全基线和多类型正式记录。
- 当前实现与目标架构最关键的冲突是：Git Snapshot 被全部分析运行全局强制；后续必须只在交付核验配置中强制。

## 2026-08-10 当前实现审计

- `analysis_service.start_analysis_run` 要求正式快照且必须存在 `InputSnapshotGit`；`snapshot_service` 冻结正式快照时也强制写入 Git 绑定。因此项目总结、安全基线目前无法作为独立运行启动。
- `verification_graph`、报告服务和现有 `VerificationTask -> VerificationCycle -> InputSnapshot -> AnalysisRun -> ReportVersion -> PublishedRecord` 语义均围绕单次正式交付核验构建，应保留该链但不能直接承担项目态势或安全基线。
- 编排服务固定 `requirement-claim-core`、`delivery-git-diff`、`evidence-reconciliation` 三个必经节点；默认模板名称和任务绑定也明确为“默认交付核验”。这是正确基础，但必须增加按运行配置验证模板的能力，不能继续对所有模板使用同一必经集合。
- 数据模型已有来源版本、Git 快照、外部 CI/构建证据、手工证据、风险、Coverage、报告与发布记录；尚无外部连接/同步、外部事项镜像、交付项、关联关系、项目态势快照和安全基线专用对象。
- 前端有任务、交付历史、审批、知识库、Agent 功能块和 Notebook 页面；任务中心、工作台、审批和交付历史仍主要依赖 fixtures，知识库和 Agent 功能块要求用户粘贴项目 UUID，尚未形成真实项目到事项到运行的导航链。
- API 现状只有项目创建/读取、资料、Git 仓库与快照、核验任务、分析、报告、审批和编排端点；不存在项目列表、外部连接、同步、事项、关联、态势或安全基线端点。
- Worker 固定调用 `run_verification_graph`，运行完成后依照现有核验结果更新轮次状态并生成报告草稿；未来的项目态势和安全基线必须有独立 workflow/worker dispatch，而不是塞进该图。
- 当前数据库迁移最新为 `015_dual_core_agent_orchestration.py`。后续扩展应使用追加迁移、保留既有交付核验历史，不能重写或复用历史快照与报告语义。

## 2026-08-10 运行范围切片实现审计

- `InputSnapshot` 目前只有 `purpose`，`AnalysisRun`、`OrchestrationTemplate`、`ReportVersion` 与 `PublishedRecord` 都没有运行配置/记录类型字段。
- `freeze_formal_snapshot` 将 Git SHA/Diff 纳入正式快照哈希，并总是创建 `InputSnapshotGit`；该逻辑应明确为交付核验专用函数和 Profile 校验。
- `start_analysis_run` 固定工作流为 `dual-core-v1`，固定调用编排指纹，也只允许含 Git 的正式快照；应将其改为 Profile 分发入口，但本切片只允许执行 `DELIVERY_VERIFICATION`。
- 现有历史数据可安全兼容：新增列的数据库默认值和非空约束均使用 `DELIVERY_VERIFICATION`，不会改变现有输入快照、报告内容哈希或记录哈希。
- Profile 字段将落在 `InputSnapshot`、`AnalysisRun`、`OrchestrationTemplate`、`AnalysisRunOrchestrationSnapshot`、`ReportVersion` 和 `PublishedRecord`；现有列与哈希不重算，新增字段由迁移默认值兼容。
- 对外响应需要显示快照和运行的 Profile；新建编排模板的请求可以声明 Profile，但本切片只允许创建和绑定 `DELIVERY_VERIFICATION` 模板，防止未实现外围 workflow 被提前启用。
- Worker 应保留单独的 Profile dispatcher：当前仅路由 `DELIVERY_VERIFICATION` 到既有 `run_verification_graph`，其他值一律报明确的“未开放”领域错误。

## 2026-08-10 运行范围切片已实施内容

- 已新增 `AssessmentProfile` 及 016 追加迁移：历史数据通过默认 `DELIVERY_VERIFICATION` 保持原有语义。
- 已将 Profile 写入快照、运行、模板、运行编排快照、报告和正式记录；新的交付快照哈希显式包含该 Profile。
- 已将 Git 范围约束改为交付核验专用校验，并加入未开放 Profile 的显式拒绝逻辑；Worker 使用 Profile dispatcher 且当前只路由到既有双核图。

## 2026-08-10 外部来源切片审计

- 当前仓库远端为 GitHub，因此首个实际 Git 平台适配器确定为 GitHub；适配器仍只读，不执行 Webhook、写操作或仓库代码。
- 现有 `GitRepository` 只服务本地只读 Git Diff，不能承载 Issue、PR 或 Milestone 的远程元数据；需要独立的来源连接和资源版本模型。
- 已有 `SourceRevision` 是项目文档的版本化证据来源。新交付项模型将为后续文档关联预留关系，不复制文档内容或用本系统手工文本覆盖外部事实。
- `agent_tool_runner` 的 HTTP 能力不适合承担正式来源同步：其结果是运行期临时工具证据，且 URL 由 Agent 模板配置。GitHub 同步必须走独立的服务端连接适配器、凭据引用和同步审计。

## 2026-08-10 开发方案结论

- 实施必须先完成运行配置与快照规则收敛，再建立外部来源和交付项；项目态势、安全基线、真实工作台均不能跳过这两个前置层。
- 建议拆为七个独立提交切片：运行范围、来源同步、事项关联、项目态势、安全质量、工作台导航、工具证据收口。
- 首个实际外部 Git 平台适配器的提供方仍需以项目实际使用的平台为准；这不影响先行的数据模型与适配器接口设计。

## 仓库现状

- 仓库已初始化，当前分支为 `main`，暂无提交。
- `origin` 指向 `https://github.com/yyy2045/one.git`。
- 当前没有现有代码、架构文档或仓库级 `AGENTS.md` 需要兼容。

## 架构审查结论

- 当前产品方向成立，关键卖点是多源证据核验、受控 AI 编排和人工审批闭环。
- 下一次完整架构设计必须优先固定不可变输入快照、证据引用、三类独立状态机、持久异步执行、权限审批和失败恢复。
- 不能通过增加框架代替领域边界设计；首版保持模块化单体。
- 完整架构设计应明确哪些内容已固定、哪些仍需决策，以及每项决策的验收标准。

## 最终文档结构

- 采用“模块化单体 + 独立 Worker + PostgreSQL Job”。
- 固定核心数据主链、不可变快照、四套状态机、证据协议、LangGraph 边界、权限审批和失败恢复。
- 下一次对话必须产出一份完整架构文档和一份一个月实现计划，并通过端到端一致性走查与验收清单。
- 使用默认值关闭非关键歧义；只有真实仓库冲突、覆盖风险或权限阻塞才停下询问。
