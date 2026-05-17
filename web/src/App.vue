<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { fetchHistory, fetchHistoryDetail, streamAssessment } from './api'
import type {
  AssessmentHistoryItem,
  AssessmentRecord,
  AssessmentReport,
  AssessmentStreamEvent,
  ClarificationNeeded,
  MatchItem,
  ProgressEvent,
  TraceItem,
  UnsupportedRequest,
} from './types'

const form = reactive({
  root_path: '',
  repo_path: '',
  requirement: '',
})

const clarificationAnswer = ref('')
const loading = ref(false)
const historyLoading = ref(false)
const histories = ref<AssessmentHistoryItem[]>([])
const report = ref<AssessmentReport | null>(null)
const clarification = ref<ClarificationNeeded | null>(null)
const unsupported = ref<UnsupportedRequest | null>(null)
const selectedHistoryId = ref<string | null>(null)
const errorMessage = ref('')
const progressEvents = ref<ProgressEvent[]>([])
const streamStatus = ref<'idle' | 'running' | 'done' | 'error'>('idle')

const evidenceItems = computed(() => report.value?.evidence_chain?.items ?? [])
const coverageItems = computed(() => {
  if (!report.value) return []
  return Object.entries(report.value.coverage).map(([key, value]) => ({
    key,
    label: displayCoverageKey(key),
    value: displayCoverageValue(key, value),
  }))
})

const changeTypeText: Record<string, string> = {
  field_rename: '字段变更',
  feature_change: '功能变更',
}

const riskText: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
  unknown: '未知',
}

const confidenceText: Record<string, string> = {
  high: '高',
  medium: '中',
  low: '低',
  unknown: '未知',
}

const decisionText: Record<string, string> = {
  confirmed_affected: '确定影响',
  uncertain: '不确定',
  excluded: '已排除',
}

const reasonText: Record<string, string> = {
  api_field: '接口字段',
  already_migrated_reference: '已存在新名称引用，默认不作为待修改影响项',
  ast_bracket_property: 'AST 括号属性访问',
  ast_config_field: 'AST 配置字段',
  ast_destructuring_alias: 'AST 解构别名',
  ast_destructuring_property: 'AST 解构字段',
  ast_jsx_attribute: 'AST JSX 属性',
  ast_object_field: 'AST 对象字段定义',
  ast_object_property: 'AST 对象属性访问',
  ast_type_field: 'AST 类型字段定义',
  bracket_property: '括号属性访问',
  comment_match: '注释命中，已排除',
  config_field: '配置字段',
  dynamic_field_reference: '动态字段引用',
  file_read_failed: '文件读取失败',
  jsx_expression: 'JSX 表达式引用',
  llm_semantic_confirmed: '语义判断为受影响',
  llm_semantic_excluded: '语义判断为可排除',
  object_field: '对象字段定义',
  object_property: '对象属性访问',
  react_bracket_property: 'React 括号属性访问',
  react_config_field: 'React 配置字段',
  react_jsx_expression: 'React JSX 表达式引用',
  react_object_field: 'React 对象字段定义',
  react_object_property: 'React 对象属性访问',
  react_string_key: 'React 字符串键名',
  static_field_reference: '静态字段引用',
  string_key: '字符串键名',
  substring_only_match: '仅子串命中，暂不作为字段引用',
  template_binding: '模板绑定引用',
  template_interpolation: '模板插值引用',
  variable_propagation_reference: '变量传递引用',
  vue_bracket_property: 'Vue 括号属性访问',
  vue_object_field: 'Vue 对象字段定义',
  vue_object_property: 'Vue 对象属性访问',
  vue_string_key: 'Vue 字符串键名',
  vue_template_binding: 'Vue 模板绑定引用',
  vue_template_interpolation: 'Vue 模板插值引用',
}

const traceNodeText: Record<string, string> = {
  analyze_matches: '分析候选命中',
  build_report: '生成报告',
  decide_search_next_step: '判断是否继续检索',
  evaluate_confidence: '评估置信度',
  evaluate_risk: '评估风险',
  generate_clues: '生成检索线索',
  llm_clue_expansion: '大模型扩展关键词',
  llm_context_review: '大模型复核特殊上下文',
  llm_intake: '大模型判断需求',
  llm_semantic_review: '大模型复核动态引用',
  load_knowledge: '读取知识上下文',
  load_source_snapshot: '读取代码源快照',
  review_special_contexts: '特殊场景复核',
  skill_act: '调用 Skill',
  skill_ast_analyze: 'Skill AST 分析',
  validate_request: '校验请求',
}

