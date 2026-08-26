# AI-CodeReview 双人协作开发功能清单与承接上下文

> 审查日期：2026-08-24
> 审查基线：`main@4b13ded` + 当前未提交工作树
> 证据口径：源码/迁移/页面/API/测试分别核对；文档声明和历史运行记录不等于本轮运行验收。
> 本轮限制：Docker Engine 当前不可连接；未运行测试套件、前端构建或真实外部服务联调。
> 产品方向：完整工作台 C 架构，先交付可信的 GitHub Issue → Git Diff P0；P0 不宣称项目整体完成、安全通过或 CI 已验证。

## 1. 进度标尺与协作使用说明

完成度表示“相对当前目标能力的源码与交互闭合程度”，不是测试通过率：

- `90%–100%`：主逻辑、权限、失败路径、查询回放和自动化验证基本闭合。
- `70%–89%`：主路径已落地，仍缺关键恢复、角色 UI、详情回放或系统测试。
- `40%–69%`：已有模型/API/页面，但目标语义或上下游链路明显不完整。
- `1%–39%`：仅有旧模型、占位页面、局部接口或设计文档。
- `0%`：目标领域对象和入口均不存在。

本清单不预设负责人。协作者可按当前空闲度与专长领取功能切片；涉及迁移字段、公开 API、状态枚举、Snapshot Manifest 和 Report/PublishedRecord 投影的跨层改动，需要在合并前共同确认。

## 2. 功能拆解与进度清单

### 2.1 平台基础、身份与项目上下文

| ID | 功能模块/组件 | 已实现部分 | 当前进度与完成度 | 后续开发方向与待办（TODO） | AI 承接提示（Context Injection） | 主要代码证据 |
| --- | --- | --- | --- | --- | --- | --- |
| F01 | FastAPI 应用与模块化路由 | `/api/v1` 总路由；模块化单体；SQLAlchemy Session；健康检查；统一领域异常对象。 | 已实现，85% | 统一所有路由的 `DomainError → HTTP status + {code,message}` 映射；补请求关联 ID 返回头；增加 readiness 对迁移/Worker/Artifact 的真实健康读模型。 | 领域逻辑不得写入 route；route 只做 DTO、鉴权依赖、事务提交/回滚和错误映射。 | `backend/app/main.py`；`backend/app/api/router.py`；`backend/app/domain/errors.py` |
| F02 | PostgreSQL/pgvector 与迁移 | 001–026 已提交；当前工作树新增 027，多数领域对象已关系化；迁移采用追加式。 | 部分实现，82% | 应用并验证 027；为 P0 V2 增加 Issue Revision、ClaimSet、ArtifactObject、Manifest、ApprovalEvent 等迁移；不得改写历史哈希。 | 只能新增迁移；历史快照/报告/正式记录不可重算。迁移 ID 长度需兼容已扩容的 `alembic_version`。 | `backend/migrations/versions`；`backend/app/infrastructure/persistence/models.py` |
| F03 | 登录与 JWT | 邮箱密码登录；PBKDF2；短期 JWT；Bearer 鉴权；禁用用户拒绝访问。 | 部分实现，70% | 增加 `/auth/me`；返回用户 ID、显示名和各项目角色；处理 Token 过期；补登录限流/审计；生产环境改外部 Secret。 | 不把角色写进长期前端常量；后端每次资源访问仍按 ProjectMember 校验。 | `backend/app/application/security.py`；`backend/app/api/routes/auth.py` |
| F04 | 当前用户与角色化前端 | 登录页真实调用 API；Token 存 sessionStorage。 | 部分实现，35% | 删除固定“张伟”；加载 `/auth/me`；按项目角色隐藏/禁用上传、冻结、提交、审批、固化、Agent 配置按钮；全局拦截 401 并回登录。 | 前端权限只改善体验，不能替代后端 RBAC；不能从登录邮箱猜角色。 | `frontend/src/pages/LoginPage.vue`；`frontend/src/layouts/WorkbenchLayout.vue` |
| F05 | 项目创建、列表与选择 | 创建项目即创建 ADMIN 成员与默认双核编排；只列当前用户可访问项目；顶栏项目选择写 sessionStorage。 | 已实现，80% | URL 引入项目范围（建议 `/p/:projectId/...`）或至少校验路由详情与项目切换一致；项目切换时清空旧页面请求/选择；补项目编辑/归档（如确认需要）。 | 任何项目资源查询必须带 project_id 并在服务层重新鉴权；前端异步响应需检查请求时 projectId，避免串项目。 | `project_service.py`；`project-context.ts`；`WorkbenchLayout.vue` |
| F06 | 项目成员与双人审批准备 | 后端可按邮箱添加成员并分配 SUBMITTER/REVIEWER/ADMIN。 | 部分实现，40% | 增加成员列表 API、成员页/设置区、邀请演示审核者流程、角色调整与移除保护；确保项目至少保留一个 ADMIN；从空项目可纯前端建立提交者+审核者。 | 当前 `start.ps1` 只创建两个用户，不会把 reviewer 加入新项目；P0 双人审批会因此阻断。 | `project_service.py`；`projects.py`；`seed_demo_users.py` |

### 2.2 外部来源、研发事项与只读 Git

