<script setup lang="ts">
import { computed } from "vue";
import type { VerificationConclusion } from "../../types/workbench";

type GitFile = {
  path: string;
  old_path?: string | null;
  edit_type: string;
  additions: number;
  deletions: number;
  binary: boolean;
  hunks: Array<{ header: string; payload: string }>;
};
type DiffLine = {
  oldNo: string;
  newNo: string;
  kind: "added" | "deleted" | "context";
  content: string;
};

const props = defineProps<{
  conclusions: VerificationConclusion[];
  selectedId: string;
  live?: boolean;
  view: "conclusions" | "diff";
  selectedFile?: GitFile | null;
}>();
const emit = defineEmits<{
  select: [id: string];
  changeView: [view: "conclusions" | "diff"];
}>();

const summary = computed(() => ({
  confirmed: props.conclusions.filter((item) => item.status === "已确认")
    .length,
  partial: props.conclusions.filter((item) => item.status === "部分支持")
    .length,
  insufficient: props.conclusions.filter((item) => item.status === "证据不足")
    .length,
  conflicting: props.conclusions.filter((item) => item.status === "存在冲突")
    .length,
  pending: props.conclusions.filter((item) => item.needsHumanDecision).length,
}));

const deliveryState = computed(() => {
  if (!props.live) return "尚未形成可审批的交付结论";
  if (!props.conclusions.length) return "本轮尚未生成逐项交付结论";
  if (summary.value.conflicting) return "存在需要处理的交付证据冲突";
  if (summary.value.insufficient && summary.value.pending)
    return "存在待人工确认与证据不足项";
  if (summary.value.insufficient) return "存在需要补充证据的交付项";
  if (summary.value.pending || summary.value.partial)
    return "交付结论仍需人工确认";
  return "已形成逐项交付证据结论";
});

function diffLines(header: string, payload: string): DiffLine[] {
  const match = /@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/.exec(header);
  let oldLine = Number(match?.[1] ?? 1);
  let newLine = Number(match?.[2] ?? 1);
  return payload.split("\n").map((line) => {
    if (line.startsWith("+") && !line.startsWith("+++"))
      return {
        oldNo: "",
        newNo: String(newLine++),
        kind: "added" as const,
        content: line.slice(1),
      };
    if (line.startsWith("-") && !line.startsWith("---"))
      return {
        oldNo: String(oldLine++),
        newNo: "",
        kind: "deleted" as const,
        content: line.slice(1),
      };
    return {
      oldNo: String(oldLine++),
      newNo: String(newLine++),
      kind: "context" as const,
      content: line.startsWith(" ") ? line.slice(1) : line,
    };
  });
}
</script>

<template>
  <section class="notebook-pane notebook-verification">
    <header class="notebook-pane-header">
      <div>
        <h2>{{ view === "conclusions" ? "交付核验" : "代码变更" }}</h2>
        <p>
          {{
            view === "conclusions"
              ? live
                ? "当前真实运行结果"
                : "尚未运行固定双核"
              : "冻结 Diff 的只读视图"
          }}
        </p>
      </div>
    </header>
    <nav class="workspace-tabs" aria-label="审查内容">
      <button
        type="button"
        :class="{ active: view === 'conclusions' }"
        @click="emit('changeView', 'conclusions')"
      >
        交付结论</button
      ><button
        type="button"
        :class="{ active: view === 'diff' }"
        @click="emit('changeView', 'diff')"
      >
        代码变更
      </button>
    </nav>
    <template v-if="view === 'conclusions'"
      ><section class="conclusion-banner">
        <span>本轮状态</span><strong>{{ deliveryState }}</strong>
        <p>
          已确认 {{ summary.confirmed }} 项，部分支持
          {{ summary.partial }} 项，证据不足
          {{ summary.insufficient }} 项，待人工确认 {{ summary.pending }} 项。
        </p>
      </section>
      <ol class="conclusion-list">
        <li
          v-for="item in conclusions"
          :key="item.id"
          :class="{ selected: selectedId === item.id }"
        >
          <button type="button" @click="emit('select', item.id)">
            <div class="conclusion-top">
              <strong>{{ item.requirement }}</strong
              ><span :class="['conclusion-status', item.status]">{{
                item.status
              }}</span>
            </div>
            <p>{{ item.summary }}</p>
            <small
              ><span v-if="item.risk" :class="['risk-chip', item.risk]">{{
                item.risk
              }}</span
              >{{
                item.needsHumanDecision
                  ? "需要人工确认"
                  : item.status === "证据不足"
                    ? "需要补充证据"
                    : "证据已形成闭环"
              }}</small
            >
          </button>
        </li>
      </ol></template
    >
    <section v-else-if="selectedFile" class="center-diff-view">
      <header>
        <div>
          <strong>{{ selectedFile.path }}</strong
          ><small
            >{{ selectedFile.edit_type }} · +{{ selectedFile.additions }} / -{{
              selectedFile.deletions
            }}</small
          >
        </div>
        <span>{{ selectedFile.hunks.length }} 个片段</span>
      </header>
      <p v-if="selectedFile.binary" class="quiet-note">
        二进制文件不会进入模型或代码片段视图。
      </p>
      <p v-else-if="!selectedFile.hunks.length" class="quiet-note">
        该文件没有可展示的文本变更片段。
      </p>
      <div
        v-else
        v-for="(hunk, index) in selectedFile.hunks"
        :key="`${selectedFile.path}-${index}`"
        class="center-diff-editor"
      >
        <header>
          <span>片段 {{ index + 1 }}</span
          ><code>{{ hunk.header }}</code>
        </header>
        <div
          v-for="(line, lineIndex) in diffLines(hunk.header, hunk.payload)"
          :key="lineIndex"
          :class="['center-diff-line', line.kind]"
        >
          <span>{{ line.oldNo }}</span
          ><span>{{ line.newNo }}</span
          ><i>{{
            line.kind === "added" ? "+" : line.kind === "deleted" ? "−" : " "
          }}</i
          ><code>{{ line.content }}</code>
        </div>
      </div>
    </section>
    <p v-else class="notebook-empty">
      从左侧选择一个冻结的变更文件，即可在这里查看 IDE Diff。
    </p>
  </section>
</template>