const traceKeyText: Record<string, string> = {
  action: '动作',
  candidate_count: '候选复核数量',
  confirmed_count: '确定影响数量',
  derived_relation_count: '变量传递派生数量',
  excluded_count: '已排除数量',
  history_count: '历史记录数量',
  keywords: '关键词',
  max_review_items: '复核上限',
  next_keywords: '后续关键词',
  overall_confidence: '整体置信度',
  reason: '原因',
  reasoning: '判断说明',
  reviewed_count: '已复核数量',
  risk_level: '风险等级',
  search_round: '检索轮次',
  search_engine: '检索引擎',
  scanned_files: '命中文件数',
  skill: 'Skill',
  skipped: '跳过原因',
  uncertain_count: '不确定数量',
  ast_analyzed_files: 'AST 分析文件数',
}

const actionText: Record<string, string> = {
  finish: '结束检索',
  search_more: '继续检索',
}

const coverageKeyText: Record<string, string> = {
  confirmed_count: '确定影响数量',
  derived_relation_count: '变量传递派生数量',
  excluded_count: '已排除数量',
  search_roots: '检索范围',
  search_round: '检索轮次',
  searched_keywords: '已检索关键词',
  total_matches: '总命中数',
  uncertain_count: '不确定数量',
}

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
  streamStatus.value = 'running'
  progressEvents.value = []
  errorMessage.value = ''
  clarification.value = null
  unsupported.value = null
  report.value = null
  if (!form.root_path.trim()) {
    errorMessage.value = '请先填写工程路径'
    loading.value = false
    streamStatus.value = 'idle'
    return
  }
  if (!requirement.trim()) {
    errorMessage.value = '请先填写需求描述'
    loading.value = false
    streamStatus.value = 'idle'
    return
  }
  try {
    await streamAssessment(
      {
        requirement,
        root_path: form.root_path.trim(),
        repo_path: form.repo_path.trim() || undefined,
        change_type: 'field_rename',
      },
      handleStreamEvent,
    )
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '分析提交失败'
    streamStatus.value = 'error'
  } finally {
    loading.value = false
  }
}

