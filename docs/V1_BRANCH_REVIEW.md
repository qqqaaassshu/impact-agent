# V1 分支项目评估

本文档记录 `featureChange` 分支在 V1 阶段的项目优点、当前不足和后续调整方向。它用于帮助后续接手者判断下一步应该优先补哪里，而不是替代 `README.md` 或 `AGENTS.md`。

## 当前结论

这个分支已经具备一个可运行的前端影响范围分析 Agent 雏形：

- 可以构建本地前端仓库索引。
- 可以使用 Chroma 做语义检索。
- 可以使用 SQLite 保存索引元数据和记忆骨架。
- 可以接入 DeepSeek 这类 OpenAI-compatible chat model。
- 可以使用 Ollama `bge-m3` 做本地 embedding。
- 可以通过 WebApp 触发索引、搜索和分析。
- 可以通过流式接口展示 ReAct 分析过程。
- 可以在候选影响项中展示原因和证据。

V1 的价值在于把“需求变更影响范围分析”的核心闭环跑通了：索引、检索、模型决策、工具调用、证据展示、人工复核。

## 优点

### 1. 架构边界已经初步拉开

当前代码按职责拆成了 API、indexer、providers、tools、orchestrator、services、models、memory 和 web。这个拆法是合理的，后续继续扩展 AST、调用链、记忆和反馈时，不需要大面积推翻目录结构。

比较重要的是 provider adapter 已经存在，业务逻辑没有直接绑死 DeepSeek 或 Ollama SDK。后续替换模型、切换远程 embedding 或增加本地模型，都有明确入口。

### 2. RAG 存储职责比较清晰

V1 已经明确：

- Chroma 存 chunk content 和 embedding。
- SQLite 存索引状态、文件信息、chunk metadata、历史和反馈。
- SQLite 不依赖 `indexed_chunks.content`。

这个分工是对的。它避免 SQLite 变成大文本仓库，也让语义检索和精确元数据检索各做各的事。

### 3. ReAct 过程可见

之前点击“分析中”后没有反馈，现在流式接口会输出：

- 当前分析阶段。
- 模型决策。
- 调用的工具。
- 查询参数。
- 查询原因。
- 命中数量。
- 最终报告。

这对这个产品很关键。影响分析不是普通问答，用户必须知道 Agent 查了什么、为什么这么查、查到了什么，才敢相信结果。

### 4. 候选影响项有原因和证据

现在结果不仅列文件，还会包含：

- 为什么认为该文件可能受影响。
- 命中的代码位置。
- 命中的代码片段。
- 是否需要人工确认。

这符合项目目标：输出可复核的影响范围，而不是一个看起来很聪明但不可验证的列表。

### 5. 已处理大仓库的基础风险

V1 已经支持 `include_paths`，可以只扫业务子目录，避免全仓 embedding 过慢。

索引过滤也排除了常见非业务文件：

- `node_modules`
- 构建产物
- mock
- fixtures
- tests
- `*.test.*`
- `*.spec.*`
- `setupTests.*`

同时检索已经按最新 active repo 隔离，避免多个仓库索引混在一起影响分析。

### 6. 有基础测试兜底

当前已有单元测试覆盖：

- 配置加载。
- API health / index / search / analyze。
- 文件过滤。
- include_paths。
- 最新索引仓库隔离。
- Ollama embedding provider。
- memory 初始化。
- ReAct 流式分析接口。

这让 V1 后续迭代有一个基本安全网。

## 不足

### 1. 代码理解还偏轻量

当前 symbol 和 structure 提取主要依赖轻量正则，并不是真正完整 AST。

这意味着它对复杂场景会不稳定，例如：

- TypeScript 类型导出。
- Vue SFC 的 `template` 和 `script setup` 关系。
- React hooks 里的复杂闭包。
- 动态 import。
- alias 路径。
- re-export。
- 组件 props 传递链。
- store 字段流转。

所以 V1 的结果应该被定位为“候选影响范围”，不能当成确定影响闭环。

### 2. Chroma 检索质量还需要调优

当前语义检索能跑通，但还没有做足够的质量优化：

- chunk 粒度比较粗。
- file-level chunk 和 symbol-level chunk 混排。
- 没有 rerank。
- 没有按路径、语言、符号类型做细粒度过滤。
- 没有把结构化调用关系作为排序因素。
- 没有针对中文业务需求和英文代码 token 做 query expansion。

因此有时会出现“语义上接近但业务上不够准”的结果。

### 3. 影响传播还没有真正成图

