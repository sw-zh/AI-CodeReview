# AI-CodeReview 架构约束文档任务计划

## 目标

生成一份可直接交给下一次 Codex 对话的架构设计约束文档，使下一次对话能够在既定范围内完成 AI-CodeReview 的完整架构设计，而不会提前进入业务实现或扩展重型能力。

## 阶段

- [x] 检查仓库与远程状态
- [x] 汇总已确认的产品、技术与范围约束
- [x] 编写架构设计约束文档
- [x] 自检占位符、矛盾、歧义和范围漂移
- [x] 检查 Git 变更并提交、推送

## 固定决策

- 项目名称：AI-CodeReview
- 仓库：`D:\秋招项目\AI应用开发项目\one`
- 远程：`https://github.com/yyy2045/one.git`
- 首版为模块化单体：Vue 3 + TypeScript、FastAPI、PostgreSQL + pgvector、LangGraph、Gemini 适配器、Docker Compose
- LangGraph 只编排一次交付核验任务内部的 AI 分析流程
- PostgreSQL 是正式业务状态的唯一事实来源
- 本轮只生成设计约束文档，不编写业务代码

## 错误记录

| 错误 | 原因 | 处理 |
|---|---|---|
| `git log` 返回当前 `main` 无提交 | 远程与本地仓库均为空 | 作为新仓库处理，不重复执行日志查询 |
| 首次 `rg` 自检使用了默认引擎不支持的负向前瞻 | 表达式包含 `(?!...)` | 改用 `rg --pcre2` 完成扫描 |
| PowerShell 中把 `*.md` 直接拼进 `rg` 的绝对路径失败 | Windows 将该参数解析为非法路径 | 改为在仓库根目录使用 `rg --glob '*.md'` |