| ID | 功能模块/组件 | 已实现部分 | 当前进度与完成度 | 后续开发方向与待办（TODO） | AI 承接提示（Context Injection） | 主要代码证据 |
| --- | --- | --- | --- | --- | --- | --- |
| F07 | GitHub 公开/私有只读连接 | 限定 `api.github.com`；公开仓库无需 Token；Fine-grained PAT 仅以环境变量名引用；无重定向；响应大小/超时限制。 | 已实现，85%（私有外部未验收） | 增加连接测试、禁用/恢复、编辑凭据引用；真实私有仓库联调需用户提供本地忽略 PAT；错误投影区分 401/403/404/限流。 | 绝不保存或返回 Token；`secret_ref` 是环境变量名，不是密钥值。GitHub 连接是事项来源，不等于 Git 仓库记录。 | `github_source_client.py`；`credential_resolver.py`；`external_source_service.py` |
| F08 | GitHub 同步运行 | Link/cursor 兼容分页；最多 50 页；同步 Issue、PR、Milestone；失败保存页数、游标、错误码；设置页可触发同步并查看最近运行。 | 已实现，78% | 支持续传 cursor；展示多次同步历史而非仅最近一次；限流 reset/下一步；避免同步中重复点击；为部分成功提供“继续同步”。 | 同步失败不能覆盖历史镜像；`PARTIALLY_SUCCEEDED` 与 `FAILED` 不得显示为成功。 | `github_source_client.py`；`external_source_service.py`；`IntegrationsSettingsPage.vue` |
| F09 | Issue/PR/Milestone 镜像与交付项 | 外部资源与不可变 Revision；Issue 投影为 DeliveryItem；外部计划状态与本系统核验状态分离。 | 已实现，75% | P0 新增明确的 `DeliveryItemRevision/IssueRevision` 冻结；保存并回放 Issue 原始 JSON；记录同步 revision 与正式周期关系；处理 Issue 删除/转移。 | DeliveryItem 是镜像投影，不是正式验收目标；正式目标必须绑定具体 Revision。 | `ExternalResource*`、`DeliveryItem`；`external_source_service.py` |
| F10 | 事项页与任务创建 | 列真实事项/任务；筛选；从同步 Issue 创建核验任务并进入 Notebook。 | 已实现，78% | 展示 Issue 最新 Revision、正文摘要、来源新鲜度和“较当前周期已变化”；禁止一个事项无意创建多个活跃任务；补空项目到设置页入口。 | 任务只是核验容器；Issue `DECLARED_DONE` 不得映射为核验通过。 | `TaskCenterPage.vue`；`tasks.py`；`task_service.py` |
| F11 | 事项—PR/Git 范围归属 | 平台时间线发现；候选 Agent；人工确认；同仓库强校验；关联只表示归属、不表示完成。 | 部分实现，72% | UI 增加平台关系发现入口（后端已有）；显示输入清单/规则版本；补重复/并发/历史任务测试；P0 简化为“任务只选同源仓库”。 | `DeliveryChangeLink.CONFIRMED` 不能成为 `DIFF_SUPPORTED` 的替代证据。 | `delivery_association_service.py`；`TaskCenterPage.vue` |
| F12 | 只读 Git 仓库登记与项目列表 | HTTPS/SSH 登记；私有凭据引用；`GET /projects/{id}/git-repositories` 工作树已实现；设置页登记/列出。 | 部分实现，82% | 提交当前实现并执行迁移/测试；连接 GitHub 时可一键登记同源 HTTPS 仓库；增加停用/连通性检查；列表返回规范化 repository identity。 | P0 选仓库必须使用服务端列表；不得让用户提交任意 URL 到冻结接口。 | `git.py`；`git_service.py`；`IntegrationsSettingsPage.vue`；`test_git_repository_listing.py` |
| F13 | Git Diff 冻结与重读 | 解析 base/target 为具体 SHA；two/three-dot；路径包含/排除；禁 Hook/交互/重定向；记录 diff hash 与 coverage；运行时按 SHA 重读并验 hash。 | 部分实现，78% | 冻结时持久保存完整 Diff artifact、大小、媒体类型、哈希；拒绝空 Diff、截断 Diff 和超限 Diff；稳定映射 Git 错误码；覆盖 ref 不存在、二进制、子模块、大文件测试。 | 现有 `GitSnapshot` 只保存 hash/coverage，不保存 Diff 正文；远端/镜像丢失会破坏回放。 | `git_reader.py`；`git_service.py`；`GitSnapshot` |

### 2.3 项目知识库与检索

