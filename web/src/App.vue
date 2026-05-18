<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

type IndexStatus = {
  status: string;
  repo_root: string | null;
  indexed_files: number;
  last_built_at: string | null;
};

type ToolHit = {
  file: string;
  symbol: string | null;
  kind: string;
  line_start: number | null;
  line_end: number | null;
  content: string;
};

type ImpactItem = {
  file: string;
  symbol: string | null;
  impact_type: string;
  description: string;
  reason: string;
  evidence: {
    file: string;
    line_start: number | null;
    line_end: number | null;
    snippet: string;
    reason: string;
  }[];
  confidence: "high" | "medium" | "low";
  needs_review: boolean;
};

type ImpactReport = {
  summary: string;
  uncertain: ImpactItem[];
  affected: ImpactItem[];
  excluded: ImpactItem[];
  tool_trace: AnalysisEvent[];
  risk_level: "low" | "medium" | "high";
  overall_confidence: "low" | "medium" | "high";
};

type AnalysisEvent = {
  type: string;
  message?: string;
  action?: string;
  tool?: string;
  query?: string;
  reason?: string;
  result_count?: number;
  error?: string;
  hits?: {
    file: string;
    symbol: string | null;
    kind: string;
    line_start: number | null;
    line_end: number | null;
    content?: string;
  }[];
};

const repoRoot = ref("");
const includePaths = ref("");
const requirement = ref("");
const searchQuery = ref("");
const indexStatus = ref<IndexStatus | null>(null);
const searchResults = ref<ToolHit[]>([]);
const report = ref<ImpactReport | null>(null);
const analysisEvents = ref<AnalysisEvent[]>([]);
const isBuilding = ref(false);
const isSearching = ref(false);
const isAnalyzing = ref(false);
const errorMessage = ref("");

const visibleAnalysisEvents = computed(() => {
  if (analysisEvents.value.length > 0) {
    return analysisEvents.value;
  }
  if (!report.value?.tool_trace?.length) {
    return [];
  }
  return report.value.tool_trace.map((trace) => ({
    type: "tool_result",
    action: trace.tool,
    query: trace.query,
    reason: trace.reason,
    result_count: trace.result_count,
    message: `${trace.tool} 查询「${trace.query}」，命中 ${trace.result_count} 条。`
  }));
});

async function loadIndexStatus() {
  errorMessage.value = "";
  const response = await fetch("/api/index/status");
  if (!response.ok) {
    errorMessage.value = "索引状态读取失败";
    return;
  }
  indexStatus.value = await response.json();
}

async function buildIndex() {
  if (!repoRoot.value.trim()) {
    errorMessage.value = "请先输入仓库路径";
    return;
  }

  isBuilding.value = true;
  errorMessage.value = "";
  try {
    const paths = includePaths.value
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
    const response = await fetch("/api/index/build", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_root: repoRoot.value.trim(),
        include_paths: paths
      })
    });

    if (!response.ok) {
      const payload = await response.json();
      errorMessage.value = payload.detail ?? "索引构建失败";
      return;
    }

    await loadIndexStatus();
  } finally {
    isBuilding.value = false;
  }
}

async function searchText() {
  if (!searchQuery.value.trim()) {
    errorMessage.value = "请输入搜索关键词";
    return;
  }

  isSearching.value = true;
  errorMessage.value = "";
  try {
    const response = await fetch("/api/search/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: searchQuery.value.trim(), limit: 5 })
    });

    if (!response.ok) {
      errorMessage.value = "搜索失败";
      return;
    }

    searchResults.value = await response.json();
  } finally {
    isSearching.value = false;
  }
}

async function analyzeRequirement() {
  if (!requirement.value.trim()) {
    errorMessage.value = "请先输入需求变更描述";
    return;
  }

  isAnalyzing.value = true;
  errorMessage.value = "";
  report.value = null;
  analysisEvents.value = [
    {
      type: "phase",
      message: "分析请求已提交，正在连接后端。"
    }
  ];
  try {
    const response = await fetch("/api/analyze/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        repo_root: repoRoot.value.trim() || indexStatus.value?.repo_root,
        requirement: requirement.value.trim()
      })
    });

    if (!response.ok) {
      errorMessage.value = "分析失败";
      return;
    }

    if (!response.body) {
      errorMessage.value = "浏览器不支持读取分析过程流";
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        handleAnalysisEvent(line);
      }
    }

    if (buffer.trim()) {
      handleAnalysisEvent(buffer);
    }
  } finally {
    isAnalyzing.value = false;
  }
}

function handleAnalysisEvent(line: string) {
  if (!line.trim()) {
    return;
  }
  const event = JSON.parse(line) as AnalysisEvent & { report?: ImpactReport };
  if (event.type === "report" && event.report) {
    report.value = event.report;
  }
  analysisEvents.value.push(event);
}

