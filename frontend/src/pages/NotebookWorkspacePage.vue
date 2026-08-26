<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import ReviewDetailPane from "../features/notebook/ReviewDetailPane.vue";
import SourceEvidencePane from "../features/notebook/SourceEvidencePane.vue";
import VerificationPane from "../features/notebook/VerificationPane.vue";
import {
  apiRequest,
  projectHeaders,
  selectedProjectId,
} from "../features/projects/project-context";
import type {
  EvidenceReference,
  VerificationConclusion,
} from "../types/workbench";

type AnalysisRun = { id: string; snapshot_id: string; run_status: string };
type RunEvent = {
  id: string;
  nodeId: string | null;
  eventType: string;
  status: string;
  details: Record<string, unknown>;
  createdAt: string;
};
type SourceItem = {
  id: string;
  logical_name: string;
  source_role: string;
  revision_no: number;
  processing_status: string;
};
type GitRepository = { id: string; display_url: string; read_only: boolean };
type GitSnapshot = {
  id: string;
  base_sha: string;
  target_sha: string;
  diff_hash: string;
  coverage: { changedFiles?: string[] };
};
type GitDiff = {
  files: Array<{
    path: string;
    old_path?: string | null;
    edit_type: string;
    additions: number;
    deletions: number;
    binary: boolean;
    hunks: Array<{ header: string; payload: string }>;
  }>;
  coverage: Record<string, unknown>;
};
type CodeReview = {
  gitSnapshotId: string | null;
  findings: Array<{
    id: string;
    evidenceId: string;
    severity: string;
    findingKind: string;
    title: string;
    problem: string;
    triggerScenario: string;
    recommendation: string;
    confidence: number;
    challenge: {
      state: string;
      verdict: string | null;
      reason: string | null;
      evidenceIds: string[];
    };
  }>;
  coverage: Array<{
    scopeKind: string;
    state: string;
    reasonCode: string | null;
    details: Record<string, unknown>;
  }>;
};
type ProjectReport = {
  id: string;
  cycle_id: string;
  sequence_no: number;
  status: string;
  editorial_note: string;
  version: number;
  content_hash: string;
};
type ReportPreview = ProjectReport & {
  snapshot_hash: string;
  task_title: string;
  requirement_key: string;
  items: Array<{
    id: string;
    claimText: string;
    result: {
      status: string;
      reason: string;
      humanDecision: {
        decision: string;
        note: string;
        createdAt: string | null;
      } | null;
    };
    disposition: string | null;
    citations: Array<{
      id: string;
      sourceType: string;
      excerpt: string;
      locator: Record<string, unknown>;
    }>;
  }>;
};
type RunOrchestration = {
  contentHash: string;
  template: { name: string; version: number };
  nodes: Array<{
    capabilityKey: string;
    capabilityName: string;
    capabilityVersion: number;
    displayOrder: number;
    locked: boolean;
    tools: Array<{ key: string }>;
  }>;
};
type ResultEvidence = {
  id: string;
  sourceType: string;
  excerpt: string;
  locator: Record<string, unknown>;
  precision: string;
};
type AnalysisResult = {
  id: string;
  claim_text: string;
  status: string;
  reason: string;
  requires_human_confirmation: boolean;
  evidence: ResultEvidence[];
  risks: Array<{ severity: string }>;
  human_decision: {
    id: string;
    decision: string;
    note: string;
    actorId: string;
    createdAt: string | null;
  } | null;
  allowed_human_decisions: string[];
};
type DeliveryClaim = {
  id: string;
  claim_key: string;
  text: string;
  rationale: string;
  origin: "MODEL" | "HUMAN";
  status: "CANDIDATE" | "CONFIRMED";
  source_manifest: Record<string, unknown>;
};
type ToolExecution = {
  id: string;
  analysis_run_id: string;
  capability_key: string;
  tool_key: string;
  content_hash: string;
  excerpt_safe: string;
  locator: Record<string, unknown>;
  status: string;
  imported_manual_evidence_id: string | null;
};
type PullRequestRange = {
  number: string;
  baseRef: string;
  baseSha: string;
  headRef: string;
  headSha: string;
  mergedAt: string | null;
};
type TaskContext = {
  id: string;
  title: string;
  cycle_id: string | null;
  cycle_status: string;
  formal_snapshot_id: string | null;
  formal_snapshot_hash: string | null;
  report_id: string | null;
  report_status: string | null;
  delivery_pull_request: PullRequestRange | null;
};

const route = useRoute();
const selectedId = ref("pending-result");
const task = ref<TaskContext | null>(null);
const sources = ref<SourceItem[]>([]);
const repositories = ref<GitRepository[]>([]);
const selectedSourceIds = ref<string[]>([]);
const claimEdits = ref<
  Array<{
    id?: string;
    text: string;
    rationale: string;
    origin: "MODEL" | "HUMAN";
    status: "CANDIDATE" | "CONFIRMED";
    selected: boolean;
  }>
>([]);
const claimProposalAttempted = ref(false);
const gitForm = ref({
  repositoryId: "",
  baseRef: "main",
  targetRef: "HEAD",
  diffMode: "TWO_DOT",
  includePaths: "",
  excludePaths: "",
});
const gitSnapshot = ref<GitSnapshot | null>(null);
const liveRun = ref<AnalysisRun | null>(null);
const liveEvents = ref<RunEvent[]>([]);
const liveOrchestration = ref<RunOrchestration | null>(null);
const liveResults = ref<AnalysisResult[]>([]);
const liveCodeReview = ref<CodeReview>({
  gitSnapshotId: null,
  findings: [],
  coverage: [],
});
const liveGitDiff = ref<GitDiff | null>(null);
const toolExecutions = ref<ToolExecution[]>([]);
const report = ref<ProjectReport | null>(null);
const reportPreview = ref<ReportPreview | null>(null);
const reportNote = ref("");
const decisionNote = ref("");
const decisionMessage = ref("");
const busy = ref(false);
const runLogOpen = ref(false);
const centerView = ref<"conclusions" | "diff">("conclusions");
const selectedDiffPath = ref("");
const preparationMessage = ref(
  "选择可选资料并冻结与本次 Pull Request 同源的只读 Git Diff。",
);
const claimMessage = ref(
  "先由 DeepSeek 根据 Pull Request 描述提出候选交付内容；确认后才能冻结本轮核验范围。",
);
const gitFreezeMessage = ref("");
const gitFreezeState = ref<"idle" | "working" | "success" | "error">("idle");
const reportMessage = ref(
  "运行结束后，系统会根据冻结结果生成可提交的报告草稿。",
);
const toolImportNames = ref<Record<string, string>>({});
const importingToolExecutionId = ref("");
const toolExecutionError = ref("");
const toolImportMessage = ref("");
const liveLoadError = ref("");
let pollTimer: ReturnType<typeof window.setTimeout> | undefined;