目前 ReAct 通过工具多轮检索模拟影响传播，但还没有建立可靠的依赖图或调用图。

缺的能力包括：

- 文件 import graph。
- symbol reference graph。
- 组件引用图。
- route 到 page/component 的映射。
- store/action/getter 到使用点的映射。
- API method 到页面调用点的映射。

没有这些图，Agent 很难稳定回答“A 变了会影响 B，B 又会影响 C”的深层链路。

### 4. 索引构建还是同步阻塞

当前 `/api/index/build` 是同步接口。小目录可以接受，大仓库体验会差：

- 页面不知道进度。
- 用户不知道当前卡在扫描、embedding 还是写 Chroma。
- 不能取消。
- 失败恢复弱。

这会直接影响真实项目可用性。

### 5. 记忆还只是骨架

SQLite 已经有 memory / feedback 的方向，但还没有真正进入下一次分析：

- 人工确认结果没有影响排序。
- 历史需求没有被召回。
- 项目常见命名、目录偏好、业务模块边界没有沉淀。

也就是说，V1 还没有做到“越用越顺”。

### 6. 前端体验仍然偏工程原型

WebApp 已经能用，但还是偏调试台：

- 没有任务列表。
- 没有分析历史。
- 没有命中项筛选和分组。
- 没有按文件树查看影响范围。
- 没有确认/排除/标注反馈入口。
- 没有索引构建进度条。

对于日常开发使用，这些都会变成阻力。

### 7. 结论置信度还比较保守

当前影响项大多是 `uncertain` 和 `low confidence`，这是安全的，但还不够有用。

后续需要根据证据类型提升置信度，例如：

- 字段直接命中展示逻辑。
- API 返回字段直接进入组件渲染。
- formatter 直接处理目标字段。
- 类型定义被多个页面引用。
- store 字段被 action 和 UI 同时引用。

这些信号应该进入评分模型。

## 后续调整方向

### P0：让索引和分析更可控

优先做：

- 索引构建改成后台任务。
- 增加 `/api/index/jobs`、进度查询、取消任务。
- 前端展示扫描文件数、embedding 进度、写入 Chroma 进度。
- 增加最大文件大小限制。
- 增加更明确的 include/exclude 配置。
- 允许用户在 UI 中编辑排除规则。

目标是解决“大仓库不知道等多久”的问题。

### P0：补强检索质量

优先做：

- chunk 分层：file、symbol、template、style、api、route、store。
- query expansion：从中文需求中扩展字段名、英文 token、驼峰/下划线变体。
- hybrid search：Chroma 语义检索 + SQLite 精确匹配合并。
- rerank：优先当前业务路径、字段直接命中、symbol 命中、调用关系命中。
- 返回结果去重和聚合到文件级影响项。

目标是减少“看起来相关但不是业务重点”的命中。

### P1：引入真实代码图

建议逐步加入：

- TypeScript Compiler API 或 Tree-sitter。
- Vue SFC parser。
- import/export graph。
- component usage graph。
- API call graph。
- route graph。
- store usage graph。

目标是让影响传播从“模型猜下一步查什么”变成“模型沿着可解释的图做探索”。

### P1：把人工反馈接入记忆

需要补：

- 用户确认受影响。
- 用户排除误报。
- 用户标注原因。
- 下次分析时召回同类历史。
- 按项目目录和业务模块调整排序。

目标是让系统真的越用越顺。

### P1：完善报告结构

建议把结果分成：

- 确认受影响。
- 高风险候选。
- 低风险候选。
- 已排除。
- 需要补充信息。

每项包含：

- 影响原因。
- 证据链。
- 建议检查点。
- 关联文件。
- 置信度来源。

目标是让报告更像开发可执行 checklist。

### P2：改善 WebApp 使用体验

建议做：

- 分析历史列表。
- 文件树视图。
- 命中项按模块/类型分组。
- 影响项确认和排除按钮。
- 索引任务进度。
- 分析过程折叠。
- 一键复制报告。

目标是从工程 Demo 变成日常工具。

### P2：工程化和部署

后续可以补：

- 配置页面。
- 更完善的错误展示。
- provider 健康检查。
- Chroma collection 清理工具。
- 数据目录迁移脚本。
- 集成测试。
- Docker / 本地启动脚本。

## 建议下一步

最建议先做两件事：

1. 索引构建后台化和进度展示。
2. hybrid retrieval + rerank。

原因很简单：前者解决可用性，后者解决结果质量。只有这两点稳定后，再做代码图、记忆和报告体验，收益会更扎实。
