<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchHistory, fetchHistoryDetail, submitAssessment } from './api'
import type {
  AssessmentHistoryItem,
  AssessmentRecord,
  AssessmentReport,
  ClarificationNeeded,
  MatchItem,
  TraceItem,
} from './types'

const form = reactive({
  requirement: '将订单金额字段从 amount 改为 totalAmount',
})

const clarificationAnswer = ref('')
const loading = ref(false)
const historyLoading = ref(false)
const histories = ref<AssessmentHistoryItem[]>([])
const report = ref<AssessmentReport | null>(null)
const clarification = ref<ClarificationNeeded | null>(null)
const selectedHistoryId = ref<string | null>(null)
const errorMessage = ref('')

const evidenceItems = computed(() => report.value?.evidence_chain?.items ?? [])
const prettyJson = computed(() => (report.value ? JSON.stringify(report.value, null, 2) : ''))

async function loadHistory() {
  historyLoading.value = true
  try {
    histories.value = await fetchHistory()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '历史记录加载失败'
  } finally {
    historyLoading.value = false
  }
}

async function handleSubmit(requirement = form.requirement) {
  loading.value = true
  errorMessage.value = ''
  clarification.value = null
  try {
    const result = await submitAssessment({ requirement })

    if ('kind' in result && result.kind === 'clarification') {
      clarification.value = result
      report.value = null
      return
    }

    report.value = result
    clarification.value = null
    selectedHistoryId.value = result.summary.assessment_id ?? null
    await loadHistory()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '分析提交失败'
  } finally {
    loading.value = false
  }
}

async function submitClarificationAnswer() {
  const answer = clarificationAnswer.value.trim()
  if (!answer) return
  const mergedRequirement = `${form.requirement}\n补充信息：${answer}`
  form.requirement = mergedRequirement
  clarificationAnswer.value = ''
  await handleSubmit(mergedRequirement)
}

async function openHistory(item: AssessmentHistoryItem) {
  selectedHistoryId.value = item.assessment_id
  errorMessage.value = ''
  clarification.value = null
  try {
    const detail: AssessmentRecord = await fetchHistoryDetail(item.assessment_id)
    report.value = detail.report
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '历史详情加载失败'
  }
}

function formatTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

function displayFile(item: MatchItem) {
  return item.relative_path || item.file_path || '-'
}