const readySources = computed(() =>
  sources.value.filter((source) => source.processing_status === "READY"),
);
const confirmedClaimCount = computed(
  () =>
    claimEdits.value.filter(
      (claim) => claim.status === "CONFIRMED" && claim.text.trim().length >= 3,
    ).length,
);
const selectedClaimCount = computed(
  () =>
    claimEdits.value.filter(
      (claim) => claim.selected && claim.text.trim().length >= 3,
    ).length,
);
const canFreezeGit = computed(() =>
  Boolean(
    task.value?.cycle_id &&
    gitForm.value.repositoryId &&
    gitForm.value.baseRef.trim() &&
    gitForm.value.targetRef.trim(),
  ),
);
const canFreezeFormalSnapshot = computed(() =>
  Boolean(
    task.value?.cycle_id && gitSnapshot.value && confirmedClaimCount.value,
  ),
);
const canStartRun = computed(() =>
  Boolean(
    task.value?.formal_snapshot_id ||
    (gitSnapshot.value && selectedSourceIds.value.length),
  ),
);
const activeRun = computed(() =>
  Boolean(
    liveRun.value &&
    !["SUCCEEDED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED"].includes(
      liveRun.value.run_status,
    ),
  ),
);
const selectedDiffFile = computed(() => {
  const files = liveGitDiff.value?.files ?? [];
  return (
    files.find((file) => file.path === selectedDiffPath.value) ??
    files[0] ??
    null
  );
});

function splitPaths(value: string) {
  return value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}
function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
function runStepLabel(nodeId: string | null) {
  return (
    (
      {
        run_custom_agents: "补充分析",
        reconcile: "汇总证据与结论",
        "report-draft": "生成报告草稿",
        worker: "后台任务",
      } as Record<string, string>
    )[nodeId ?? ""] ?? "核验处理"
  );
}
function runStepStatus(status: string) {
  return (
    (
      {
        RUNNING: "进行中",
        SUCCEEDED: "已完成",
        FAILED: "失败",
        CANCELLED: "已取消",
        PENDING: "等待中",
      } as Record<string, string>
    )[status] ?? status
  );
}
function isUuid(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(
      value,
    )
  );
}
function mapStatus(status: string): VerificationConclusion["status"] {
  if (status === "CONFIRMED") return "已确认";
  if (status === "PARTIALLY_SUPPORTED") return "部分支持";
  if (status === "INSUFFICIENT_EVIDENCE") return "证据不足";
  if (status === "CONFLICTING") return "存在冲突";
  return "待人工确认";
}
function effectiveConclusionStatus(item: AnalysisResult): VerificationConclusion["status"] {
  if (item.human_decision?.decision === "CONFIRM_SUPPORT") return "已确认";
  if (item.human_decision?.decision === "CONFIRM_PARTIAL") return "部分支持";
  if (
    item.human_decision?.decision === "CONFIRM_INSUFFICIENT" ||
    item.human_decision?.decision === "RETURN_FOR_EVIDENCE"
  )
    return "证据不足";
  return mapStatus(item.status);
}
function reportConclusionStatus(item: ReportPreview["items"][number]) {
  const decision = item.result.humanDecision?.decision;
  if (decision === "CONFIRM_SUPPORT") return "已确认";
  if (decision === "CONFIRM_PARTIAL") return "部分支持";
  if (
    decision === "CONFIRM_INSUFFICIENT" ||
    decision === "RETURN_FOR_EVIDENCE"
  )
    return "证据不足";
  return mapStatus(item.result.status);
}
function mapEvidenceKind(sourceType: string): EvidenceReference["kind"] {
  if (sourceType === "CODE") return "代码";
  if (sourceType === "TEST" || sourceType === "BUILD") return "测试";
  if (sourceType === "MANUAL") return "人工补证";
  return "需求";
}
function locatorLabel(locator: Record<string, unknown>): string {
  return String(
    locator.path ??
      locator.hunk ??
      locator.toolKey ??
      locator.sourceRevisionId ??
      "冻结快照证据",
  );
}
function stopPolling() {
  if (pollTimer) window.clearTimeout(pollTimer);
  pollTimer = undefined;
}

const liveEvidence = computed<EvidenceReference[]>(() => {
  const byId = new Map<string, EvidenceReference>();
  for (const result of liveResults.value)
    for (const item of result.evidence)
      if (!byId.has(item.id))
        byId.set(item.id, {
          id: item.id,
          kind: mapEvidenceKind(item.sourceType),
          title: item.sourceType,
          locator: locatorLabel(item.locator),
          excerpt: item.excerpt,
          state: "已引用",
        });
  return [...byId.values()];
});
const liveConclusions = computed<VerificationConclusion[]>(() =>
  liveResults.value.map((item) => ({
    id: item.id,
    requirement: item.claim_text,
    status: effectiveConclusionStatus(item),
    summary: item.human_decision
      ? `${item.reason} 人工裁决：${decisionLabel(item.human_decision.decision)}。`
      : item.reason,
    needsHumanDecision: item.requires_human_confirmation && !item.human_decision,
    risk: item.risks.some((risk) => risk.severity === "HIGH")
      ? "P0"
      : item.risks.length
        ? "P1"
        : null,
    evidenceIds: item.evidence.map((evidence) => evidence.id),
    systemStatus: item.status,
    humanDecision: item.human_decision,
    allowedHumanDecisions: item.allowed_human_decisions,
  })),
);
const displayedConclusions = computed<VerificationConclusion[]>(() =>
  liveRun.value && liveConclusions.value.length
    ? liveConclusions.value
    : claimEdits.value
        .filter((claim) => claim.selected && claim.text.trim())
        .map((claim, index) => ({
          id: `pending-${claim.id ?? index}`,
          requirement: claim.text,
          status: "待人工确认",
          summary: liveRun.value
            ? "该主张尚未产生可展示的核验结果。请查看运行记录中的真实失败或处理状态。"
            : "该主张已确认，但尚未冻结输入并启动核验。",
          needsHumanDecision: true,
          risk: null,
          evidenceIds: [],
        })),
);
const selectedConclusion = computed(
  () =>
    displayedConclusions.value.find((item) => item.id === selectedId.value) ??
    displayedConclusions.value[0],
);
const unresolvedDecisionCount = computed(
  () =>
    liveResults.value.filter(
      (item) => item.requires_human_confirmation && !item.human_decision,
    ).length,
);