| ID | 功能模块/组件 | 已实现部分 | 当前进度与完成度 | 后续开发方向与待办（TODO） | AI 承接提示（Context Injection） | 主要代码证据 |
| --- | --- | --- | --- | --- | --- | --- |
| F14 | 知识上传接收与版本 | 权限校验；100 MiB 默认上限；扩展名/签名检测；原件哈希与版本号；原件写受控 artifact；创建持久 ingestion job。 | 工作树部分实现，78% | 校验 logical_name/source_role 空白；定义同名同 hash 去重策略；流式上传避免整文件入内存；文件名冲突/非法字符测试；提交迁移与依赖锁定。 | 当前 route 使用 `await file.read()`，100 MiB 会整体进入内存；不能只依赖浏览器 `accept`。 | `sources.py`；`source_service.py`；迁移 027 |
| F15 | 多格式检测与解析 | 支持 txt/md/csv/json/yaml/xml/html、pdf、doc/docx、xls/xlsx、ppt/pptx、odt/ods/odp、PNG/JPEG/WebP/TIFF；Office/OCR 工具已加入镜像。 | 工作树部分实现，68% | 增加解析器测试矩阵；限制 ZIP 条目/解压体积、Excel 行列、图片像素；HTML 去 script/style；XML 安全解析；PPT 表格/备注；CSV 方言与编码策略；旧 Office 结构丢失写入 metadata/coverage。 | “支持格式”必须指可提取且定位，不是仅能打开；音视频、压缩包、宏、嵌入对象继续不支持。 | `document_parser.py`；`backend/Dockerfile`；`pyproject.toml` |
| F16 | PDF 与 OCR | 可提取文本 PDF 直接读取；短文本页转 200dpi 图像 OCR；中文+英文；平均/页级阈值；加密 PDF、页数超限失败。 | 工作树部分实现，65% | 测试扫描件、混合文本、旋转页、空白页、低置信中文；对“无 token 页”明确失败/coverage；增加渲染与 OCR 资源上限、单页超时和总超时；保存页级 locator artifact。 | 置信度不足不得 READY；但 OCR 失败与低置信应是不同错误码和恢复建议。 | `document_parser.py::_extract_pdf/_ocr_image`；`source_service.py` |
| F17 | 异步 ingestion Worker | 独立 Job 表；FOR UPDATE SKIP LOCKED；租约、心跳、3 次重试；失败码/消息；Worker 主循环同时消费分析与资料任务。 | 工作树部分实现，72% | 分离 analysis/ingestion lane 或至少独立并发与背压；幂等重试前清理旧 chunks/artifacts；捕获进程崩溃后重复写；提供手动重试/取消；健康读模型和积压指标。 | 当前单 Worker 每轮先跑分析再跑一个 ingestion，长分析可能让资料排队；重试必须防止重复分块。 | `worker/source_ingestion.py`；`worker/main.py`；`SourceIngestionJob` |
| F18 | 文本标准化、分块与定位 | 统一 `knowledge-extraction-v1`；原始 locator 保留页/段/表格/Sheet/Slide/OCR box；提取文本单独保存。 | 工作树部分实现，70% | 统一 parser/chunker/retrieval policy 版本公式；避免段落 `find()` 对重复文本定位错误；大表/长段落二次分块；保存 normalized artifact hash 并纳入快照 Manifest。 | `parser_version` 当前被统一为 canonical 版本，真实 extractor 只在 metadata；下游需要同时保存 extractor/chunker 版本。 | `source_service.py`；`document_parser.py`；`DocumentChunk` |
| F19 | Embedding 与降级 | 默认百炼 `text-embedding-v4` 768 维；Gemini 适配；无 Key/不可用时保留真实词法 chunks，不写 Fake 向量；项目活动索引独立。 | 部分实现，76%（外部链未验收） | 解决工作树 canonical parser 与既有索引版本策略兼容；真实多格式→百炼→检索验证；异步 shadow rebuild；把内容 READY 与检索 DEGRADED 分状态显示。 | FakeEmbedding 类仍存在但工厂不选择；正式运行不得添加 Fake fallback。 | `embedding_model.py`；`retrieval_index_service.py`；`retrieval_service.py` |
| F20 | 检索索引管理 | 项目活动/历史索引；重建运行记录；失败可查询；查询只比较活动版本；无向量时词法降级。 | 部分实现，75% | 重建从 normalized artifact 而非仅旧 parser 假设；后台 Worker 化，禁止 HTTP 请求内逐块模型调用；原子切换；前端增加索引状态/重建入口或明确留在运维页。 | `READY` 仅代表内容可靠可冻结；语义检索可能 `DEGRADED`，两者不能合并为一个成功状态。 | `retrieval_index_service.py`；`retrieval_indexes.py` |
| F21 | 知识库页面可用性 | 项目级真实列表；分类/版本/格式/处理状态/快照引用；多文件上传；3 秒轮询；提取文本查看。 | 工作树部分实现，74% | 增原件下载、分块/定位查看、失败详情、手动重试、批量逐文件进度、大小/格式即时校验、空项目链接；更新 Notebook 空态的“仅 md/txt”旧文案。 | 后端已有 download/chunks 接口但 UI 未接；不要把知识库改成通用资料导入中心，信息架构仍以知识版本为主。 | `KnowledgeBasePage.vue`；`sources.py` |
| F22 | 知识库可靠性测试 | 历史仅验证过单一文本/Embedding 路径。 | 未实现，10% | 为用户目录 `D:\测试文档\省民政厅测试文档\查重测试文档` 建立不提交原件的验收脚本/清单；覆盖每类格式、中文名、重复内容、损坏/加密/超限/OCR 低置信、Worker 重试、原件/提取文本/hash/locator/检索一致性。 | 测试数据目录在仓库外；测试只记录相对文件名、hash、结果和失败码，不复制敏感文档进 Git。 | 当前 `backend/tests` 无 knowledge/ingestion/parser 用例 |

### 2.4 可信 P0：Issue → Claim → Snapshot → 双核