async function handleStreamEvent(event: AssessmentStreamEvent) {
  if (event.event === 'progress') {
    progressEvents.value.push(event.data)
    return
  }
  if (event.event === 'heartbeat') {
    progressEvents.value.push({
      stage: 'heartbeat',
      title: '持续分析中',
      message: event.data.message,
    })
    return
  }
  if (event.event === 'error') {
    errorMessage.value = event.data.message
    streamStatus.value = 'error'
    return
  }
  if (event.event === 'done') {
    streamStatus.value = 'done'
    return
  }
  if (event.event === 'result') {
    const result = event.data
    if ('kind' in result && result.kind === 'clarification') {
      clarification.value = result
      report.value = null
      return
    }
    if ('kind' in result && result.kind === 'unsupported') {
      unsupported.value = result
      report.value = null
      return
    }
    report.value = result
    clarification.value = null
    selectedHistoryId.value = result.summary.assessment_id ?? null
    void loadHistory()
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
  unsupported.value = null
  streamStatus.value = 'idle'
  progressEvents.value = []
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

function displayChangeType(value?: string | null) {
  return displayMappedText(changeTypeText, value)
}

function displayRisk(value?: string | null) {
  return displayMappedText(riskText, value)
}

function displayConfidence(value?: string | null) {
  return displayMappedText(confidenceText, value)
}

function displayDecision(value?: string | null) {
  return displayMappedText(decisionText, value)
}

function displayReason(value?: string | null) {
  return displayMappedText(reasonText, value)
}

function displaySupportedTypes(values: string[]) {
  return values.map(displayChangeType).join('、')
}

function displayCoverageKey(key: string) {
  return coverageKeyText[key] ?? key
}

function displayCoverageValue(key: string, value: unknown) {
  if (Array.isArray(value)) {
    return value.length ? value.map((item) => String(item)).join('、') : '无'
  }
  if (key.endsWith('confidence') && typeof value === 'string') return displayConfidence(value)
  if (key.endsWith('risk_level') && typeof value === 'string') return displayRisk(value)
  if (value === undefined || value === null || value === '') return '-'
  return String(value)
}

function displayTrace(item: TraceItem) {
  const details = Object.entries(item)
    .filter(([key, value]) => key !== 'node' && value !== undefined && value !== null && value !== '')
    .map(([key, value]) => `${displayTraceKey(key)}：${displayTraceValue(key, value)}`)
  const node = item.node ? displayMappedText(traceNodeText, item.node) : '执行记录'
  return details.length ? `${node}：${details.join('；')}` : node
}

function displayTraceKey(key: string) {
  return traceKeyText[key] ?? key
}

function displayTraceValue(key: string, value: unknown) {
  if (Array.isArray(value)) return value.length ? value.map((item) => String(item)).join('、') : '无'
  if (key === 'action' && typeof value === 'string') return displayMappedText(actionText, value)
  if (key === 'risk_level' && typeof value === 'string') return displayRisk(value)
  if (key === 'overall_confidence' && typeof value === 'string') return displayConfidence(value)
  if (key === 'reason' && typeof value === 'string') return displayReason(value)
  return String(value)
}

function displayMappedText(map: Record<string, string>, value?: string | null) {
  if (!value) return '-'
  return map[value] ?? value
}

onMounted(async () => {
  await loadHistory()
})
</script>

<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1>影响范围评估</h1>
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
          <strong>风险：{{ displayRisk(item.risk_level) }}</strong>
          <span>置信度：{{ displayConfidence(item.overall_confidence) }}</span>
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
            <p>填写本地工程路径和字段变更需求，直接走真实代码检索。</p>
          </div>
          <button class="primary" :disabled="loading" @click="handleSubmit()">
            {{ loading ? '分析中...' : '开始分析' }}
          </button>
        </div>
        <div class="form-grid">
          <label>
            <span>工程路径</span>
            <input v-model="form.root_path" placeholder="例如 D:\\Wrok\\product" />
          </label>
          <label>
            <span>扫描子路径（可选）</span>
            <input v-model="form.repo_path" placeholder="例如 packages\\upgrade_react\\packages\\repo\\src" />
          </label>
        </div>
        <label>
          <span>需求描述</span>
          <textarea v-model="form.requirement" rows="5" placeholder="例如：将字段 integrateAmt 改为 totalIntegrateAmt，评估前端影响范围" />
        </label>
      </section>

      <section v-if="errorMessage" class="panel error-panel">
        {{ errorMessage }}
      </section>

      <section v-if="progressEvents.length > 0 || streamStatus === 'running'" class="panel progress-panel">
        <div class="progress-header">
          <div>
            <h2>分析进度</h2>
            <p>{{ streamStatus === 'running' ? '正在实时推进分析流程' : streamStatus === 'error' ? '分析已停止' : '分析流程已结束' }}</p>
          </div>
          <span class="status-pill" :class="streamStatus">
            {{ streamStatus === 'running' ? '进行中' : streamStatus === 'error' ? '失败' : streamStatus === 'done' ? '完成' : '待开始' }}
          </span>
        </div>
        <ol class="progress-list">
          <li v-for="(item, index) in progressEvents" :key="`${item.stage}-${index}`" class="progress-item">
            <span class="progress-dot" :class="{ active: index === progressEvents.length - 1 && streamStatus === 'running' }"></span>
            <div>
              <strong>{{ item.title }}</strong>
              <p>{{ item.message }}</p>
            </div>
          </li>
        </ol>
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

      <section v-if="unsupported" class="panel unsupported-panel">
        <h2>当前暂不支持</h2>
        <p>{{ unsupported.reason }}</p>
        <p>当前支持：{{ displaySupportedTypes(unsupported.current_supported_change_types) }}</p>
      </section>

      <template v-if="report">
        <section class="panel summary-grid">
          <div class="summary-card">
            <span class="label">变更类型</span>
            <strong>{{ displayChangeType(report.summary.change_type) }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">风险等级</span>
            <strong>{{ displayRisk(report.summary.risk_level) }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">置信度</span>
            <strong>{{ displayConfidence(report.summary.overall_confidence) }}</strong>
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
            <h3>确定影响项</h3>
            <div v-if="report.confirmed_affected.length === 0" class="empty">暂无确定影响项</div>
            <table v-else class="evidence-table">
              <thead><tr><th>文件</th><th>行号</th><th>判定原因</th><th>置信度</th></tr></thead>
              <tbody>
                <tr v-for="item in report.confirmed_affected" :key="item.evidence_id || `${item.file_path}-${item.line_no}`">
                  <td>{{ displayFile(item) }}</td><td>{{ item.line_no ?? '-' }}</td><td>{{ displayReason(item.reason) }}</td><td>{{ displayConfidence(item.confidence) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="match-section">
            <h3>不确定项</h3>
            <div v-if="report.uncertain.length === 0" class="empty">暂无不确定项</div>
            <table v-else class="evidence-table">
              <thead><tr><th>文件</th><th>行号</th><th>判定原因</th><th>置信度</th></tr></thead>
              <tbody>
                <tr v-for="item in report.uncertain" :key="item.evidence_id || `${item.file_path}-${item.line_no}`">
                  <td>{{ displayFile(item) }}</td><td>{{ item.line_no ?? '-' }}</td><td>{{ displayReason(item.reason) }}</td><td>{{ displayConfidence(item.confidence) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="match-section">
            <h3>已排除项</h3>
            <div v-if="report.excluded.length === 0" class="empty">暂无排除项</div>
            <table v-else class="evidence-table">
              <thead><tr><th>文件</th><th>行号</th><th>判定原因</th><th>置信度</th></tr></thead>
              <tbody>
                <tr v-for="item in report.excluded" :key="item.evidence_id || `${item.file_path}-${item.line_no}`">
                  <td>{{ displayFile(item) }}</td><td>{{ item.line_no ?? '-' }}</td><td>{{ displayReason(item.reason) }}</td><td>{{ displayConfidence(item.confidence) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section class="panel">
          <h2>证据链</h2>
          <div v-if="evidenceItems.length === 0" class="empty">暂无证据</div>
          <table v-else class="evidence-table">
            <thead>
              <tr>
                <th>结论</th>
                <th>文件</th>
                <th>行号</th>
                <th>原因</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in evidenceItems" :key="String(item.evidence_id)">
                <td>{{ displayDecision(String(item.decision ?? '')) }}</td>
                <td>{{ displayFile(item) }}</td>
                <td>{{ item.line_no }}</td>
                <td>{{ displayReason(item.reason) }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="panel result-columns two-columns">
          <div>
            <h3>覆盖情况</h3>
            <dl class="coverage-list">
              <div v-for="item in coverageItems" :key="item.key" class="coverage-item">
                <dt>{{ item.label }}</dt>
                <dd>{{ item.value }}</dd>
              </div>
            </dl>
          </div>
          <div>
            <h3>执行轨迹</h3>
            <ul class="trace-list">
              <li v-for="(item, index) in report.trace" :key="index">{{ displayTrace(item) }}</li>
            </ul>
          </div>
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

.form-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  margin-bottom: 16px;
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

.coverage-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin: 0;
}

.coverage-item {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr);
  gap: 12px;
}

.coverage-item dt {
  color: #64748b;
}

.coverage-item dd {
  margin: 0;
  word-break: break-word;
}

.empty {
  color: #94a3b8;
}

.error-panel {
  color: #b91c1c;
  background: #fef2f2;
}

.unsupported-panel {
  color: #92400e;
  background: #fffbeb;
}

.clarification-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.progress-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.progress-header h2,
.progress-header p {
  margin: 0;
}

.progress-header p {
  margin-top: 4px;
  color: #64748b;
}

.status-pill {
  border-radius: 999px;
  padding: 6px 12px;
  background: #e2e8f0;
  color: #334155;
  font-size: 13px;
}

.status-pill.running {
  background: #dbeafe;
  color: #1d4ed8;
}

.status-pill.done {
  background: #dcfce7;
  color: #15803d;
}

.status-pill.error {
  background: #fee2e2;
  color: #b91c1c;
}

.progress-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.progress-item {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr);
  gap: 12px;
}

.progress-item strong {
  display: block;
  color: #0f172a;
}

.progress-item p {
  margin: 4px 0 0;
  color: #64748b;
}

.progress-dot {
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 999px;
  background: #93c5fd;
  box-shadow: 0 0 0 4px #eff6ff;
}

.progress-dot.active {
  background: #2563eb;
  animation: pulse-dot 1.2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }

  50% {
    transform: scale(1.25);
    opacity: 0.65;
  }
}

@media (max-width: 1100px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .summary-grid,
  .form-grid,
  .two-columns {
    grid-template-columns: 1fr;
  }
}
</style>
