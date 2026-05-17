import { computed, onMounted, reactive, ref } from 'vue';
import { fetchHistory, fetchHistoryDetail, streamAssessment } from './api';
const form = reactive({
    root_path: '',
    repo_path: '',
    requirement: '',
});
const clarificationAnswer = ref('');
const loading = ref(false);
const historyLoading = ref(false);
const histories = ref([]);
const report = ref(null);
const clarification = ref(null);
const unsupported = ref(null);
const selectedHistoryId = ref(null);
const errorMessage = ref('');
const progressEvents = ref([]);
const streamStatus = ref('idle');
const evidenceItems = computed(() => report.value?.evidence_chain?.items ?? []);
const coverageItems = computed(() => {
    if (!report.value)
        return [];
    return Object.entries(report.value.coverage).map(([key, value]) => ({
        key,
        label: displayCoverageKey(key),
        value: displayCoverageValue(key, value),
    }));
});
const changeTypeText = {
    field_rename: '字段变更',
    feature_change: '功能变更',
};
const riskText = {
    high: '高',
    medium: '中',
    low: '低',
    unknown: '未知',
};
const confidenceText = {
    high: '高',
    medium: '中',
    low: '低',
    unknown: '未知',
};
const decisionText = {
    confirmed_affected: '确定影响',
    uncertain: '不确定',
    excluded: '已排除',
};
const reasonText = {
    api_field: '接口字段',
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
};
const traceNodeText = {
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
};
const traceKeyText = {
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
};
const actionText = {
    finish: '结束检索',
    search_more: '继续检索',
};
const coverageKeyText = {
    confirmed_count: '确定影响数量',
    derived_relation_count: '变量传递派生数量',
    excluded_count: '已排除数量',
    search_roots: '检索范围',
    search_round: '检索轮次',
    searched_keywords: '已检索关键词',
    total_matches: '总命中数',
    uncertain_count: '不确定数量',
};
async function loadHistory() {
    historyLoading.value = true;
    try {
        histories.value = await fetchHistory();
    }
    catch (error) {
        errorMessage.value = error instanceof Error ? error.message : '历史记录加载失败';
    }
    finally {
        historyLoading.value = false;
    }
}
async function handleSubmit(requirement = form.requirement) {
    loading.value = true;
    streamStatus.value = 'running';
    progressEvents.value = [];
    errorMessage.value = '';
    clarification.value = null;
    unsupported.value = null;
    report.value = null;
    if (!form.root_path.trim()) {
        errorMessage.value = '请先填写工程路径';
        loading.value = false;
        streamStatus.value = 'idle';
        return;
    }
    if (!requirement.trim()) {
        errorMessage.value = '请先填写需求描述';
        loading.value = false;
        streamStatus.value = 'idle';
        return;
    }
    try {
        await streamAssessment({
            requirement,
            root_path: form.root_path.trim(),
            repo_path: form.repo_path.trim() || undefined,
            change_type: 'field_rename',
        }, handleStreamEvent);
    }
    catch (error) {
        errorMessage.value = error instanceof Error ? error.message : '分析提交失败';
        streamStatus.value = 'error';
    }
    finally {
        loading.value = false;
    }
}
async function handleStreamEvent(event) {
    if (event.event === 'progress') {
        progressEvents.value.push(event.data);
        return;
    }
    if (event.event === 'heartbeat') {
        progressEvents.value.push({
            stage: 'heartbeat',
            title: '持续分析中',
            message: event.data.message,
        });
        return;
    }
    if (event.event === 'error') {
        errorMessage.value = event.data.message;
        streamStatus.value = 'error';
        return;
    }
    if (event.event === 'done') {
        streamStatus.value = 'done';
        return;
    }
    if (event.event === 'result') {
        const result = event.data;
        if ('kind' in result && result.kind === 'clarification') {
            clarification.value = result;
            report.value = null;
            return;
        }
        if ('kind' in result && result.kind === 'unsupported') {
            unsupported.value = result;
            report.value = null;
            return;
        }
        report.value = result;
        clarification.value = null;
        selectedHistoryId.value = result.summary.assessment_id ?? null;
        void loadHistory();
    }
}
async function submitClarificationAnswer() {
    const answer = clarificationAnswer.value.trim();
    if (!answer)
        return;
    const mergedRequirement = `${form.requirement}\n补充信息：${answer}`;
    form.requirement = mergedRequirement;
    clarificationAnswer.value = '';
    await handleSubmit(mergedRequirement);
}
async function openHistory(item) {
    selectedHistoryId.value = item.assessment_id;
    errorMessage.value = '';
    clarification.value = null;
    unsupported.value = null;
    streamStatus.value = 'idle';
    progressEvents.value = [];
    try {
        const detail = await fetchHistoryDetail(item.assessment_id);
        report.value = detail.report;
    }
    catch (error) {
        errorMessage.value = error instanceof Error ? error.message : '历史详情加载失败';
    }
}
function formatTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime()))
        return value;
    return new Intl.DateTimeFormat('zh-CN', {
        month: 'numeric',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    }).format(date);
}
function displayFile(item) {
    return item.relative_path || item.file_path || '-';
}
function displayChangeType(value) {
    return displayMappedText(changeTypeText, value);
}
function displayRisk(value) {
    return displayMappedText(riskText, value);
}
function displayConfidence(value) {
    return displayMappedText(confidenceText, value);
}
function displayDecision(value) {
    return displayMappedText(decisionText, value);
}
function displayReason(value) {
    return displayMappedText(reasonText, value);
}
function displaySupportedTypes(values) {
    return values.map(displayChangeType).join('、');
}
function displayCoverageKey(key) {
    return coverageKeyText[key] ?? key;
}
function displayCoverageValue(key, value) {
    if (Array.isArray(value)) {
        return value.length ? value.map((item) => String(item)).join('、') : '无';
    }
    if (key.endsWith('confidence') && typeof value === 'string')
        return displayConfidence(value);
    if (key.endsWith('risk_level') && typeof value === 'string')
        return displayRisk(value);
    if (value === undefined || value === null || value === '')
        return '-';
    return String(value);
}
function displayTrace(item) {
    const details = Object.entries(item)
        .filter(([key, value]) => key !== 'node' && value !== undefined && value !== null && value !== '')
        .map(([key, value]) => `${displayTraceKey(key)}：${displayTraceValue(key, value)}`);
    const node = item.node ? displayMappedText(traceNodeText, item.node) : '执行记录';
    return details.length ? `${node}：${details.join('；')}` : node;
}
function displayTraceKey(key) {
    return traceKeyText[key] ?? key;
}
function displayTraceValue(key, value) {
    if (Array.isArray(value))
        return value.length ? value.map((item) => String(item)).join('、') : '无';
    if (key === 'action' && typeof value === 'string')
        return displayMappedText(actionText, value);
    if (key === 'risk_level' && typeof value === 'string')
        return displayRisk(value);
    if (key === 'overall_confidence' && typeof value === 'string')
        return displayConfidence(value);
    if (key === 'reason' && typeof value === 'string')
        return displayReason(value);
    return String(value);
}
function displayMappedText(map, value) {
    if (!value)
        return '-';
    return map[value] ?? value;
}
onMounted(async () => {
    await loadHistory();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['sidebar-header']} */ ;
/** @type {__VLS_StyleScopedClasses['history-item']} */ ;
/** @type {__VLS_StyleScopedClasses['form-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['match-section']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-table']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-table']} */ ;
/** @type {__VLS_StyleScopedClasses['coverage-item']} */ ;
/** @type {__VLS_StyleScopedClasses['coverage-item']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-header']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-header']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-header']} */ ;
/** @type {__VLS_StyleScopedClasses['status-pill']} */ ;
/** @type {__VLS_StyleScopedClasses['status-pill']} */ ;
/** @type {__VLS_StyleScopedClasses['status-pill']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-item']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-item']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['active']} */ ;
/** @type {__VLS_StyleScopedClasses['layout']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['form-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['two-columns']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "layout" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
    ...{ class: "sidebar" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "sidebar-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h1, __VLS_intrinsicElements.h1)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
if (__VLS_ctx.historyLoading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty" },
    });
}
else if (__VLS_ctx.histories.length === 0) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "empty" },
    });
}
for (const [item] of __VLS_getVForSourceType((__VLS_ctx.histories))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                __VLS_ctx.openHistory(item);
            } },
        key: (item.assessment_id),
        ...{ class: "history-item" },
        ...{ class: ({ active: __VLS_ctx.selectedHistoryId === item.assessment_id }) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "history-meta" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.displayRisk(item.risk_level));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    (__VLS_ctx.displayConfidence(item.overall_confidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "history-requirement" },
    });
    (item.requirement);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "history-time" },
    });
    (__VLS_ctx.formatTime(item.created_at));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.main, __VLS_intrinsicElements.main)({
    ...{ class: "content" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: "panel form-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "panel-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (...[$event]) => {
            __VLS_ctx.handleSubmit();
        } },
    ...{ class: "primary" },
    disabled: (__VLS_ctx.loading),
});
(__VLS_ctx.loading ? '分析中...' : '开始分析');
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "form-grid" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    placeholder: "\u4f8b\u5982\u0020\u0044\u003a\u005c\u005c\u0057\u0072\u006f\u006b\u005c\u005c\u0070\u0072\u006f\u0064\u0075\u0063\u0074",
});
(__VLS_ctx.form.root_path);
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.input)({
    placeholder: "\u4f8b\u5982\u0020\u0070\u0061\u0063\u006b\u0061\u0067\u0065\u0073\u005c\u005c\u0075\u0070\u0067\u0072\u0061\u0064\u0065\u005f\u0072\u0065\u0061\u0063\u0074\u005c\u005c\u0070\u0061\u0063\u006b\u0061\u0067\u0065\u0073\u005c\u005c\u0072\u0065\u0070\u006f\u005c\u005c\u0073\u0072\u0063",
});
(__VLS_ctx.form.repo_path);
__VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.textarea)({
    value: (__VLS_ctx.form.requirement),
    rows: "5",
    placeholder: "例如：将字段 integrateAmt 改为 totalIntegrateAmt，评估前端影响范围",
});
if (__VLS_ctx.errorMessage) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel error-panel" },
    });
    (__VLS_ctx.errorMessage);
}
if (__VLS_ctx.progressEvents.length > 0 || __VLS_ctx.streamStatus === 'running') {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel progress-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "progress-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.streamStatus === 'running' ? '正在实时推进分析流程' : __VLS_ctx.streamStatus === 'error' ? '分析已停止' : '分析流程已结束');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "status-pill" },
        ...{ class: (__VLS_ctx.streamStatus) },
    });
    (__VLS_ctx.streamStatus === 'running' ? '进行中' : __VLS_ctx.streamStatus === 'error' ? '失败' : __VLS_ctx.streamStatus === 'done' ? '完成' : '待开始');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ol, __VLS_intrinsicElements.ol)({
        ...{ class: "progress-list" },
    });
    for (const [item, index] of __VLS_getVForSourceType((__VLS_ctx.progressEvents))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
            key: (`${item.stage}-${index}`),
            ...{ class: "progress-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "progress-dot" },
            ...{ class: ({ active: index === __VLS_ctx.progressEvents.length - 1 && __VLS_ctx.streamStatus === 'running' }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (item.title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        (item.message);
    }
}
if (__VLS_ctx.clarification) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel clarification-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({});
    for (const [question] of __VLS_getVForSourceType((__VLS_ctx.clarification.questions))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
            key: (question),
        });
        (question);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.label, __VLS_intrinsicElements.label)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.textarea)({
        value: (__VLS_ctx.clarificationAnswer),
        rows: "3",
        placeholder: "在这里补充回答，然后继续分析",
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (__VLS_ctx.submitClarificationAnswer) },
        ...{ class: "primary" },
        disabled: (__VLS_ctx.loading || !__VLS_ctx.clarificationAnswer.trim()),
    });
}
if (__VLS_ctx.unsupported) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel unsupported-panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.unsupported.reason);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.displaySupportedTypes(__VLS_ctx.unsupported.current_supported_change_types));
}
if (__VLS_ctx.report) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel summary-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "summary-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.displayChangeType(__VLS_ctx.report.summary.change_type));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "summary-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.displayRisk(__VLS_ctx.report.summary.risk_level));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "summary-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.displayConfidence(__VLS_ctx.report.summary.overall_confidence));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "summary-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    (__VLS_ctx.report.summary.needs_human_review ? '是' : '否');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.report.summary.requirement);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
    (__VLS_ctx.report.summary.conclusion);
    if (__VLS_ctx.report.next_action) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
        (__VLS_ctx.report.next_action);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "match-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    if (__VLS_ctx.report.confirmed_affected.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.table, __VLS_intrinsicElements.table)({
            ...{ class: "evidence-table" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.thead, __VLS_intrinsicElements.thead)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tbody, __VLS_intrinsicElements.tbody)({});
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.report.confirmed_affected))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({
                key: (item.evidence_id || `${item.file_path}-${item.line_no}`),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayFile(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (item.line_no ?? '-');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayReason(item.reason));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayConfidence(item.confidence));
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "match-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    if (__VLS_ctx.report.uncertain.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.table, __VLS_intrinsicElements.table)({
            ...{ class: "evidence-table" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.thead, __VLS_intrinsicElements.thead)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tbody, __VLS_intrinsicElements.tbody)({});
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.report.uncertain))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({
                key: (item.evidence_id || `${item.file_path}-${item.line_no}`),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayFile(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (item.line_no ?? '-');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayReason(item.reason));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayConfidence(item.confidence));
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "match-section" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    if (__VLS_ctx.report.excluded.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.table, __VLS_intrinsicElements.table)({
            ...{ class: "evidence-table" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.thead, __VLS_intrinsicElements.thead)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tbody, __VLS_intrinsicElements.tbody)({});
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.report.excluded))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({
                key: (item.evidence_id || `${item.file_path}-${item.line_no}`),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayFile(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (item.line_no ?? '-');
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayReason(item.reason));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayConfidence(item.confidence));
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({});
    if (__VLS_ctx.evidenceItems.length === 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "empty" },
        });
    }
    else {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.table, __VLS_intrinsicElements.table)({
            ...{ class: "evidence-table" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.thead, __VLS_intrinsicElements.thead)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.th, __VLS_intrinsicElements.th)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.tbody, __VLS_intrinsicElements.tbody)({});
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.evidenceItems))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.tr, __VLS_intrinsicElements.tr)({
                key: (String(item.evidence_id)),
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayDecision(String(item.decision ?? '')));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayFile(item));
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (item.line_no);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.td, __VLS_intrinsicElements.td)({});
            (__VLS_ctx.displayReason(item.reason));
        }
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "panel result-columns two-columns" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.dl, __VLS_intrinsicElements.dl)({
        ...{ class: "coverage-list" },
    });
    for (const [item] of __VLS_getVForSourceType((__VLS_ctx.coverageItems))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            key: (item.key),
            ...{ class: "coverage-item" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.dt, __VLS_intrinsicElements.dt)({});
        (item.label);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.dd, __VLS_intrinsicElements.dd)({});
        (item.value);
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
        ...{ class: "trace-list" },
    });
    for (const [item, index] of __VLS_getVForSourceType((__VLS_ctx.report.trace))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
            key: (index),
        });
        (__VLS_ctx.displayTrace(item));
    }
}
/** @type {__VLS_StyleScopedClasses['layout']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-header']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['history-item']} */ ;
/** @type {__VLS_StyleScopedClasses['history-meta']} */ ;
/** @type {__VLS_StyleScopedClasses['history-requirement']} */ ;
/** @type {__VLS_StyleScopedClasses['history-time']} */ ;
/** @type {__VLS_StyleScopedClasses['content']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['form-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel-header']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['form-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['error-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-header']} */ ;
/** @type {__VLS_StyleScopedClasses['status-pill']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-list']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-item']} */ ;
/** @type {__VLS_StyleScopedClasses['progress-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['clarification-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['primary']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['unsupported-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['label']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['match-section']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-table']} */ ;
/** @type {__VLS_StyleScopedClasses['match-section']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-table']} */ ;
/** @type {__VLS_StyleScopedClasses['match-section']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-table']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['empty']} */ ;
/** @type {__VLS_StyleScopedClasses['evidence-table']} */ ;
/** @type {__VLS_StyleScopedClasses['panel']} */ ;
/** @type {__VLS_StyleScopedClasses['result-columns']} */ ;
/** @type {__VLS_StyleScopedClasses['two-columns']} */ ;
/** @type {__VLS_StyleScopedClasses['coverage-list']} */ ;
/** @type {__VLS_StyleScopedClasses['coverage-item']} */ ;
/** @type {__VLS_StyleScopedClasses['trace-list']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            form: form,
            clarificationAnswer: clarificationAnswer,
            loading: loading,
            historyLoading: historyLoading,
            histories: histories,
            report: report,
            clarification: clarification,
            unsupported: unsupported,
            selectedHistoryId: selectedHistoryId,
            errorMessage: errorMessage,
            progressEvents: progressEvents,
            streamStatus: streamStatus,
            evidenceItems: evidenceItems,
            coverageItems: coverageItems,
            handleSubmit: handleSubmit,
            submitClarificationAnswer: submitClarificationAnswer,
            openHistory: openHistory,
            formatTime: formatTime,
            displayFile: displayFile,
            displayChangeType: displayChangeType,
            displayRisk: displayRisk,
            displayConfidence: displayConfidence,
            displayDecision: displayDecision,
            displayReason: displayReason,
            displaySupportedTypes: displaySupportedTypes,
            displayTrace: displayTrace,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
