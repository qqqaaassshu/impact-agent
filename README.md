# impact-agent

## Claude Code CLI 说明

本项目以 Claude Code CLI 作为主要智能体开发与维护入口。项目级协作规范统一维护在 [CLAUDE.md](CLAUDE.md)，后续开发、评审、调试和文档更新均应以该文件为准。

## 1. 项目概述

`impact-agent` 是面向前端代码仓库的需求变更影响范围评估智能体。项目以字段变更场景为切入点，对本地前端工程进行只读扫描，识别字段重命名可能影响的页面、组件、类型定义、接口映射、mock 数据、schema 配置、表格列和表单配置，并生成结构化评估报告。

本项目对应公司“AI 智能体工程化实战培训”第一阶段作业，目标是在明确业务边界内完成一个可运行、可验证、可扩展的业务智能体模块。

## 2. 场景定义

当前业务场景为：字段变更影响范围评估。

典型输入：

- 工程根路径
- 可选扫描子路径
- 字段变更需求描述

典型输出：

- 需求是否属于当前支持范围
- 已确认受影响位置
- 已排除位置
- 静态分析无法确认的位置
- 证据链
- 风险等级
- 整体置信度

## 3. 当前功能范围

当前版本支持：

- 变更类型：`field_rename`
- 代码源：本地代码仓库
- 前端框架：Vue、React
- 文件类型：`.ts` `.tsx` `.js` `.jsx` `.vue` `.json`
- 交互入口：CLI、Web 页面、Web 流式接口
- 运行方式：只读分析，不修改被分析仓库

当前版本不承诺支持：

- 功能变更 `feature_change` 的完整分析链路
- GitLab 远程代码源
- 全量 AST 深度分析
- 自动修复、自动提交、自动创建 MR
- 跨仓库、跨服务、跨语言影响链分析

## 4. 交付状态说明

当前项目定位为培训第一阶段可交付的智能体最小可用版本，具备以下基础能力：

- 基于 LangGraph 的多阶段流程编排
- 基于本地代码源的确定性扫描能力
- 面向前端字段变更的证据分类能力
- 由前端检索 Skill 提供的关键词搜索和 AST 分析能力
- 面向 Vue / React 的上下文分析能力
- 面向高风险不确定项的有限 LLM 复核能力
- 面向 Web 的流式阶段状态展示能力
- 面向评审和后续集成的结构化报告能力

当前项目尚未达到生产级平台标准。正式生产化还需要补充 MCP Tool 服务形态、代码索引缓存、权限控制、审计日志、GitLab 代码源、增量扫描、任务队列和更完整的静态分析能力。

## 5. 核心流程

系统主流程如下：

1. 用户提交工程路径、可选扫描子路径和需求描述
2. `intake` 模块将自然语言需求规范化为结构化请求
3. Agent 判断需求是否属于当前支持范围
4. 不支持的需求直接返回拒绝原因
5. 支持的需求进入前端代码检索流程
6. 扫描引擎召回候选代码证据
7. 字段变更策略对候选证据进行分类
8. Vue / React 分析器补充框架上下文判断
9. 特殊高风险上下文进入有限 LLM 复核
10. 风险与置信度策略生成整体判断
11. 报告构建器输出结构化 JSON
12. Web 端以流式方式展示阶段进度和最终结果

详细架构见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。

## 6. Skill、扫描引擎与 LLM 分工

项目中各能力边界如下：

- Skill：定义前端代码检索工作流、输入输出契约、调用顺序和注意事项
- 扫描引擎：执行本地文件过滤、关键词搜索、上下文截取和结果归一化
- Agent 主流程：负责阶段编排、证据解释、风险评估和报告生成
- LLM：参与需求支持性判断、少量线索补充和高风险上下文复核

LLM 不作为全仓库扫描器，也不作为代码事实的主来源。报告结论应优先依据本地代码证据生成。

当前 Skill 位于 [skills/frontend-impact-search/SKILL.md](skills/frontend-impact-search/SKILL.md)。当前实现已具备本地 Skill 化检索能力，正式 MCP Tool 封装列为后续增强事项。

## 7. 大型仓库处理策略

为适配大型前端项目，当前版本采用分层分析策略：

- 使用字段名和命名变体生成确定性检索线索
- 使用 `ripgrep` 执行多关键词快速召回
- 通过本地规则识别模板、JSX、对象属性、类型定义、mock、schema、列配置和表单配置
- 对已召回的 JS / TS 文件执行有限 AST 分析，识别类型字段、对象属性、配置字段和解构绑定
- 将注释命中、动态字段、变量传递和上下文不足等结果显式标记
- 仅对有限数量的高风险不确定项调用 LLM

LLM 复核默认配置：

- `LLM_CONTEXT_REVIEW=true`
- `MAX_CONTEXT_REVIEW_ITEMS=20`
- LLM 仅可判断已有 evidence
- LLM 不得新增命中文件

该策略用于控制模型调用成本、扫描耗时和误报范围。

## 8. 变量传递处理策略

当前版本支持有限的同文件局部变量传递识别。