onMounted(loadIndexStatus);
</script>

<template>
  <main class="shell">
    <section class="workspace">
      <header class="header">
        <p class="eyebrow">impact-agent</p>
        <h1>需求变更影响范围分析</h1>
      </header>

      <form class="analysis-form">
        <label>
          <span>仓库路径</span>
          <input v-model="repoRoot" placeholder="/path/to/frontend-repo" />
        </label>

        <label>
          <span>扫描子路径</span>
          <input v-model="includePaths" placeholder="例如：packages,jsyh-mobile/src" />
        </label>

        <label>
          <span>需求变更描述</span>
          <textarea
            v-model="requirement"
            rows="7"
            placeholder="例如：行情价格字段从分改为元，精度变了。"
          />
        </label>

        <label>
          <span>索引搜索</span>
          <input v-model="searchQuery" placeholder="例如：price / OrderDetail / QuoteCard" />
        </label>

        <div class="actions">
          <button type="button" :disabled="isBuilding" @click="buildIndex">
            {{ isBuilding ? "构建中" : "构建索引" }}
          </button>
          <button type="button" class="secondary" :disabled="isSearching" @click="searchText">
            {{ isSearching ? "搜索中" : "搜索索引" }}
          </button>
          <button type="button" class="secondary" :disabled="isAnalyzing" @click="analyzeRequirement">
            {{ isAnalyzing ? "分析中..." : "开始分析" }}
          </button>
        </div>

        <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

        <section v-if="searchResults.length" class="results">
          <h2>搜索结果</h2>
          <article v-for="hit in searchResults" :key="`${hit.file}-${hit.line_start}`">
            <strong>{{ hit.file }}</strong>
            <span>{{ hit.kind }} · {{ hit.line_start ?? "-" }}-{{ hit.line_end ?? "-" }}</span>
            <pre>{{ hit.content.slice(0, 420) }}</pre>
          </article>
        </section>

        <section v-if="report" class="results">
          <h2>候选影响清单</h2>
          <p class="summary">{{ report.summary }}</p>
          <article v-for="item in report.uncertain" :key="`${item.file}-${item.symbol}`">
            <strong>{{ item.file }}</strong>
            <span>
              {{ item.impact_type }} · {{ item.confidence }} ·
              {{ item.needs_review ? "需人工确认" : "已确认" }}
            </span>
            <p>{{ item.description }}</p>
            <p v-if="item.reason" class="reason">{{ item.reason }}</p>
            <details v-if="item.evidence.length" class="evidence">
              <summary>查看证据</summary>
              <div v-for="evidence in item.evidence" :key="`${evidence.file}-${evidence.line_start}`">
                <span>{{ evidence.file }} · {{ evidence.line_start ?? "-" }}-{{ evidence.line_end ?? "-" }}</span>
                <p>{{ evidence.reason }}</p>
                <pre v-if="evidence.snippet">{{ evidence.snippet }}</pre>
              </div>
            </details>
          </article>
        </section>
      </form>
    </section>

    <aside class="panel">
      <section class="status-block">
        <h2>索引状态</h2>
        <dl>
          <div>
            <dt>状态</dt>
            <dd>{{ indexStatus?.status ?? "读取中" }}</dd>
          </div>
          <div>
            <dt>文件数</dt>
            <dd>{{ indexStatus?.indexed_files ?? 0 }}</dd>
          </div>
          <div>
            <dt>仓库</dt>
            <dd>{{ indexStatus?.repo_root ?? "未构建" }}</dd>
          </div>
          <div v-if="report">
            <dt>风险</dt>
            <dd>{{ report.risk_level }} / {{ report.overall_confidence }}</dd>
          </div>
        </dl>
      </section>

      <h2>分析过程</h2>
      <ol v-if="visibleAnalysisEvents.length" class="trace-list">
        <li
          v-for="(event, index) in visibleAnalysisEvents"
          :key="`${event.type}-${index}`"
          :class="['trace-item', event.type]"
        >
          <strong>{{ event.message ?? event.type }}</strong>
          <span v-if="event.query">
            {{ event.action ?? event.tool }} · {{ event.query }}
          </span>
          <p v-if="event.reason">{{ event.reason }}</p>
          <span v-if="event.result_count !== undefined">命中 {{ event.result_count }} 条</span>
          <ul v-if="event.hits?.length" class="hit-preview">
            <li v-for="hit in event.hits" :key="`${hit.file}-${hit.line_start}`">
              {{ hit.file }} · {{ hit.kind }} · {{ hit.line_start ?? "-" }}
            </li>
          </ul>
        </li>
      </ol>
      <p v-else class="empty-trace">还没有开始分析。</p>
    </aside>
  </main>
</template>