| ID | 功能模块/组件 | 已实现部分 | 当前进度与完成度 | 后续开发方向与待办（TODO） | AI 承接提示（Context Injection） | 主要代码证据 |
| --- | --- | --- | --- | --- | --- | --- |
| F23 | Issue Revision 冻结 | 外部资源已有不可变 Revision，任务可绑定 DeliveryItem。 | 目标未实现，25% | 新增正式 `DeliveryItemRevision/IssueRevision`；快照创建时选定最新 Revision 并保存原始 JSON artifact/hash；后续同步只提示“有新版本”，不改旧周期。 | 不能从当前 DeliveryItem 可变投影直接生成正式 Claim。 | `ExternalResourceRevision`；`VerificationTask.delivery_item_id` |
| F24 | Claim 草稿、人工确认与 ClaimSet | 旧 Workflow 从每个知识块自动生成 Claim；无确认 UI。 | 目标未实现，15% | 模型仅生成 ClaimDraft；用户逐项编辑/确认/排除；形成不可变 ClaimSet；保存来源 locator、Issue Revision、确认人/时间；无 confirmed claim 不得正式快照。 | 最新 P0 的“验收目标”来自 Issue 正文/验收段，不是所有知识块；知识资料只作为补充权威输入。 | `verification_graph.py::create_claims`（旧逻辑） |
| F25 | Formal InputSnapshot V2 | 现有 V1 可冻结 READY source、Git snapshot、external/manual evidence，拒绝重复和跨周期输入。 | 部分实现，48% | 门禁加入 confirmed ClaimSet、Issue Revision、同源仓库、具体 SHA、非空未截断 Diff、artifact 写入成功、每项 hash/size/media type；创建 `SnapshotManifest V2`；输入改变强制新 cycle。 | 现有 `snapshot_hash` 只覆盖关联摘要，不等于自包含制品清单。 | `snapshot_service.py::freeze_formal_snapshot` |
| F26 | ArtifactObject 与可离线回放 Manifest | 有 LocalArtifactStorage 和多个 `artifact_uri`；发布记录通过外键间接引用。 | 目标未实现，20% | 建 `ArtifactObject`（project/kind/hash/size/mediaType/storageUri/schemaVersion）；快照复制/引用 Issue JSON、ClaimSet、原件、normalized、chunk locators、完整 Diff、规则/模型版本；发布时 hash 校验。 | 原始远端/本地镜像删除后，正式记录仍必须可回放；仅保存 hash 不够。 | `artifact_storage.py`；`InputSnapshot*`；`PublishedRecord` |
| F27 | 分析 Run/Job 状态机 | 正式 snapshot 门禁；幂等键；Run/Manifest/Job；租约/心跳/重试/取消；节点事件；终态派生周期状态。 | 部分实现，78% | 保留具体 DomainError 到 job/run，不要统一 `WORKFLOW_FAILED`；增加 lease fencing token；Worker health/queue metrics；禁止失败 run 生成草稿；验证同 snapshot/config 重放。 | Job 状态、Run 状态、Cycle 状态、结论状态必须继续分离。 | `analysis_service.py`；`worker/main.py`；`analysis.py` |
| F28 | 固定双核编排 | 固定资料 Claim、Git Diff 收集、确定性链接、模型候选、外围 Agent、裁决、报告草稿；模板不可移除双核。 | 部分实现，62% | 用 confirmed ClaimSet 替换运行时文档块 Claim；Diff 必须来自 Snapshot artifact 而非远端重读；模型失败不得形成支持结论；固定双核版本升级为 V2。 | LangGraph 只负责编排，不保存正式业务状态；节点交换 ID/DTO，不把大原文塞 checkpoint。 | `verification_graph.py`；`orchestration_service.py` |
| F29 | P0 裁决语义 | 旧规则可输出 CONFLICTING、CONFIRMED、PARTIALLY_SUPPORTED、INFERENCE_REQUIRES_CONFIRMATION、INSUFFICIENT_EVIDENCE；模型关联不能直接确认。 | 与目标不一致，40% | 改为 `DIFF_SUPPORTED / PARTIALLY_SUPPORTED / INSUFFICIENT_EVIDENCE / CONFLICTING / REQUIRES_HUMAN_CONFIRMATION`；`DIFF_SUPPORTED` 必须有非空 CODE evidence locator；CI 不作为 P0 必需条件；模型/读取失败绝不能输出支持。 | 当前 `CONFIRMED` 要求成功 TEST/BUILD，这与 P0 Issue–Diff 定义冲突；迁移时旧记录保留 V1 标识。 | `verification_graph.py::reconcile`；`DeliveryVerificationStatus` |
| F30 | DeepSeek 真实生成适配 | DeepSeek JSON-mode 适配；Key 缺失/网络/Schema 失败有明确错误；工厂默认 DeepSeek；无 Fake 回退。 | 代码实现，70%（真实外部未验收） | 用有效本地 Key 真实跑 P0；确认模型名/响应契约；记录 provider/model/prompt/schema/allowed evidence/延迟/用量；模型不可用时 Run 显示部分/失败而非成功。 | `FakeGenerationModelAdapter` 虽存在，但正式工厂不可选择；不要删除历史测试夹具，也不要在 P0 自动回退。 | `generation_model.py`；`ModelCall`；`verification_graph.py` |
| F31 | Notebook 准备与运行控制 | 工作树已接资料选择、仓库列表、ref/path、Diff 冻结、正式快照、启动运行、3 秒轮询、事件/结果/报告。 | 部分实现，70% | 按真实门禁分步解锁；显示同源仓库原因；失败/终态后提供新 cycle/重试；补取消按钮；不自动全选全部 READY 资料；显示 ClaimSet/Issue Revision；修正多格式空态文案。 | 现有页面只在 `!liveRun` 展示准备区，失败 run 会把用户困在结果态。写操作完成后必须重新读服务端投影。 | `NotebookWorkspacePage.vue` |
| F32 | 证据、结论与 Diff 展示 | 三栏真实结果；证据摘要、locator、风险、运行编排；不再使用 fixtures。 | 部分实现，58% | 接 Evidence detail；实现只读高亮 Diff（文件/commit/hunk/行/Claim）；显示 coverage/skipped/failed；状态映射加入 CONFLICTING 和新 P0 五态；空结果不能显示“当前运行没有 P0 风险”。 | `live=true` 且结果为空/失败时不能解释为成功；必须先判断 run terminal 与 coverage。 | `SourceEvidencePane.vue`；`VerificationPane.vue`；`ReviewDetailPane.vue` |
| F33 | 临时工具结果与补证 | HTTP_QUERY 结果仅存临时 execution；不能进正式 Evidence/Report；用户可显式导入 ManualEvidence。 | 部分实现，68% | 补“要求补证→新 cycle→选择补证→新 snapshot→新 run”完整入口；当前导入后只提示，无可达下一轮操作；P0 默认可关闭 Agent 工具导航。 | 导入为 ManualEvidence 仍不是当前快照证据，必须进入新正式快照。 | `agent_tool_execution_service.py`；`NotebookWorkspacePage.vue` |