async function loadRun(run: AnalysisRun) {
  liveRun.value = run;
  const results = await apiRequest<AnalysisResult[]>(
    `/analysis-runs/${run.id}/results`,
    { headers: projectHeaders() },
  );
  liveResults.value = results;
  selectedId.value = results[0]?.id ?? "pending-result";

  const [orchestrationResult, eventsResult, codeReviewResult] =
    await Promise.allSettled([
      apiRequest<RunOrchestration>(`/analysis-runs/${run.id}/orchestration`, {
        headers: projectHeaders(),
      }),
      apiRequest<{ items: RunEvent[] }>(`/analysis-runs/${run.id}/events`, {
        headers: projectHeaders(),
      }),
      apiRequest<CodeReview>(`/analysis-runs/${run.id}/code-review`, {
        headers: projectHeaders(),
      }),
    ]);
  if (orchestrationResult.status === "fulfilled")
    liveOrchestration.value = orchestrationResult.value;
  if (eventsResult.status === "fulfilled")
    liveEvents.value = eventsResult.value.items;
  if (codeReviewResult.status === "fulfilled") {
    liveCodeReview.value = codeReviewResult.value;
  }
  if (
    codeReviewResult.status === "fulfilled" &&
    codeReviewResult.value.gitSnapshotId
  ) {
    try {
      liveGitDiff.value = await apiRequest<GitDiff>(
        `/git-snapshots/${codeReviewResult.value.gitSnapshotId}/diff`,
        { headers: projectHeaders() },
      );
    } catch {
      liveGitDiff.value = null;
    }
  }
  try {
    toolExecutions.value = await apiRequest<ToolExecution[]>(
      `/analysis-runs/${run.id}/tool-executions`,
      { headers: projectHeaders() },
    );
  } catch (error) {
    toolExecutionError.value =
      error instanceof Error
        ? `临时工具结果读取失败：${error.message}`
        : "临时工具结果读取失败。";
  }
}

async function loadReport(projectId: string, cycleId: string | null) {
  if (!cycleId) {
    report.value = null;
    reportPreview.value = null;
    return;
  }
  const reports = await apiRequest<ProjectReport[]>(
    `/projects/${projectId}/report-versions`,
    { headers: projectHeaders() },
  );
  report.value = reports.find((item) => item.cycle_id === cycleId) ?? null;
  reportNote.value = report.value?.editorial_note ?? "";
  if (!report.value) {
    reportPreview.value = null;
    return;
  }
  try {
    reportPreview.value = await apiRequest<ReportPreview>(
      `/projects/${projectId}/report-versions/${report.value.id}/content`,
      { headers: projectHeaders() },
    );
  } catch (error) {
    reportPreview.value = null;
    reportMessage.value =
      error instanceof Error
        ? `报告已保存，但内容回看暂时不可用：${error.message}`
        : "报告已保存，但内容回看暂时不可用。";
  }
}

function applyClaims(claims: DeliveryClaim[]) {
  claimEdits.value = claims.map((claim) => ({
    id: claim.id,
    text: claim.text,
    rationale: claim.rationale,
    origin: claim.origin,
    status: claim.status,
    selected: claim.status === "CONFIRMED",
  }));
  claimProposalAttempted.value = claims.length > 0;
}

async function loadClaims(projectId: string, taskId: string) {
  const claims = await apiRequest<DeliveryClaim[]>(
    `/projects/${projectId}/verification-tasks/${taskId}/delivery-claims`,
    { headers: projectHeaders() },
  );
  applyClaims(claims);
}

async function proposeClaims() {
  const projectId = selectedProjectId.value;
  const taskId = task.value?.id;
  if (!projectId || !taskId) return;
  if (
    claimEdits.value.length > 0 &&
    !window.confirm(
      "重新提取会替换当前未确认的候选交付内容。尚未确认的手动补充也会被替换，是否继续？",
    )
  ) {
    return;
  }
  claimProposalAttempted.value = true;
  busy.value = true;
  claimMessage.value = "正在使用 DeepSeek 提取候选交付内容…";
  try {
    const claims = await apiRequest<DeliveryClaim[]>(
      `/projects/${projectId}/verification-tasks/${taskId}/delivery-claims/propose`,
      {
        method: "POST",
        headers: projectHeaders(true),
        body: JSON.stringify({ source_revision_ids: selectedSourceIds.value }),
      },
    );
    applyClaims(claims);
    claimMessage.value = claims.length
      ? "已生成候选交付内容。请逐条确认、调整或删除后再继续。"
      : "PR 描述和已选资料不足以识别可核验交付内容。请手动补充本次要交付的功能。";
  } catch (error) {
    claimMessage.value =
      error instanceof Error
        ? `候选提取失败：${error.message}`
        : "候选提取失败。请检查 DeepSeek 配置后重试。";
  } finally {
    busy.value = false;
  }
}

function addManualClaim() {
  if (claimEdits.value.length >= 12) return;
  claimEdits.value.push({
    text: "",
    rationale: "提交人补充的交付内容",
    origin: "HUMAN",
    status: "CANDIDATE",
    selected: true,
  });
}

function removeClaim(index: number) {
  claimEdits.value.splice(index, 1);
}

async function confirmClaims() {
  const projectId = selectedProjectId.value;
  const taskId = task.value?.id;
  const claims = claimEdits.value
    .filter((claim) => claim.selected)
    .map((claim) => ({ id: claim.id, text: claim.text.trim() }))
    .filter((claim) => claim.text);
  if (!projectId || !taskId || !claims.length) {
    claimMessage.value = "请至少选择或补充一条本次需要核验的交付内容。";
    return;
  }
  busy.value = true;
  try {
    const confirmed = await apiRequest<DeliveryClaim[]>(
      `/projects/${projectId}/verification-tasks/${taskId}/delivery-claims`,
      {
        method: "PUT",
        headers: projectHeaders(true),
        body: JSON.stringify({ claims }),
      },
    );
    applyClaims(confirmed);
    claimMessage.value = `已确认 ${confirmed.length} 条交付内容；冻结后将不能修改本轮范围。`;
  } catch (error) {
    claimMessage.value =
      error instanceof Error
        ? `确认失败：${error.message}`
        : "交付内容确认失败。";
  } finally {
    busy.value = false;
  }
}