function displayTrace(item: TraceItem) {
  const details = Object.entries(item)
    .filter(([key, value]) => key !== 'node' && value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(', ') : String(value)}`)
  return details.length ? `${item.node ?? 'trace'} — ${details.join('；')}` : item.node ?? JSON.stringify(item)
}

onMounted(async () => {
  await loadHistory()
})
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1>impact-agent</h1>
        <p>历史记录</p>
      </div>
      <div v-if="historyLoading" class="empty">历史记录加载中...</div>
      <div v-else-if="histories.length === 0" class="empty">暂无历史记录</div>
      <button
        v-for="item in histories"
        :key="item.assessment_id"
        class="history-item"
        :class="{ active: selectedHistoryId === item.assessment_id }"
        @click="openHistory(item)"
      >
        <div class="history-meta">
          <strong>{{ item.risk_level }}</strong>
          <span>{{ item.overall_confidence }}</span>
        </div>
        <div class="history-requirement">{{ item.requirement }}</div>
        <div class="history-time">{{ formatTime(item.created_at) }}</div>
      </button>
    </aside>

    <main class="content">
      <section class="panel form-panel">
        <div class="panel-header">
          <div>
            <h2>发起分析</h2>
            <p>只需要描述你想做的变更，项目路径和文件范围由后端配置读取。</p>
          </div>
          <button class="primary" :disabled="loading" @click="handleSubmit()">
            {{ loading ? '分析中...' : '开始分析' }}
          </button>
        </div>
        <label>
          <span>需求描述</span>
          <textarea v-model="form.requirement" rows="5" />
        </label>
      </section>

      <section v-if="errorMessage" class="panel error-panel">
        {{ errorMessage }}
      </section>

      <section v-if="clarification" class="panel clarification-panel">
        <h2>需要补充信息</h2>
        <ul>
          <li v-for="question in clarification.questions" :key="question">{{ question }}</li>
        </ul>
        <label>
          <span>补充说明</span>
          <textarea v-model="clarificationAnswer" rows="3" placeholder="在这里补充回答，然后继续分析" />
        </label>
        <button class="primary" :disabled="loading || !clarificationAnswer.trim()" @click="submitClarificationAnswer">
          提交补充并继续分析
        </button>
      </section>

      <template v-if="report">
        <section class="panel summary-grid">
          <div class="summary-card">
            <span class="label">变更类型</span>
            <strong>{{ report.summary.change_type }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">风险等级</span>
            <strong>{{ report.summary.risk_level }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">置信度</span>
            <strong>{{ report.summary.overall_confidence }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">需要人工复核</span>
            <strong>{{ report.summary.needs_human_review ? '是' : '否' }}</strong>
          </div>
        </section>

        <section class="panel">
          <h2>结论摘要</h2>
          <p>{{ report.summary.requirement }}</p>
          <p>{{ report.summary.conclusion }}</p>
          <p v-if="report.next_action"><strong>下一步：</strong>{{ report.next_action }}</p>
        </section>

        <section class="panel">
          <h2>三态结果</h2>
          <div class="match-section">
            <h3>confirmed_affected</h3>
            <div v-if="report.confirmed_affected.length === 0" class="empty">暂无确定影响项</div>
            <table v-else class="evidence-table">
              <thead><tr><th>文件</th><th>行号</th><th>原因</th><th>置信度</th></tr></thead>
              <tbody>
                <tr v-for="item in report.confirmed_affected" :key="item.evidence_id || `${item.file_path}-${item.line_no}`">
                  <td>{{ displayFile(item) }}</td><td>{{ item.line_no ?? '-' }}</td><td>{{ item.reason ?? '-' }}</td><td>{{ item.confidence ?? '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="match-section">
            <h3>uncertain_matches</h3>
            <div v-if="report.uncertain_matches.length === 0" class="empty">暂无不确定项</div>
            <table v-else class="evidence-table">
              <thead><tr><th>文件</th><th>行号</th><th>原因</th><th>置信度</th></tr></thead>
              <tbody>
                <tr v-for="item in report.uncertain_matches" :key="item.evidence_id || `${item.file_path}-${item.line_no}`">
                  <td>{{ displayFile(item) }}</td><td>{{ item.line_no ?? '-' }}</td><td>{{ item.reason ?? '-' }}</td><td>{{ item.confidence ?? '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="match-section">
            <h3>excluded_matches</h3>
            <div v-if="report.excluded_matches.length === 0" class="empty">暂无排除项</div>
            <table v-else class="evidence-table">
              <thead><tr><th>文件</th><th>行号</th><th>原因</th><th>置信度</th></tr></thead>
              <tbody>
                <tr v-for="item in report.excluded_matches" :key="item.evidence_id || `${item.file_path}-${item.line_no}`">
                  <td>{{ displayFile(item) }}</td><td>{{ item.line_no ?? '-' }}</td><td>{{ item.reason ?? '-' }}</td><td>{{ item.confidence ?? '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <h2>Evidence Chain</h2>
          <div v-if="evidenceItems.length === 0" class="empty">暂无 evidence</div>
          <table v-else class="evidence-table">
            <thead>
              <tr>
                <th>decision</th>
                <th>file</th>
                <th>line</th>
                <th>reason</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in evidenceItems" :key="String(item.evidence_id)">
                <td>{{ item.decision }}</td>
                <td>{{ displayFile(item) }}</td>
                <td>{{ item.line_no }}</td>
                <td>{{ item.reason }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="panel result-columns two-columns">
          <div>
            <h3>Coverage</h3>
            <pre>{{ JSON.stringify(report.coverage, null, 2) }}</pre>
          </div>
          <div>
            <h3>Trace</h3>
            <ul class="trace-list">
              <li v-for="(item, index) in report.trace" :key="index">{{ displayTrace(item) }}</li>
            </ul>
          </div>
        </section>

        <section class="panel">
          <h2>原始报告</h2>
          <pre>{{ prettyJson }}</pre>
        </section>
      </template>
    </main>
  </div>
</template>

<style scoped>
.layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  min-height: 100vh;
}

.sidebar {
  background: #0f172a;
  color: white;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar-header h1 {
  margin: 0;
  font-size: 24px;
}

.sidebar-header p {
  margin: 4px 0 0;
  color: #cbd5e1;
}

.history-item {
  text-align: left;
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.4);
  color: white;
  padding: 12px;
  border-radius: 12px;
}

.history-item.active {
  border-color: #38bdf8;
  background: rgba(14, 165, 233, 0.2);
}

.history-meta,
.history-time {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
  color: #cbd5e1;
}

.history-requirement {
  margin: 8px 0;
  font-size: 14px;
}

.content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel {
  background: white;
  border-radius: 16px;
  padding: 20px;
  box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
}

.form-panel .panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.form-panel p {
  margin: 4px 0 0;
  color: #64748b;
}

label {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

label span {
  font-size: 14px;
  color: #475569;
}

input,
textarea {
  width: 100%;
  border: 1px solid #cbd5e1;
  border-radius: 10px;
  padding: 12px;
  background: #fff;
}

.primary {
  border: none;
  border-radius: 10px;
  background: #2563eb;
  color: white;
  padding: 10px 16px;
}

.primary:disabled {
  opacity: 0.6;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 16px;
}

.label {
  display: block;
  color: #64748b;
  font-size: 12px;
  margin-bottom: 8px;
}

.two-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.match-section + .match-section {
  margin-top: 20px;
}

.evidence-table {
  width: 100%;
  border-collapse: collapse;
}

.evidence-table th,
.evidence-table td {
  text-align: left;
  padding: 10px;
  border-bottom: 1px solid #e2e8f0;
  vertical-align: top;
}

.trace-list {
  margin: 0;
  padding-left: 18px;
}

.empty {
  color: #94a3b8;
}

.error-panel {
  color: #b91c1c;
  background: #fef2f2;
}

.clarification-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .summary-grid,
  .two-columns {
    grid-template-columns: 1fr;
  }
}
</style>