### 2.5 报告、审批与正式记录

| ID | 功能模块/组件 | 已实现部分 | 当前进度与完成度 | 后续开发方向与待办（TODO） | AI 承接提示（Context Injection） | 主要代码证据 |
| --- | --- | --- | --- | --- | --- | --- |
| F34 | 自动报告草稿与编辑 | Worker 可自动建 Draft；ReportItem 快照结果/引用；前端保存 editorial_note；乐观锁 version；提交审批。 | 部分实现，72% | 前端展示/编辑每个 ReportItem disposition，而非提交空 `{}`；展示正文、证据引用和 coverage；防止多个 Draft 选错（Notebook 当前按 cycle 找第一条）。 | 报告 hash 必须覆盖完整正文/条目/引用/处置；不能只覆盖结果 ID、状态和 editorial_note。 | `report_service.py`；`NotebookWorkspacePage.vue` |
| F35 | 审批状态机 | SUBMITTED 后 REVIEWER/ADMIN 可批准、要求修改、驳回；提交者不能自审；批准绑定 report/snapshot/run hash；退回复制新 Draft；PUBLISHED 锁死。 | 已实现，86% | 为“退回修改报告”与“要求补充证据”拆成两条业务命令；补并发、重复、跨项目、旧草稿、审批哈希变化测试；ApprovalEvent 统一查询。 | 退回报告可复用同 snapshot/run；补证必须关闭/派生新 cycle，不能复制旧报告就算完成。 | `report_service.py`；`test_report_cycle_immutability.py` |
| F36 | 审批队列与详情 | 真实 SUBMITTED 列表；原因输入；批准/退回/驳回；APPROVED 时显示固化按钮。 | 部分实现，65% | 按当前角色显示动作；审批人看到 Claim/报告条目/引用/coverage，而不是只有两个 hash；动作后导航到新草稿/记录；区分“修改报告”和“补证”。 | 后端 403 是最终边界，但 UI 不应向无权限用户展示“管理员固化”。 | `ApprovalQueuePage.vue`；`ApprovalDetailPage.vue` |
| F37 | 固化正式记录 | 仅 ADMIN 发布 APPROVED；复验 ApprovalAction 与 citations；写 PublishedRecord；更新 Cycle/Report；回写 DeliveryItem 核验状态。 | 部分实现，70% | PublishedRecord V2 固化完整 Manifest、报告正文/条目/引用、结论原因、处置、全部审批事件、发布事件；record hash 覆盖全部内容；旧 V1 标记不可完整回放。 | 当前 record hash 只基于 reportContentHash+snapshotHash，详情依赖可变外部 artifact/关联表。 | `report_service.py::publish`；`PublishedRecord` |
| F38 | 正式记录列表与回放详情 | 真实项目列表/详情；显示记录号、报告版本、snapshot/record hash、审批人与时间；只读。 | 部分实现，45% | 增报告正文、每项结论、引用证据、Issue Revision/ClaimSet、Snapshot Manifest、Diff/资料定位和审批时间线；提供 hash 校验状态；无编辑/回写按钮。 | 正式记录详情不是“元数据详情”，而是离线可审计回放页。 | `DeliveryHistoryPage.vue`；`DeliveryDetailPage.vue` |

### 2.6 完整工作台 C 的外围能力