async function createNextCycle() {
  const projectId = selectedProjectId.value;
  const taskId = task.value?.id;
  if (!projectId || !taskId) return;
  busy.value = true;
  try {
    await apiRequest(
      `/projects/${projectId}/verification-tasks/${taskId}/cycles`,
      {
        method: "POST",
        headers: projectHeaders(true),
      },
    );
    preparationMessage.value =
      "已创建新的核验轮次。请重新确认交付内容并冻结新的输入。";
    await loadWorkspace();
  } catch (error) {
    preparationMessage.value =
      error instanceof Error
        ? `创建新轮次失败：${error.message}`
        : "创建新轮次失败。";
  } finally {
    busy.value = false;
  }
}

async function loadWorkspace() {
  stopPolling();
  liveRun.value = null;
  liveEvents.value = [];
  liveOrchestration.value = null;
  liveResults.value = [];
  liveCodeReview.value = { gitSnapshotId: null, findings: [], coverage: [] };
  liveGitDiff.value = null;
  toolExecutions.value = [];
  toolExecutionError.value = "";
  liveLoadError.value = "";
  task.value = null;
  report.value = null;
  reportPreview.value = null;
  claimEdits.value = [];
  claimProposalAttempted.value = false;
  centerView.value = "conclusions";
  selectedDiffPath.value = "";
  const projectId = selectedProjectId.value;
  const taskId = route.params.taskId;
  if (!projectId || !isUuid(taskId)) return;
  try {
    const [taskList, sourceList, repositoryList] = await Promise.all([
      apiRequest<TaskContext[]>(`/projects/${projectId}/verification-tasks`, {
        headers: projectHeaders(),
      }),
      apiRequest<SourceItem[]>(`/projects/${projectId}/sources`, {
        headers: projectHeaders(),
      }),
      apiRequest<GitRepository[]>(`/projects/${projectId}/git-repositories`, {
        headers: projectHeaders(),
      }),
    ]);
    const matchedTask = taskList.find((item) => item.id === taskId);
    if (!matchedTask)
      throw new Error("该核验任务不属于当前项目，或已无权访问。");
    task.value = matchedTask;
    sources.value = sourceList;
    repositories.value = repositoryList;
    if (!gitForm.value.repositoryId && repositoryList.length)
      gitForm.value.repositoryId = repositoryList[0].id;
    if (!matchedTask.formal_snapshot_id && matchedTask.delivery_pull_request) {
      gitForm.value.baseRef =
        matchedTask.delivery_pull_request.baseSha ||
        matchedTask.delivery_pull_request.baseRef ||
        "main";
      gitForm.value.targetRef =
        matchedTask.delivery_pull_request.headSha ||
        matchedTask.delivery_pull_request.headRef ||
        "HEAD";
      gitForm.value.diffMode = "THREE_DOT";
    }
    if (!selectedSourceIds.value.length)
      selectedSourceIds.value = sourceList
        .filter((item) => item.processing_status === "READY")
        .map((item) => item.id);
    await Promise.all([
      loadReport(projectId, matchedTask.cycle_id),
      loadClaims(projectId, matchedTask.id),
    ]);
    try {
      const run = await apiRequest<AnalysisRun>(
        `/verification-tasks/${taskId}/latest-analysis-run`,
        { headers: projectHeaders() },
      );
      await loadRun(run);
      if (
        !["SUCCEEDED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED"].includes(
          run.run_status,
        )
      )
        schedulePoll();
    } catch {
      liveLoadError.value = matchedTask.formal_snapshot_id
        ? "正式快照已创建，尚未启动分析运行。"
        : "";
    }
  } catch (error) {
    liveLoadError.value =
      error instanceof Error ? error.message : "核验任务加载失败";
  }
}

function schedulePoll() {
  stopPolling();
  pollTimer = window.setTimeout(() => {
    void refreshRun();
  }, 3000);
}
async function refreshRun() {
  const runId = liveRun.value?.id;
  const projectId = selectedProjectId.value;
  if (!runId || !projectId) return;
  try {
    const run = await apiRequest<AnalysisRun>(`/analysis-runs/${runId}`, {
      headers: projectHeaders(),
    });
    await loadRun(run);
    if (
      !["SUCCEEDED", "PARTIALLY_COMPLETED", "FAILED", "CANCELLED"].includes(
        run.run_status,
      )
    )
      schedulePoll();
    else {
      await loadReport(projectId, task.value?.cycle_id ?? null);
      reportMessage.value = report.value
        ? "已生成报告草稿。请补充提交说明后提交审批。"
        : "运行已结束，但当前模板没有生成报告草稿。";
    }
  } catch (error) {
    liveLoadError.value =
      error instanceof Error
        ? `运行状态读取失败：${error.message}`
        : "运行状态读取失败。";
  }
}

async function freezeGit() {
  const cycleId = task.value?.cycle_id;
  if (!cycleId || !canFreezeGit.value) return;
  busy.value = true;
  gitFreezeState.value = "working";
  gitFreezeMessage.value = "正在读取指定范围并冻结 Diff…";
  try {
    gitSnapshot.value = await apiRequest<GitSnapshot>(
      `/cycles/${cycleId}/git-snapshots`,
      {
        method: "POST",
        headers: projectHeaders(true),
        body: JSON.stringify({
          repository_id: gitForm.value.repositoryId,
          base_ref: gitForm.value.baseRef.trim(),
          target_ref: gitForm.value.targetRef.trim(),
          diff_mode: gitForm.value.diffMode,
          include_paths: splitPaths(gitForm.value.includePaths),
          exclude_paths: splitPaths(gitForm.value.excludePaths),
        }),
      },
    );
    gitFreezeState.value = "success";
    gitFreezeMessage.value = `已冻结 ${gitSnapshot.value.coverage.changedFiles?.length ?? 0} 个变更文件：${gitSnapshot.value.base_sha.slice(0, 12)}… → ${gitSnapshot.value.target_sha.slice(0, 12)}…`;
    preparationMessage.value = `已冻结 Diff：${gitSnapshot.value.base_sha.slice(0, 12)}… → ${gitSnapshot.value.target_sha.slice(0, 12)}…。现在可创建正式输入快照。`;
  } catch (error) {
    const reason = error instanceof Error ? error.message : "Git Diff 冻结失败";
    gitFreezeState.value = "error";
    gitFreezeMessage.value = reason.includes("指定范围没有可冻结的 Git Diff")
      ? "没有找到代码差异：当前 Base ref 与 Target ref 指向同一提交或没有变更。请把 Target ref 改为包含本次改动的分支或提交，例如 Base 为 main、Target 为 dev。"
      : `冻结失败：${reason}`;
    preparationMessage.value = gitFreezeMessage.value;
  } finally {
    busy.value = false;
  }
}

