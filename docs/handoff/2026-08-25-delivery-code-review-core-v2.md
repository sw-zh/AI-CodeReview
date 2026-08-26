# 交付代码审查核心 v2 承接说明

## 已实现

- `028_delivery_code_review_core.py` 新增不可变 `ArtifactObject`、`CodeReviewFinding`、Git Snapshot 制品引用与 `AnalysisCoverage.details`。
- Git 冻结阶段通过 `ReadOnlyGitReader` 只读 clone/fetch/rev-parse/merge-base/diff/show，保存完整原始 Diff bytes 和 `CODE_CHANGE_BUNDLE`；不会 checkout 或执行仓库内容。
- 分析图中的 `collect_git_evidence` 只读取本地 ArtifactObject，校验 Diff/Bundle 哈希后创建 `GIT_DIFF_HUNK` EvidenceItem；分析期不再访问远端 Git。
- `review_code` 作为锁定 `delivery-git-diff` 内部节点执行。它只允许 DeepSeek；模型失败写入 ModelCall、Coverage 和 Manifest degradation，不切换 Fake/Gemini。
- `CodeReviewFinding` 经过 evidence/claim/fingerprint 校验后保存。一般 Finding 仅展示，不直接改写最终 VerificationResult。
- 新只读 API：`GET /git-snapshots/{id}/diff`、`GET /analysis-runs/{id}/code-review`。
- Notebook 来源栏读取上述 API，展示冻结文件、二进制跳过、Finding、触发场景、建议和 Coverage。

## 标准核验增强

- `029_standard_verification_challenge.py` 新增不可变 `CodeReviewFindingChallenge`；同一运行的同一 Finding 只能保存一条复核结果，原 Finding 永不被覆盖或删除。
- 固定图在 `review_code` 后运行 `challenge_code_findings`，再运行纯代码 `summarize_code_coverage`，随后才进入既有确定性链接与裁决。复核只能给出 `SUPPORTED`、`UNSUPPORTED`、`NEEDS_HUMAN`，不能生成新 Finding、改 Severity 或写 `VerificationResult`。
- `challenge_code_findings` 仅将原 Finding、其冻结 Hunk、可选 Claim 和受预算限制的上下文传给 DeepSeek；Fake/Gemini/无 Key、超时或无效结构化输出均写 ModelCall、Manifest degradation 与 Coverage，不切换模型或制造结果。
- `STANDARD_VERIFICATION` Coverage 汇总文件/Hunk、二进制、审查 Hunk、Finding 数、复核 verdict 和未覆盖原因；它不是完成率或无风险结论。
- `GET /analysis-runs/{id}/code-review` 为每个 Finding 返回复核状态、结论、理由和 Hunk Evidence ID，并返回 `FINDING_CHALLENGE` 与 `STANDARD_VERIFICATION` Coverage。Notebook 显示“标准核验”、四种复核状态和针对模型/预算/制品失败的下一步。

## 固定边界

- `requirement-claim-core -> delivery-git-diff -> evidence-reconciliation` 保持不变。
- Hunk 才是正式代码证据；base/target 全文仅 `CONTEXT_ONLY`。
- 不写 Git/GitHub，不运行任何仓库代码、构建、测试或 Hook。
- `TWO_DOT` 和 `THREE_DOT` 兼容既有 Notebook；前者是精确 base/target，后者是 merge-base/target。

## 运行与维护