| ID | 功能模块/组件 | 已实现部分 | 当前进度与完成度 | 后续开发方向与待办（TODO） | AI 承接提示（Context Injection） | 主要代码证据 |
| --- | --- | --- | --- | --- | --- | --- |
| F39 | 项目态势与总结 | 不可变态势快照、总结草稿/个人固化记录、页面读取；能区分计划状态与核验状态。 | 部分实现，68% | 从空项目增加“创建态势快照/总结”完整 UI；时间/里程碑筛选；数据新鲜度；团队审批类型；不在 P0 导航中抢占主链。 | 它读取正式事实，不能用提交数量或外部 done 推断完成。 | `project_status_service.py`；`ProjectStatusPage.vue` |
| F40 | 安全扫描工件、基线与质量趋势 | 导入 SHA 绑定扫描工件/风险；解释；基线/确认记录；严格可比趋势；页面查看与固化外围运行。 | 部分实现，65% | 前端缺扫描工件导入、风险处置、基线创建/确认入口；当前页面主要读取既有数据；补 API/权限/测试；保持“不执行扫描器”。 | 安全基线只说明指定 SHA/扫描器/规则/覆盖，不得输出“项目安全通过”。 | `security_baseline_service.py`；`SecurityBaselinePage.vue` |
| F41 | Agent 能力/工具/模板生命周期 | 固定双核锁定；CUSTOM 仅 SHARED；版本化 Prompt/schema/tools；停用；模板排序与任务绑定；HTTP_QUERY 白名单只读。 | 部分实现，74% | 当前用户角色化；工具连通性与白名单配置状态；模板兼容性/版本差异；外围 Agent 失败不影响双核主结论；P0 默认隐藏或标二阶段。 | Agent 不能替换核心、审批、发布、写 Git、任意执行代码或把临时 HTTP 结果直接变正式证据。 | `orchestration_service.py`；`AgentBlocksPage.vue`；`agent_tool_runner.py` |
| F42 | 工作台视觉与响应式 | 固定侧栏、顶栏项目选择、浅色中性、线性分隔；Notebook 三栏；多页面真实数据与空态；工作树做了布局优化。 | 部分实现，76% | 统一 form/table/modal/error/loading 组件；减少单文件超长模板；移动端 Notebook；真实角色/项目标题；浏览器视觉回归；避免重复页面标题与过多提示文案。 | 普通页面遵循 Dify 式线性分隔，Notebook 保留三栏；不要回退成卡片堆叠、AI 紫色或黑色大屏。 | `styles.css`；`WorkbenchLayout.vue`；各 page |
| F43 | API 客户端与前端状态 | 统一 `apiRequest`；项目上下文；写请求自动幂等 key；页面普遍在 project 切换时重载。 | 部分实现，55% | 封装 typed API 模块；保留 `error.code/status/details`；统一 401/403/409/422；AbortController；防重复提交；Pinia 查询缓存与 invalidation；文件下载单独处理非 JSON。 | 当前 `apiRequest` 假设 JSON 响应，不能直接用于原件下载；不要靠自然语言解析业务状态。 | `project-context.ts` |

### 2.7 工程可靠性、测试与文档

| ID | 功能模块/组件 | 已实现部分 | 当前进度与完成度 | 后续开发方向与待办（TODO） | AI 承接提示（Context Injection） | 主要代码证据 |
| --- | --- | --- | --- | --- | --- | --- |
| F44 | 审计与运行事件 | AuditEvent、RunEvent、NodeAttempt、ModelCall、AnalysisCoverage、同步/索引运行记录均已持久化。 | 部分实现，72% | 统一 correlation/project/task/cycle/run/job；错误分类保留原始 code；管理员运行状态页面；队列积压、lease、重试、模型耗时；日志脱敏测试。 | 可观测数据不能变成业务结论，也不能包含密钥/完整敏感原文。 | `common.py`；`Analysis*`/`AuditEvent` 模型 |
| F45 | 后端自动化测试 | 现有 6 个已提交测试文件，覆盖凭据、GitHub 分页、发布锁、仓库 identity、索引策略；工作树新增仓库列表/缺 Git 快照门禁。 | 明显不足，25% | 按 P0 增领域状态机、Issue/ClaimSet、snapshot V2、artifact hash、same-origin、DeepSeek failure、Worker lease/retry、报告双通道、发布回放、RBAC/API 契约；知识库测试见 F22。 | 不用“文件存在”当覆盖率；每个信任门禁至少有成功、拒绝、不留脏数据三类断言。 | `backend/tests` |
| F46 | 前端组件/E2E 测试 | 无 `test` script、无组件/E2E 依赖。 | 未实现，0% | 引入 Vitest + Vue Test Utils；覆盖项目切换、上传状态、Notebook 门禁、运行失败、非自审 UI、固化权限、正式回放；再用 Playwright 做公开仓库 P0 E2E。 | 先测试状态转换与错误显示，避免仅做 snapshot 样式测试。 | `frontend/package.json` |
| F47 | 本地启动/部署 | Compose：Postgres/api/worker/frontend/migrate；`start.ps1` 生成本地密码/JWT、迁移、启动、seed 两用户；artifact 与 DB 持久卷。 | 部分实现，75% | 当前 Docker 未运行，需后续验证 027/新系统包；增加 Worker/readiness health；启动后可选 seed project+members；校验 DeepSeek/百炼配置状态但不输出密钥。 | `start.ps1` 不是 P0 数据脚本；不要自动调用真实模型或 GitHub。 | `start.ps1`；`infra/docker-compose.yml`；`backend/Dockerfile` |
| F48 | 文档一致性与承接 | 架构、UI、可信边界、多格式知识库和历史进度文档齐全。 | 部分实现，60% | 标注“设计验收”与“代码/运行验收”；修正文档中旧的 FakeModel/Gemini、md/txt-only、旧差距清单；每个切片完成后同步本清单和功能文档。 | `AI-CodeReview-v1.md` 的全勾选是设计闭合，不能作为当前测试证据；`project-verification-overall-direction.md` 部分差距已过时。 | `docs/architecture`；`docs/lzh`；`docs/specs` |
| F49 | 当前未提交工作树收口 | 多格式知识库、P0 前端、Git 仓库列表、审批固化和布局改动已存在于工作树；旧 NotebookReviewPage 已删除。 | 未验证，55% | 先审 diff/补测试/应用迁移/构建；按“知识库可靠性”“P0 接口与 Notebook”“角色/回放 UI”拆小提交；不要把规划文档与业务代码混成一个提交。 | 这些代码不是 HEAD 能力；另一位开发者接手前必须先保存/分支化当前工作树，禁止 reset/checkout 覆盖。 | `git status`：31 个文件变动，含 3 个未跟踪文件 |