async function freezeFormalSnapshot() {
  const cycleId = task.value?.cycle_id;
  if (!cycleId || !gitSnapshot.value) return;
  busy.value = true;
  try {
    const snapshot = await apiRequest<{ id: string; snapshot_hash: string }>(
      `/cycles/${cycleId}/input-snapshots/formal`,
      {
        method: "POST",
        headers: projectHeaders(true),
        body: JSON.stringify({
          source_revision_ids: selectedSourceIds.value,
          git_snapshot_id: gitSnapshot.value.id,
          external_evidence_ids: [],
          manual_evidence_ids: [],
        }),
      },
    );
    if (task.value) {
      task.value.formal_snapshot_id = snapshot.id;
      task.value.formal_snapshot_hash = snapshot.snapshot_hash;
    }
    preparationMessage.value =
      "正式输入快照已冻结。后续资料或 Diff 改动必须创建新轮次，不能覆盖本次输入。";
  } catch (error) {
    preparationMessage.value =
      error instanceof Error ? error.message : "正式输入快照创建失败";
  } finally {
    busy.value = false;
  }
}

async function startRun() {
  const snapshotId = task.value?.formal_snapshot_id;
  if (!snapshotId) {
    preparationMessage.value = "请先创建正式输入快照。";
    return;
  }
  busy.value = true;
  try {
    const run = await apiRequest<AnalysisRun>(
      `/input-snapshots/${snapshotId}/analysis-runs`,
      { method: "POST", headers: projectHeaders(true) },
    );
    preparationMessage.value =
      "固定双核已启动。系统每 3 秒读取运行状态、节点事件和核验结果。";
    await loadRun(run);
    schedulePoll();
  } catch (error) {
    preparationMessage.value =
      error instanceof Error ? error.message : "分析运行启动失败";
  } finally {
    busy.value = false;
  }
}

async function saveReport(): Promise<boolean> {
  if (!report.value) return false;
  busy.value = true;
  try {
    const updated = await apiRequest<ProjectReport>(
      `/report-versions/${report.value.id}`,
      {
        method: "PUT",
        headers: projectHeaders(true),
        body: JSON.stringify({
          editorial_note: reportNote.value.trim(),
          item_dispositions: {},
          expected_version: report.value.version,
        }),
      },
    );
    report.value = updated;
    if (selectedProjectId.value && task.value?.cycle_id)
      await loadReport(selectedProjectId.value, task.value.cycle_id);
    if (reportPreview.value)
      reportMessage.value = "报告草稿已保存，可在下方回看本版本内容。";
    return true;
  } catch (error) {
    reportMessage.value =
      error instanceof Error ? error.message : "报告草稿保存失败";
    return false;
  } finally {
    busy.value = false;
  }
}

async function submitReport() {
  if (!report.value || report.value.status !== "DRAFT") return;
  if (unresolvedDecisionCount.value) {
    reportMessage.value = `还有 ${unresolvedDecisionCount.value} 条交付结论等待人工裁决。请在右侧“人工裁决”中逐项处理后再提交。`;
    return;
  }
  busy.value = true;
  try {
    if (
      reportNote.value.trim() !== report.value.editorial_note &&
      !(await saveReport())
    )
      return;
    if (!report.value || report.value.status !== "DRAFT") return;
    report.value = await apiRequest<ProjectReport>(
      `/report-versions/${report.value.id}/submit`,
      { method: "POST", headers: projectHeaders(true) },
    );
    if (selectedProjectId.value && task.value?.cycle_id)
      await loadReport(selectedProjectId.value, task.value.cycle_id);
    reportMessage.value =
      "报告已提交审批。不同成员的审核者可在待审批队列作出决定。";
  } catch (error) {
    reportMessage.value =
      error instanceof Error ? error.message : "报告提交失败";
  } finally {
    busy.value = false;
  }
}

function decisionLabel(decision: string) {
  return ({
    CONFIRM_SUPPORT: "确认交付支持",
    CONFIRM_PARTIAL: "确认部分支持",
    CONFIRM_INSUFFICIENT: "确认当前证据不足",
    RETURN_FOR_EVIDENCE: "退回补充证据",
  } as Record<string, string>)[decision] ?? decision;
}

async function decideConclusion(decision: string) {
  const currentRun = liveRun.value;
  const runId = currentRun?.id;
  const resultId = selectedConclusion.value?.id;
  if (!currentRun || !runId || !resultId || resultId.startsWith("pending-")) return;
  if (
    decision === "RETURN_FOR_EVIDENCE" &&
    !decisionNote.value.trim()
  ) {
    decisionMessage.value = "请说明还需要补充哪些证据。";
    return;
  }
  busy.value = true;
  decisionMessage.value = "正在保存人工裁决…";
  try {
    await apiRequest(`/analysis-runs/${runId}/results/${resultId}/human-decisions`, {
      method: "POST",
      headers: projectHeaders(true),
      body: JSON.stringify({ decision, note: decisionNote.value.trim() }),
    });
    decisionNote.value = "";
    decisionMessage.value = `已${decisionLabel(decision)}，原始系统结论和本次人工裁决都会保留。`;
    await loadRun(currentRun);
    if (selectedProjectId.value && task.value?.cycle_id)
      await loadReport(selectedProjectId.value, task.value.cycle_id);
  } catch (error) {
    decisionMessage.value =
      error instanceof Error ? error.message : "人工裁决保存失败";
  } finally {
    busy.value = false;
  }
}

