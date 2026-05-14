# impact-agent

## 项目定位

这是一个面向前端代码仓库的“需求变更影响范围评估 Agent”。

当前基础能力范围：

- 字段变更 `field_rename`：当前 MVP 已接通主链路
- 功能变更 `feature_change`：当前是规划中的基础能力，主链路尚未实现

当前必须支持：

- Vue 项目
- React 项目
- 本地代码源
- GitLab 代码源

当前必须输出：

- `confirmed_affected`
- `excluded`
- `uncertain`
- `evidence_chain`
- `risk_level`
- `overall_confidence`

## 架构约束

开发时必须保持以下边界清晰：

- `orchestrator` 只负责流程控制，不写业务匹配细节
- `strategies` 定义不同变更类型的分析方式
- `adapters/code_source` 负责代码从哪里来
- `adapters/framework` 负责 Vue / React 代码如何解释
- `policies` 负责风险和置信度规则
- `services/report_builder` 负责最终 JSON 报告结构
- `services/knowledge_store` 负责项目画像、历史记录、人工反馈

不要把以下逻辑直接散落到主流程中：

- Vue 专属判断
- React 专属判断
- GitLab 专属判断
- 关键词词库
- 路径规则
- 风险阈值

这些应分别下沉到：

- framework analyzer
- code source adapter
- strategy
- policy
- 配置或知识库

## 开发规则

- 当前阶段只做只读分析，不修改被分析仓库代码
- 不实现自动修复、自动提交、自动开 MR、自动部署
- 对不确定项必须显式输出，不能把猜测当成确认结论
- 优先保证主流程和抽象稳定，再逐步加精度
- 每条核心规则都应该可测试
- 优先小函数、可组合实现，避免把逻辑堆进一个大文件
- 不为未来假设场景做过度抽象

## 变更类型规则

### field_rename

重点关注：

- 模板 / JSX 字段引用
- 对象属性访问
- 类型定义
- API 字段
- mock / fixture
- schema 配置

### feature_change

当前 MVP 暂未实现 `feature_change` 主链路。后续实现时重点关注：

- 页面入口
- 动作按钮或操作列
- 事件绑定
- handler
- API 调用
- 权限点
- 刷新链路
- 调用链

## 框架支持规则

Vue 和 React 都是一等支持对象。

默认文件类型：

- `.ts`
- `.tsx`
- `.js`
- `.jsx`
- `.vue`
- `.json`

不要假设：

- 页面只在 `src/views`
- 事件绑定只有 Vue 写法
- 所有列表操作都在同一个组件里
- 所有 API 都是固定目录固定命名

前端框架差异必须通过 `FrameworkAnalyzer` 处理，而不是写死在主流程。

## 代码源规则

必须支持：

- 本地项目目录
- GitLab project/ref

代码源差异必须通过 `CodeSourceAdapter` 处理，而不是写死在 strategy 或 orchestrator 中。

如果分析的是本地代码：

- 要记录当前 commit
- 要记录是否存在未提交变更

如果分析的是 GitLab：

- 要记录 project_id
- 要记录 ref
- 尽量解析到固定 commit

## 输出规则

所有结论必须能回溯到证据。

必须区分：

- `confirmed_affected`
- `excluded`
- `uncertain`

必须输出：

- `summary`
- `coverage`
- `evidence_chain`
- `risk_level`
- `overall_confidence`

如果无法静态确认，必须输出 `uncertain`，不能输出确认结论。

## 测试要求

至少覆盖：

- Vue 字段变更
- React 字段变更
- Vue 功能变更
- React 功能变更
- 不确定项识别
- 证据链生成
- 本地代码源适配
- GitLab 代码源适配

## 当前实现优先级

按以下顺序推进：

1. request / report / state / evidence 模型
2. orchestrator 主流程
3. 本地代码源适配器
4. 字段变更策略
5. 功能变更策略
6. Vue analyzer
7. React analyzer
8. 风险与置信度 policy
9. report builder
10. knowledge store

## 维护说明

这个文件只保留长期有效的项目约束。

不要把临时设计讨论、细碎关键词样例、一次性任务安排写进来。