## 3. P0 协作实施顺序

| 阶段 | 后端与领域工作 | 前端与交互工作 | 阶段验收门 |
| --- | --- | --- | --- |
| P0-0 工作树收口 | 迁移 027、解析/Worker 单测、Git 列表测试；拆分并保护现有改动 | 知识库/设置/Notebook 当前页面做组件级检查，修正旧文案 | `git diff --check`、迁移到 head、后端定向测试、前端 build；真实 Docker 可用后再验运行 |
| P0-1 身份与空项目 | `/auth/me`、成员列表/角色 API、成员状态守卫 | 真实用户卡、角色按钮门禁、成员管理入口 | 新建项目后可纯前端加入 reviewer；提交者和审核者均能进入同项目 |
| P0-2 目标冻结 | IssueRevision、ClaimDraft/ClaimSet/AcceptanceClaim、确认 API | 事项详情/Claim 确认面板 | 无 confirmed ClaimSet 时 formal snapshot 必须 409/422，且不产生 snapshot |
| P0-3 制品与快照 V2 | ArtifactObject、完整 Diff/Issue/资料制品、Snapshot Manifest/hash 校验 | Notebook 分步门禁、同源仓库说明、制品清单摘要 | 跨仓库、错误 ref、空/截断 Diff、资料未 READY 均拒绝且无残留正式快照 |
| P0-4 双核 V2 | ClaimSet 输入、Diff artifact 输入、新五态裁决、原始错误码、Worker fencing | 运行状态/coverage/真实错误、只读高亮 Diff、取消/重试/新 cycle | 缺模型 Key、Git 读取失败、模型 Schema 失败均不产生 `DIFF_SUPPORTED` |
| P0-5 报告与回放 | 报告 hash V2、退回双通道、PublishedRecord Manifest V2 | 报告条目编辑、审批证据页、角色化固化、完整记录回放 | submitter 不可自审；ADMIN 固化后离线回放报告/快照/引用/审批；历史不可写 |
| P0-6 真实验收 | 公开 GitHub + 多格式知识库 + DeepSeek/百炼（仅有本地密钥时） | Playwright 主链与失败态 | 公开 Issue→知识→Diff→Snapshot→Run→审批→正式记录完整一次；每个前置失败有下一步，不显示成功率 |

## 4. 代码规范与全局约束

### 4.1 架构与依赖方向

1. 保持 `FastAPI API → application service → domain/port → infrastructure adapter`；领域与服务层不得依赖 FastAPI、Vue、供应商 SDK 类型。
2. PostgreSQL 是正式状态源；artifact storage 保存原件/大制品；LangGraph checkpoint 不是审批、报告或发布状态源。
3. Worker 只消费持久 Job；API 不用进程内 background task 承担资料解析或核验。
4. Git 始终只读：禁 Hook、禁交互、禁执行仓库代码/构建/测试、禁写远端；P0 不增加任意命令、任意 HTTP 或扫描器执行接口。
5. 外围 Agent 只允许 `SHARED`；固定需求/验收核心与交付证据核心不可删除、替换或绕过。

### 4.2 状态与不可变规则

1. 分开维护 `SourceProcessingStatus`、IngestionJob、AnalysisJob、AnalysisRun、VerificationCycle、结论、ReportVersion、PublishedRecord 状态。
2. 正式输入一旦冻结不可变；Issue、Claim、资料、Diff、规则或模型版本变化必须创建新 cycle/snapshot/run/report。
3. 模型失败、Git 失败、资料失败、无证据、人工待确认是不同状态；不得统一显示“未通过”或“已完成”。
4. 发布后 Cycle/Report/Approval/Manifest 不可写；历史 V1 若不能完整回放，明确标记 `V1 / replay_limited`，不得伪造升级。

### 4.3 API 与 DTO

1. API 前缀固定 `/api/v1`；字段使用现有 snake_case；新增字段优先可选，破坏性变化用 V2 DTO/endpoint 或 schema_version。
2. 所有写命令要求 `Idempotency-Key`；服务层校验项目角色、资源归属、状态和版本；前端按钮禁用不是授权。
3. 错误响应固定 `{detail:{code,message,field?,retryable?,nextAction?}}`；前端保留 `code/status`，不得从中文 message 猜状态。
4. 查询接口必须按 project/cycle/snapshot 过滤；详情 ID 不能绕过项目权限。
5. 文件上传使用 multipart；文件下载不经过 JSON `apiRequest`；大文件改流式落盘并在写入时计算 hash。

