# 架构说明

## 1. 文档目的

本文档说明 `impact-agent` 的系统架构、模块职责、运行流程和培训评审维度对应关系。

系统定位为需求变更影响范围评估智能体，当前聚焦字段重命名 `field_rename` 场景。系统通过流程编排、确定性代码扫描、框架上下文分析、有限 LLM 复核和结构化报告生成，实现对前端代码仓库的只读影响评估。

## 2. 设计目标

系统设计目标如下：

- 将自然语言字段变更需求转换为结构化分析请求
- 判断需求是否属于当前支持范围
- 对本地前端代码仓库进行快速候选证据召回
- 对候选证据进行字段变更影响分类
- 对静态分析无法确认的高风险上下文进行有限复核
- 输出可追溯、可复核、可展示的结构化报告

## 3. 总体架构

```text
用户输入
  |
  v
Web / CLI
  |
  v
AssessmentService
  |
  v
LangGraph Orchestrator
  |
  +--> intake
  +--> code source snapshot
  +--> frontend search skill / scan engine
  +--> field rename strategy
  +--> framework analyzers
  +--> context review
  +--> risk / confidence policy
  +--> report builder
```

## 4. 模块职责

`web`

- 提供中文 Web 页面
- 提供 REST API 和 SSE 流式分析接口
- 展示阶段进度、结果分类、风险、置信度和证据链

`services.assessment_service`

- 提供 CLI 和 Web 的统一服务入口
- 负责原始输入到分析请求的转换
- 负责传递分析进度回调

`orchestrator.runner`

- 使用 LangGraph 编排分析阶段
- 管理阶段状态和节点转移
- 不承载具体字段匹配和框架判断逻辑

`strategies.field_rename`

- 生成字段变更搜索线索
- 调用代码源搜索能力
- 将扫描命中转换为 evidence
- 识别注释、动态引用、变量传递等特殊情况

`adapters.code_source`

- 抽象代码来源差异
- 当前优先支持本地代码源
- 后续可扩展 GitLab project/ref/commit

`adapters.framework`

- 处理 Vue 和 React 上下文差异
- 识别模板、JSX、props、对象属性、配置等证据类型

`services.frontend_search`

- 提供 Skill 本地搜索能力的运行时支撑
- 使用 `ripgrep` 执行多关键词搜索
- 对结果进行文件类型、路径和上下文归一化

`services.frontend_impact_skill`

- 作为前端检索 Skill 的运行时适配器
- 暴露 `local_search`、`local_search_many`、`ast_analyze` 等 Skill action
- 返回结构化 observation，供 Agent 策略消费

`skills/frontend-impact-search`

- 拥有前端影响检索能力包
- 包含 Skill 说明、搜索脚本、AST 脚本和规则参考
- 不直接生成最终影响结论

`services.context_review`

- 对已有 uncertain evidence 进行有限复核
- 重点处理动态字段、变量传递、文件读取失败等高风险上下文
- 使用 `MAX_CONTEXT_REVIEW_ITEMS` 控制复核数量
- 不允许 LLM 新增命中文件

`policies`

- 根据 evidence 数量、类型和风险原因计算风险等级
- 根据覆盖情况和不确定项比例计算整体置信度

`services.report_builder`

- 统一报告结构
- 保证 Web 展示、CLI 输出和后续集成使用同一数据契约

`services.knowledge_store`

- 保存历史分析摘要
- 为后续项目画像、索引缓存和人工反馈预留扩展点

## 5. Agent、Skill、扫描引擎与 LLM 边界

Agent 负责流程决策和阶段编排。

Skill 负责定义可复用工作流：

- 输入要求
- 检索线索生成原则
- 本地搜索调用方式
- 输出证据契约
- 不确定项处理原则

扫描引擎负责执行确定性操作：

- 文件枚举
- 路径过滤
- 多关键词搜索
- 上下文截取
- 命中归一化
- 已召回文件的 AST 结构分析

LLM 仅参与局部辅助判断：

- 需求是否属于 `field_rename`
- 少量检索线索补充
- 高风险 evidence 的语义复核
- 报告摘要生成

代码事实以本地扫描证据为准，不以 LLM 推断作为主事实来源。

## 6. LangGraph 阶段

当前主流程节点如下：

- `validate_request`：校验请求是否属于支持范围
- `load_source_snapshot`：加载代码源快照
- `load_knowledge`：读取历史和项目知识
- `generate_clues`：生成搜索线索
- `analyze_matches`：扫描并分析候选命中
- `decide_search_next_step`：判断是否需要补充搜索
- `review_special_contexts`：执行有限 LLM 复核
- `evaluate_risk`：计算风险等级
- `evaluate_confidence`：计算整体置信度
- `build_report`：生成最终报告

Web 流式输出围绕上述阶段展示分析进度。

## 7. 大型仓库性能策略

系统采用确定性扫描优先策略，避免对大型仓库执行高成本模型读取。

当前策略包括：

- 使用 `ripgrep` 作为搜索主路径
- 一次性执行多关键词搜索
- 仅对已召回文件执行 AST 分析
- 默认忽略依赖目录、构建产物和锁文件
- 使用本地规则完成主要证据分类
- 仅选择少量 high-risk uncertain evidence 进入 LLM 复核
- 通过配置限制 LLM 复核数量

后续增强方向：

- 项目级索引缓存
- 文件指纹增量扫描
- TypeScript AST 关系索引
- import alias 解析
- 跨文件引用图

## 8. 变量传递策略

当前版本采用保守的局部追踪策略。

支持能力：

- 识别字段字面量绑定到变量的简单关系
- 在同文件有限窗口内查找变量使用
- 将派生证据标记为 `variable_propagation_reference`
- 将派生证据纳入 uncertain 或高风险复核范围

当前不承诺支持：

- 跨文件变量传播
- 完整 import alias 解析
- 全量类型引用链追踪
- 完整调用链分析

## 9. 培训评审维度对应

业务正确性：

- 场景来源于真实研发流程
- 输入输出边界明确
- 字段变更规则可验证
- 明确区分确认、排除和不确定三类结果

MCP / Skill 集成：

- 已提供前端检索 Skill
- Skill 与扫描脚本职责分离
- 后续可将扫描能力封装为 MCP Tool

代码质量：

- 模块分层清晰
- 核心规则具备单元测试
- Web 和 CLI 共用服务层

架构匹配度：

- 使用 LangGraph 表达多阶段状态流
- 以确定性扫描作为主路径
- LLM 仅在需要判断的有限场景中参与

创新和扩展性：

- 支持 Web 流式阶段展示
- 支持 LLM 复核上限控制
- 支持注释命中排除
- 支持局部变量传递候选识别
- 预留 GitLab、MCP、索引缓存和 `feature_change` 扩展方向