function toolLocatorLabel(locator: Record<string, unknown>): string {
  return String(locator.host ?? locator.toolKey ?? "已冻结的工具配置");
}
function toolImportName(execution: ToolExecution): string {
  return (
    toolImportNames.value[execution.id] ?? `工具结果-${execution.tool_key}`
  );
}
function showDiffFile(path: string) {
  selectedDiffPath.value = path;
  centerView.value = "diff";
}
async function importToolExecution(execution: ToolExecution) {
  if (!liveRun.value) return;
  const logicalName = toolImportName(execution).trim();
  if (!logicalName) {
    toolImportMessage.value = "请先填写补证名称，再显式导入。";
    return;
  }
  importingToolExecutionId.value = execution.id;
  toolImportMessage.value = "";
  try {
    const imported = await apiRequest<{ manual_evidence_id: string }>(
      `/analysis-runs/${liveRun.value.id}/tool-executions/${execution.id}/import-manual-evidence`,
      {
        method: "POST",
        headers: projectHeaders(true),
        body: JSON.stringify({ logical_name: logicalName }),
      },
    );
    execution.imported_manual_evidence_id = imported.manual_evidence_id;
    toolImportMessage.value =
      "已导入为人工补证；仍需创建新的正式输入快照后才可正式引用。";
  } catch (error) {
    toolImportMessage.value =
      error instanceof Error
        ? `导入失败：${error.message}`
        : "导入失败，请检查当前轮次是否允许补证。";
  } finally {
    importingToolExecutionId.value = "";
  }
}

watch(
  [selectedProjectId, () => route.params.taskId],
  () => {
    void loadWorkspace();
  },
  { immediate: true },
);
onBeforeUnmount(stopPolling);
</script>