### 4.4 数据、哈希与制品

1. 哈希输入采用 canonical JSON（UTF-8、key 排序、稳定 separators）；所有 Manifest 带 `schema_version`。
2. 每个正式 artifact 至少记录 `kind/artifact_id/content_hash/size/media_type/source_identity/locator/producer/captured_at/schema_version`。
3. 快照必须自包含 Issue JSON、confirmed ClaimSet、资料原件/normalized/chunk locator、完整 Diff、SHA/path scope、模型/规则版本。
4. 报告与正式记录 hash 覆盖正文、条目、结论原因、引用、处置、审批和发布动作，不能只覆盖外键或摘要。

### 4.5 前端规范

1. Vue 3 `<script setup lang="ts">`；共享项目/身份/API 状态放 feature/store，页面只保留页面态。
2. 普通工作台页面使用浅色中性、细分隔线、真实表格/表单；Notebook 保留三栏。禁止 fixtures、AI 紫色渐变、玻璃拟态和卡片堆叠。
3. 页面必须覆盖 loading/empty/permission/error/retry/terminal；错误态给实际下一步，但不堆砌逐句引导。
4. 用户、角色、项目、任务状态全部来自服务端；不可硬编码姓名、完成率、成功结论或演示数据。
5. 按钮必须有真实 handler/API/权限/成功回读；无完整链路的按钮删除或隐藏，不保留死入口。

### 4.6 测试与交付

1. 信任门禁测试至少覆盖：成功、拒绝、事务无残留、幂等重放、跨项目/跨仓库越权。
2. 知识库测试分 parser 单元、ingestion Worker、API、真实样本文档验收；真实样本不提交 Git。
3. 前端先覆盖状态门禁与错误显示，再做视觉 snapshot；P0 最终需要浏览器→API→DB/artifact→回放 E2E。
4. 外部服务验收必须明确 Key/网络/限流条件；Fake 仅用于测试夹具，不可替代 P0 真实 DeepSeek 验收。
5. 保留小而可验证的中文提交；不推送远端；接手者先区分 HEAD、unstaged、untracked，禁止破坏当前工作树。

## 5. 可直接注入下游 AI 的全局上下文

```text
你正在 D:\秋招项目\AI应用开发项目\one 继续开发 AI-CodeReview。

产品总方向是完整工作台 C，但当前交付优先级是可信 P0：公开 GitHub Issue Revision → 人工确认 ClaimSet → READY 项目知识 → 同源只读 Git Diff → 自包含 InputSnapshot V2 → 真实 DeepSeek 固定双核 → 报告版本 → 非自审审批 → 管理员固化 PublishedRecord V2。

严格边界：P0 只回答“人工确认的 Issue 验收项是否在指定冻结 Diff 中获得可定位证据支持”，不回答项目整体完成、安全通过或 CI 已验证。Git 只读，不执行仓库代码、Hook、构建或测试。自定义 Agent 仅 SHARED，不能替换双核、审批或发布。模型/Git/资料失败不能生成 DIFF_SUPPORTED，也不能切 Fake。

当前 HEAD 是 4b13ded，但工作树有未提交的多格式知识库、Git 仓库列表、Notebook/审批/布局改动。不得 reset、checkout 或覆盖用户改动。开始编码前先读 git status、git diff 和本文件；将“已提交 HEAD 能力”和“未提交工作树能力”分开判断。

现有后端是 FastAPI 模块化单体 + SQLAlchemy/Alembic + PostgreSQL/pgvector + 独立 Worker + LangGraph；前端是 Vue 3/Vite/TypeScript。API 前缀 /api/v1，写命令需要 Idempotency-Key，后端 RBAC 是最终权限边界。正式状态在 PostgreSQL，大制品在受控 artifact storage。

当前最高风险缺口：没有 IssueRevision/ClaimSet 人工确认；正式快照不自包含完整 Diff/Issue/资料制品；旧裁决 CONFIRMED 依赖成功 TEST/BUILD，与 P0 五态不一致；正式记录详情不能完整回放；前端没有真实当前用户/角色和成员管理；知识库多格式实现未提交且无可靠性测试；前端没有组件/E2E 测试。

实施顺序：先保护并验证当前工作树 → 身份/成员闭环 → IssueRevision/ClaimSet → Artifact/Manifest/Snapshot V2 → 双核与五态 V2 → Notebook/报告/审批/回放 → 真实 P0 E2E。每次只改一个可验收切片，并同步本清单的完成度、TODO 和证据。
```

## 6. 当前结论

- 项目不是空壳：外部来源、知识库、Git、双核运行、报告审批、项目态势、安全工件和 Agent 编排均有真实后端模型/API，主要页面也已接真实数据。
- 当前还不能称为“可信 P0 完成”：Issue 没有冻结为人工确认 ClaimSet，Snapshot/PublishedRecord 不能自包含回放，裁决语义仍是旧 V1，角色/成员和失败恢复的前端链路不完整。
- 当前最成熟但最需要可靠性收口的是多格式知识库；最需要领域重构的是 P0 Issue→ClaimSet→Manifest V2；最影响双人演示的是成员/角色与正式记录完整回放。