- 新快照和新分析会拒绝没有 Diff/Bundle Artifact 的 Git Snapshot；历史快照返回 `GIT_ARTIFACT_MISSING`，不被伪装为可回放。
- 上下文配置：`CODE_REVIEW_CONTEXT_MAX_FILE_BYTES`、`CODE_REVIEW_CONTEXT_MAX_TOTAL_BYTES`、`CODE_REVIEW_INPUT_CHAR_BUDGET`。
- `CODE_REVIEW_INPUT_CHAR_BUDGET` 优先保障 Hunk；上下文超预算时成为 `CODE_CONTEXT_BUDGET_EXHAUSTED`，Coverage 必须显示。
- 反证预算配置：`CODE_REVIEW_CHALLENGE_MAX_FINDINGS`、`CODE_REVIEW_CHALLENGE_INPUT_CHAR_BUDGET`、`CODE_REVIEW_CHALLENGE_TIMEOUT_SECONDS`；超预算和超时必须保留为 Coverage/降级状态。

## 已验证与未覆盖

- 已通过：Python 编译、029 Alembic 离线 SQL、8 项交付代码审查定向测试、完整后端 24 项 pytest、API 路由导入/声明校验与前端生产构建。
- 已按项目 `pyproject.toml` 补齐本地依赖并安装 pytest；Docker Desktop Linux Engine 仍不可用，尚未启动容器或调用真实 DeepSeek。
- 下一次在完整容器依赖和有效 DeepSeek Key 下，应执行：公开仓库冻结 Diff、正式快照、分析运行、`code-review` 读取、模型不可用受控失败、报告草稿回放。

## 2026-08-25 真实 E2E 已完成

- Docker 恢复后，开发数据库已安全追加迁移至 029。以隔离项目运行了公开只读 `octocat/Hello-World` 的精确两点 Diff：`553c2077f0edc3d5dc5d17262f6aa498e69d6f8e..7fd1a60b01f91b314f59955a4e4d4e80d8edf11d`。
- 正式快照 `288da59b-4310-46ca-868a-98f754d7012e` 的运行 `1a022c32-3235-4fe7-b5a9-eb71fd0bee23` 成功。事件顺序为 `load_snapshot → collect_git_evidence → create_claims → review_code → challenge_code_findings → summarize_code_coverage → link_deterministic → reconcile → report-draft`。
- `CODE_REVIEW` 调用真实 DeepSeek 成功（`deepseek-v4-flash`，4,191 ms）。该 1 行 README 修改产生 0 条 Finding，所以 `FINDING_CHALLENGE` 正确为 `NOT_APPLICABLE / NO_CODE_REVIEW_FINDINGS`；`STANDARD_VERIFICATION` 为 `PARTIAL`，明确说明只审查了冻结范围，绝不输出完成率或无风险结论。
- 已读取冻结 Diff、运行事件、代码审查投影和结果投影，并确认自动报告草稿生成。临时源码挂载 API/Worker 已移除；镜像构建完成后，正式 Compose API/Worker 已以当前源码镜像重建，并通过 `/health/ready` 与 `code-review` 投影回读。资料索引的 Dashscope Embedding 在本次上传中仍为 `MODEL_UNAVAILABLE`，该失败保持可见且未阻断 READY 资料用于正式快照。
- 后续补跑了可产生 Finding 的真实公开 Diff：`atiradonet/weak-go-app` 从 `b4b8012bbebcc519ebf79b536e7398224101f689` 到 `72acebe2aebff3c2a17833d37cab970a2c14a984`，路径严格限制为 `handlers/system.go`。运行 `f0f3a5c9-0654-41b5-ad38-3376efff7469` 成功生成 2 条 SECURITY Finding。
- 同一运行中 DeepSeek 的 `CODE_REVIEW_CHALLENGE` 调用成功并持久化 2 条 Challenge：`sh -c` 接收用户 cmd 的 Finding 为 `NEEDS_HUMAN`，因为 Diff 不含端点注册/部署可达性；错误详情泄露 Finding 为 `UNSUPPORTED`，因为 `fetchInternalReport` 在冻结实现内总返回 nil error。最终 Coverage：1 文件、1 Hunk、2 Finding、`SUPPORTED=0 / NEEDS_HUMAN=1 / UNSUPPORTED=1`。这验证了反证步骤不会把初步 Finding 写成最终安全结论。