<template>
  <section class="notebook-page">
    <header class="notebook-topbar">
      <RouterLink class="notebook-back-button" to="/tasks"
        >返回任务中心</RouterLink
      >
      <div class="notebook-title">
        <h1>{{ task?.title ?? "核验任务" }}</h1>
        <p v-if="liveRun">
          {{ activeRun ? "正在运行" : "运行已结束" }} · 输入快照
          {{ liveRun.snapshot_id.slice(0, 12) }}…
        </p>
        <p v-else-if="task">
          当前轮次 {{ task.cycle_status }} · 按准备步骤形成真实运行
        </p>
        <p v-else>读取当前项目中的核验任务。</p>
      </div>
      <div class="notebook-header-actions">
        <button
          v-if="liveRun"
          class="run-log-trigger"
          type="button"
          aria-haspopup="dialog"
          @click="runLogOpen = true"
        >
          运行记录</button
        ><span class="notebook-status">{{
          liveRun?.run_status ?? task?.cycle_status ?? "未加载"
        }}</span>
      </div>
    </header>
    <p v-if="liveLoadError" class="notebook-live-note">{{ liveLoadError }}</p>
    <section v-if="task && !liveRun" class="surface preparation-panel">
      <div class="surface-heading">
        <div>
          <h2>准备代码审查</h2>
          <p>
            本轮将冻结所选 PR 的只读 Git Diff；不会执行仓库代码、构建、测试或
            Hook。
          </p>
        </div>
      </div>
      <p class="association-note">{{ preparationMessage }}</p>
      <div
        v-if="task.formal_snapshot_id && !confirmedClaimCount"
        class="legacy-cycle-notice"
      >
        <div>
          <strong>此任务已有旧版正式快照</strong>
          <p>
            旧快照没有记录可回放的交付主张，不能直接继续运行。请新建一轮核验，避免改变历史输入。
          </p>
        </div>
        <button type="button" :disabled="busy" @click="createNextCycle">
          新建核验轮次
        </button>
      </div>
      <div class="preparation-grid">
        <section>
          <h3>1. 确认交付内容</h3>
          <p>
            模型只根据 Pull Request 描述和所选资料提出候选，不会读取或判断代码。
          </p>
          <div class="claim-actions">
            <button
              type="button"
              :disabled="
                busy ||
                Boolean(task.formal_snapshot_id) ||
                Boolean(confirmedClaimCount)
              "
              @click="proposeClaims"
            >
              {{ claimEdits.length ? "重新提取候选" : "由 DeepSeek 提取候选" }}
            </button>
            <button
              type="button"
              :disabled="
                busy ||
                Boolean(task.formal_snapshot_id) ||
                !claimProposalAttempted ||
                claimEdits.length >= 12
              "
              @click="addManualClaim"
            >
              补充一条
            </button>
          </div>
          <p class="claim-feedback" :class="{ confirmed: confirmedClaimCount }">
            {{ claimMessage }}
          </p>
          <div
            v-for="(claim, index) in claimEdits"
            :key="claim.id ?? `manual-${index}`"
            class="claim-edit-row"
          >
            <label class="claim-select"
              ><input
                v-model="claim.selected"
                type="checkbox"
                :disabled="busy || Boolean(task.formal_snapshot_id)"
                @change="claim.status = 'CANDIDATE'"
              /><span>纳入本轮</span></label
            >
            <textarea
              v-model="claim.text"
              :disabled="busy || Boolean(task.formal_snapshot_id)"
              placeholder="描述本次需要交付并核验的一个功能结果"
              @input="claim.status = 'CANDIDATE'"
            />
            <small>{{
              claim.origin === "MODEL"
                ? `模型依据：${claim.rationale}`
                : "提交人补充"
            }}</small>
            <button
              type="button"
              :disabled="busy || Boolean(task.formal_snapshot_id)"
              @click="removeClaim(index)"
            >
              删除
            </button>
          </div>
          <p v-if="!claimEdits.length" class="empty-row">
            尚未确认交付内容。请先由 DeepSeek
            生成候选；如果没有识别到内容或模型不可用，再手动补充。
          </p>
          <button
            class="primary-button"
            type="button"
            :disabled="
              busy || Boolean(task.formal_snapshot_id) || !selectedClaimCount
            "
            @click="confirmClaims"
          >
            确认 {{ selectedClaimCount }} 条交付内容
          </button>
        </section>
        <section>
          <h3>2. 补充知识库资料（可选）</h3>
          <label
            v-for="source in readySources"
            :key="source.id"
            class="check-line"
            ><input
              v-model="selectedSourceIds"
              type="checkbox"
              :value="source.id"
              :disabled="busy || Boolean(task.formal_snapshot_id)"
            /><span>{{ source.logical_name }} · v{{ source.revision_no }}</span
            ><small>{{ source.source_role }}</small></label
          >
          <p v-if="!readySources.length" class="empty-row">
            知识库暂无 READY 资料。仍可直接审查本次 PR 的代码变更。
          </p>
        </section>
        <section>
          <h3>3. 冻结 PR Diff</h3>
          <p v-if="task.delivery_pull_request" class="preparation-proof">
            PR #{{ task.delivery_pull_request.number }}：已预填
            {{ task.delivery_pull_request.headRef }} →
            {{ task.delivery_pull_request.baseRef }}，可按需要微调。
          </p>
          <label
            >只读仓库<select
              v-model="gitForm.repositoryId"
              :disabled="busy || Boolean(task.formal_snapshot_id)"
            >
              <option value="" disabled>选择已登记仓库</option>
              <option
                v-for="repository in repositories"
                :key="repository.id"
                :value="repository.id"
              >
                {{ repository.display_url }}
              </option>
            </select></label
          >
          <div class="preparation-fields">
            <label
              >Base ref<input
                v-model="gitForm.baseRef"
                :disabled="busy || Boolean(task.formal_snapshot_id)" /></label
            ><label
              >Target ref<input
                v-model="gitForm.targetRef"
                :disabled="busy || Boolean(task.formal_snapshot_id)"
            /></label>
          </div>
          <label
            >范围模式<select
              v-model="gitForm.diffMode"
              :disabled="busy || Boolean(task.formal_snapshot_id)"
            >
              <option value="TWO_DOT">Two-dot</option>
              <option value="THREE_DOT">Three-dot</option>
            </select></label
          ><label
            >包含路径（可选，逗号或换行分隔）<input
              v-model="gitForm.includePaths"
              :disabled="busy || Boolean(task.formal_snapshot_id)"
              placeholder="src/, backend/" /></label
          ><button
            type="button"
            :disabled="
              busy || Boolean(task.formal_snapshot_id) || !canFreezeGit
            "
            @click="freezeGit"
          >
            {{ gitFreezeState === "working" ? "冻结中…" : "冻结 PR Diff" }}
          </button>
          <p
            v-if="gitFreezeMessage"
            :class="['git-freeze-feedback', gitFreezeState]"
            :role="gitFreezeState === 'error' ? 'alert' : 'status'"
            aria-live="polite"
          >
            {{ gitFreezeMessage }}
          </p>
          <p v-if="gitSnapshot" class="preparation-proof">
            {{ gitSnapshot.base_sha.slice(0, 12) }}… →
            {{ gitSnapshot.target_sha.slice(0, 12) }}… ·
            {{ gitSnapshot.coverage.changedFiles?.length ?? 0 }} 个文件
          </p>
        </section>
        <section>
          <h3>4. 正式快照与运行</h3>
          <p>
            已确认交付内容、本次 PR、可选知识库资料和 Diff
            将被哈希冻结；之后的改动不会回写本轮。
          </p>
          <button
            type="button"
            :disabled="
              busy ||
              Boolean(task.formal_snapshot_id) ||
              !canFreezeFormalSnapshot
            "
            @click="freezeFormalSnapshot"
          >
            创建正式快照
          </button>
          <p v-if="task.formal_snapshot_hash" class="preparation-proof">
            快照：{{ task.formal_snapshot_hash }}
          </p>
          <button
            class="primary-button"
            type="button"
            :disabled="busy || !task.formal_snapshot_id"
            @click="startRun"
          >
            启动真实 DeepSeek 审查
          </button>
          <p class="preparation-proof">
            未配置模型密钥或网络不可达时，系统会记录真实失败，不会改用 Fake
            模型。
          </p>
        </section>
      </div>
    </section>
    <section
      v-if="liveRun && (toolExecutions.length || toolExecutionError)"
      class="tool-execution-strip"
      aria-label="临时工具结果"
    >
      <header>
        <div>
          <h2>临时工具结果</h2>
          <p>仅供外围 Agent 提出建议；不会进入核验结论或报告引用。</p>
        </div>
        <span>需显式导入</span>
      </header>
      <p v-if="toolExecutionError" class="tool-execution-message error">
        {{ toolExecutionError }}
      </p>
      <div
        v-for="execution in toolExecutions"
        :key="execution.id"
        class="tool-execution-row"
      >
        <div class="tool-execution-copy">
          <strong
            >{{ execution.capability_key }} / {{ execution.tool_key }}</strong
          ><small
            >{{ toolLocatorLabel(execution.locator) }} ·
            {{ execution.content_hash.slice(0, 18) }}</small
          >
          <p>{{ execution.excerpt_safe }}</p>
        </div>
        <div class="tool-execution-action">
          <template v-if="execution.imported_manual_evidence_id"
            ><span class="tool-imported">已导入补证</span
            ><small>{{
              execution.imported_manual_evidence_id
            }}</small></template
          ><template v-else
            ><input
              :value="toolImportName(execution)"
              aria-label="补证名称"
              @input="
                toolImportNames[execution.id] = (
                  $event.target as HTMLInputElement
                ).value
              "
            /><button
              type="button"
              :disabled="importingToolExecutionId === execution.id"
              @click="importToolExecution(execution)"
            >
              {{
                importingToolExecutionId === execution.id
                  ? "导入中…"
                  : "显式导入为补证"
              }}
            </button></template
          >
        </div>
      </div>
      <p v-if="toolImportMessage" class="tool-execution-message">
        {{ toolImportMessage }}
      </p>
    </section>
    <main v-if="liveRun" class="notebook-grid">
      <SourceEvidencePane
        :evidence="liveEvidence"
        :snapshot-label="liveRun?.snapshot_id ?? task?.formal_snapshot_hash"
        :live="Boolean(liveRun)"
        :git-diff="liveGitDiff"
        :code-review="liveCodeReview"
        :selected-file-path="selectedDiffFile?.path"
        @select-file="showDiffFile"
      /><VerificationPane
        :conclusions="displayedConclusions"
        :selected-id="selectedId"
        :live="Boolean(liveRun)"
        :view="centerView"
        :selected-file="selectedDiffFile"
        @select="selectedId = $event"
        @change-view="centerView = $event"
      /><ReviewDetailPane
        :conclusion="selectedConclusion"
        :evidence="liveEvidence"
        :orchestration="liveOrchestration"
        :run-status="liveRun?.run_status"
        :run-snapshot-id="liveRun?.snapshot_id"
        :has-report="Boolean(report)"
        :can-decide="Boolean(selectedConclusion?.allowedHumanDecisions?.length && !selectedConclusion?.humanDecision)"
        ><template #decision
          ><div class="human-decision-panel">
            <div class="surface-heading">
              <div>
                <h2>人工裁决</h2>
                <p>系统结论保持原样；此处只记录你是否采纳当前证据。</p>
              </div>
            </div>
            <template v-if="selectedConclusion?.humanDecision">
              <p class="decision-state">已完成：{{ decisionLabel(selectedConclusion.humanDecision.decision) }}</p>
              <p v-if="selectedConclusion.humanDecision.note" class="quiet-note">{{ selectedConclusion.humanDecision.note }}</p>
              <small>裁决时间：{{ selectedConclusion.humanDecision.createdAt ? formatDate(selectedConclusion.humanDecision.createdAt) : '—' }}</small>
            </template>
            <template v-else-if="selectedConclusion?.allowedHumanDecisions?.length">
              <p class="quiet-note">请先阅读“引用”和“代码变更”。只有模型关联时，不能直接确认交付支持。</p>
              <label>裁决说明（退回补证时必填）<textarea v-model="decisionNote" :disabled="busy" placeholder="记录采纳理由、当前缺口或需要补充的证据。" /></label>
              <div class="action-buttons decision-actions">
                <button v-for="decision in selectedConclusion.allowedHumanDecisions" :key="decision" type="button" :class="{ 'primary-button': decision === 'CONFIRM_SUPPORT' }" :disabled="busy" @click="decideConclusion(decision)">{{ decisionLabel(decision) }}</button>
              </div>
            </template>
            <p v-else class="quiet-note">当前系统结论不需要人工裁决，或本轮尚未生成可裁决结果。</p>
            <p v-if="decisionMessage" class="claim-feedback">{{ decisionMessage }}</p>
          </div></template
        ><template #report
          ><div v-if="report" class="report-submit-panel detail-report">
            <div class="surface-heading">
              <div>
                <h2>交付报告</h2>
                <p>
                  报告绑定本次冻结输入与核验结果；提交后仅允许审批或固化，不可直接改写。
                </p>
              </div>
              <span class="status-mark attention">{{ report.status }}</span>
            </div>
            <p class="association-note">{{ reportMessage }}</p>
            <section v-if="reportPreview" class="report-preview" aria-label="已保存的交付报告内容">
              <div class="report-preview-meta">
                <strong>已保存的报告内容</strong>
                <span>v{{ reportPreview.version }} · 输入快照 {{ reportPreview.snapshot_hash.slice(0, 12) }}</span>
              </div>
              <p class="report-preview-note">以下内容来自本报告版本；重新进入该核验任务时仍可在这里回看，不会按当前页面数据重新生成。</p>
              <article v-for="item in reportPreview.items" :key="item.id" class="report-preview-item">
                <div class="report-preview-item-heading">
                  <strong>{{ item.claimText }}</strong>
                  <span class="status-mark">{{ reportConclusionStatus(item) }}</span>
                </div>
                <p v-if="item.result.reason">{{ item.result.reason }}</p>
                <p v-if="item.result.humanDecision" class="report-human-decision">
                  人工裁决：{{ decisionLabel(item.result.humanDecision.decision) }}
                  <template v-if="item.result.humanDecision.note"> · {{ item.result.humanDecision.note }}</template>
                  <template v-if="item.result.humanDecision.createdAt"> · {{ formatDate(item.result.humanDecision.createdAt) }}</template>
                </p>
                <details v-if="item.citations.length" class="report-citations">
                  <summary>冻结引用（{{ item.citations.length }}）</summary>
                  <div v-for="citation in item.citations" :key="citation.id" class="report-citation">
                    <span>{{ citation.sourceType }}</span><p>{{ citation.excerpt }}</p>
                  </div>
                </details>
              </article>
              <p v-if="!reportPreview.items.length" class="quiet-note">该报告版本没有可展示的交付主张。</p>
              <p v-if="reportPreview.editorial_note" class="report-editorial-note"><strong>提交说明</strong>{{ reportPreview.editorial_note }}</p>
            </section>
            <p v-else class="quiet-note">正在读取已保存的报告内容；如读取失败，请刷新后重试。</p>
            <template v-if="report.status === 'DRAFT'"
              ><p v-if="unresolvedDecisionCount" class="report-gate-note">还有 {{ unresolvedDecisionCount }} 条结论等待人工裁决；请先在右侧“人工裁决”中完成处理。</p><label
                >提交说明<textarea
                  v-model="reportNote"
                  :disabled="busy"
                  placeholder="说明本次核验范围、证据限制和需要人工确认的事项。"
                />
              </label>
              <div class="action-buttons">
                <button type="button" :disabled="busy" @click="saveReport">
                  保存草稿</button
                ><button
                  class="primary-button"
                  type="button"
                  :disabled="busy || Boolean(unresolvedDecisionCount)"
                  @click="submitReport"
                >
                  提交审批
                </button>
              </div></template
            >
            <p v-else class="empty-row">
              当前报告状态：{{ report.status }}。{{
                report.status === "SUBMITTED"
                  ? "请由不同成员的审核者进入待审批队列处理。"
                  : report.status === "APPROVED"
                    ? "管理员可在审批详情中固化正式记录。"
                    : "该报告版本仅供回放。"
              }}
            </p>
          </div></template
        ></ReviewDetailPane
      >
    </main>
    <div
      v-if="runLogOpen && liveRun"
      class="run-log-backdrop"
      role="presentation"
      @click.self="runLogOpen = false"
    >
      <section
        class="run-log-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="run-log-title"
      >
        <header>
          <div>
            <h2 id="run-log-title">运行记录</h2>
            <p>
              {{
                activeRun
                  ? "正在执行，系统每 3 秒自动更新。"
                  : "本次执行已结束，可在此回看处理过程。"
              }}
            </p>
          </div>
          <button
            type="button"
            aria-label="关闭运行记录"
            @click="runLogOpen = false"
          >
            关闭
          </button>
        </header>
        <div class="run-log-body">
          <div v-if="activeRun" class="run-events-refresh">
            <span>正在自动更新。</span
            ><button type="button" :disabled="busy" @click="refreshRun">
              立即刷新
            </button>
          </div>
          <p
            v-for="event in liveEvents.slice(-8)"
            :key="event.id"
            class="run-event"
          >
            <strong>{{ runStepLabel(event.nodeId) }}</strong
            ><span
              >{{ runStepStatus(event.status)
              }}<template v-if="event.details?.errorCode">
                · {{ event.details.errorCode }}</template
              ></span
            ><time>{{ formatDate(event.createdAt) }}</time>
          </p>
          <p v-if="!liveEvents.length" class="empty-row">
            暂时没有可展示的运行事件。
          </p>
        </div>
      </section>
    </div>
  </section>
</template>