可识别场景包括：

- 字段字面量赋值给变量
- 字段字面量作为对象 key 或配置值
- AST 识别到的解构别名和简单属性绑定
- 同文件有限范围内的变量引用

变量传递产生的结果默认标记为 `variable_propagation_reference`，通常进入不确定项或高风险复核队列。当前版本不承诺完整覆盖跨文件变量传播、import alias、类型引用链和调用链分析。

## 9. Web 使用方式

启动后端：

```powershell
python -m uvicorn impact_agent.web.app:app --host 127.0.0.1 --port 8000
```

启动前端：

```powershell
npm.cmd --prefix web run dev -- --host 127.0.0.1 --port 5173
```

访问地址：

```text
http://127.0.0.1:5173/
```

页面输入项：

- 工程路径：例如 `D:\Wrok\product`
- 扫描子路径：可选，留空表示扫描工程根目录
- 需求描述：例如“将订单金额字段从 amount 改为 totalAmount”

Web 展示内容：

- 当前分析阶段
- LLM 参与阶段
- 注释命中和排除原因
- 确认受影响项
- 已排除项
- 不确定项
- 证据链
- 风险等级和整体置信度

Web 页面不设置测试数据默认值。历史记录优先展示 Web 入口产生的分析记录。

## 10. CLI 使用方式

```powershell
python -m impact_agent.cli assess --repo-root "D:\Wrok\product" --requirement "将订单金额字段从 amount 改为 totalAmount"
```

CLI 输出为结构化 JSON，可用于保存评审材料或接入后续流水线。

## 11. LLM 配置

项目默认采用 OpenAI 兼容接口，便于接入国产大模型、公司内部模型网关或代理服务。

基础配置：

```env
LLM_MODEL=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
LLM_API_KEY=your_key_here
LLM_STRUCTURED_MODE=json
```

可使用 provider 别名：

```env
LLM_PROVIDER=qwen
LLM_MODEL=qwen-plus
LLM_API_KEY=your_key_here
```

已预留 provider：

- `deepseek`：DeepSeek
- `qwen`：通义千问 / 阿里百炼
- `zhipu`：智谱 GLM
- `moonshot`：Moonshot / Kimi
- `ark`：火山方舟 / 豆包
- `siliconflow`：硅基流动

公司内部网关配置示例：

```env
LLM_MODEL=your-company-model
LLM_BASE_URL=https://your-company-llm-gateway/v1
LLM_API_KEY=your_key_here
LLM_STRUCTURED_MODE=json
```

大型仓库建议配置：

```env
LLM_CLUE_EXPANSION=false
LLM_SEMANTIC_REVIEW=false
LLM_CONTEXT_REVIEW=true
MAX_CONTEXT_REVIEW_ITEMS=20
```

完整模板见 [.env.example](.env.example)。

## 12. 输出结构

报告核心字段：

- `summary`：评估摘要
- `coverage`：扫描范围和覆盖情况
- `confirmed_affected`：确认受影响项
- `excluded`：确认不受影响项
- `uncertain`：无法静态确认项
- `evidence_chain`：证据链
- `risk_level`：风险等级
- `overall_confidence`：整体置信度

分类原则：

- `confirmed_affected` 必须具备明确代码证据
- `excluded` 必须具备明确排除原因
- `uncertain` 表示动态引用、变量传递、上下文不足或静态分析无法确认

## 13. 测试与验证

后端单测：

```powershell
python -m pytest tests/unit
```

前端构建：

```powershell
npm.cmd --prefix web run build
```

当前测试覆盖：

- 需求支持性判断
- 本地代码源适配
- 前端搜索结果归一化
- 字段变更策略
- Vue / React 分析器
- 注释命中排除
- 变量传递候选识别
- LLM 上下文复核上限
- Web API 和流式进度

## 14. 项目结构

```text
src/impact_agent/
  adapters/              # 代码源与框架适配
  orchestrator/          # LangGraph 编排
  policies/              # 风险与置信度规则
  services/              # 搜索、报告、知识库、上下文复核
  strategies/            # 变更类型分析策略
  web/                   # FastAPI Web API

skills/frontend-impact-search/
  SKILL.md               # 前端检索 Skill 入口
  scripts/local_search.py
  references/search-patterns.md

web/
  src/App.vue            # Web 页面
```

## 15. 后续规划

短期规划：

- 封装正式 MCP Tool
- 准备稳定演示用例和评审截图
- 增加真实项目字段变更样例
- 优化 Web 对高风险 evidence 的展示

中期规划：

- 建立项目索引缓存和增量扫描机制
- 增强 TypeScript AST、import alias、变量传递和类型引用追踪
- 扩展 GitLab 代码源
- 将 `feature_change` 推进为可用分析链路
- 引入人工反馈，沉淀项目级规则

长期规划：

- 接入公司权限体系和审计日志
- 接入 CI / MR 流程
- 支持跨仓库、跨服务影响链
- 支持改造建议生成，并保留人工确认机制

详细规划见 [docs/ROADMAP.md](docs/ROADMAP.md)。
