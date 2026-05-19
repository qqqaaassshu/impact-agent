# impact-agent

本文档是 Claude Code CLI 在本仓库中的项目级工作说明。开发、调试、评审和文档更新应优先遵循本文档约定。

## 项目定位

这是一个前端需求变更影响范围分析 Agent。

用户输入本地前端仓库路径和自然语言需求变更描述，系统基于预建代码索引、RAG 检索和 ReAct 工具调用，输出可复核的候选影响范围。

当前 V1 已具备可运行实现：

- FastAPI 后端。
- Vue 3 + Vite 前端。
- SQLite 索引元数据和记忆数据结构。
- Chroma 向量库。
- Ollama `bge-m3` embedding provider。
- OpenAI-compatible chat provider，用于 DeepSeek。
- 流式 ReAct 分析过程展示。

## 当前边界

只考虑前端项目：

- JavaScript
- TypeScript
- Vue
- React
- JSON

V1 暂不支持：

- 自动改代码。
- 自动提交 commit。
- 自动创建 PR / MR。
- Java 后端接口契约分析。
- 跨仓库完整链路分析。
- 生产权限体系。

## 架构约束

目录职责：

- `src/impact_agent/api`：FastAPI route 和 HTTP 边界。
- `src/impact_agent/indexer`：文件扫描、过滤、符号提取、结构提取、chunk、SQLite、Chroma。
- `src/impact_agent/memory`：SQLite 记忆库、分析历史、人工反馈。
- `src/impact_agent/models`：Pydantic / TypedDict 数据模型。
- `src/impact_agent/orchestrator`：ReAct runner 和未来 LangGraph 编排。
- `src/impact_agent/providers`：chat / embedding provider adapter。
- `src/impact_agent/services`：业务服务层。
- `src/impact_agent/tools`：Agent 可调用检索工具。
- `web`：Vue 3 + Vite WebApp。
- `tests`：fixture 和 unit tests。

开发规则：

- API route 应保持轻量，不承载业务逻辑。
- orchestrator 不应直接处理文件系统和数据库细节。
- provider 逻辑应集中在 provider adapter 中。
- Tool 只返回证据，不直接生成最终结论。
- 记忆只能辅助检索和排序，不能替代当前代码证据。
- 所有确定结论都必须能追溯到 evidence。
- SQLite 不存 `indexed_chunks.content`；chunk content 由 Chroma 保存。

## 索引规则

默认索引前端代码文件：

- `.js`
- `.jsx`
- `.ts`
- `.tsx`
- `.vue`
- `.json`

默认排除：

- `.git`
- `.impact-agent`
- `.venv`
- `node_modules`
- `dist`
- `build`
- `.next`
- `.nuxt`
- `coverage`
- `tests`
- `fixtures`
- `mock`
- `mocks`
- `__tests__`
- `__mocks__`
- `*.test.*`
- `*.spec.*`
- `mock.*`
- `setupTests.*`
- lockfile 和 `.env`

构建大仓库时优先使用 `include_paths`，例如 `jsyh-mobile/src`，避免整仓 embedding 过慢。

## 模型与隐私

模型不强制本地运行。

要求：

- chat model 和 embedding model 必须通过 provider adapter 接入。
- provider 预留 `ollama` 和 `openai_compatible`。
- 使用远程模型时，只发送当前分析需要的 query、tool observation 和有限 chunk，不发送整仓。
- API key、token、cookie 不得写入记忆库或 tool trace。
- `.env`、`.impact-agent/`、Chroma 数据、SQLite 数据默认不提交。

## 代码质量要求

编写代码时考虑清楚再编写。代码输出后，必须自我 review：

- 是否存在冗余代码。
- 代码编排是否合理。
- 命名是否表达真实职责。
- 是否过早抽象。
- 是否把将来才需要的复杂度提前塞进来。

优先：

- 小而清楚的模块。
- 明确的数据模型。
- 可测试的纯函数。
- 保守的接口边界。

## 测试要求

改动后优先运行：

```bash
uv run --extra dev pytest
uv run --extra dev ruff check .
cd web && npm run build
```

当前 V1 测试覆盖重点：

- 配置加载。
- API health / index / search / analyze。
- indexer 文件过滤。
- include_paths。
- 最新索引仓库隔离。
- Chroma / SQLite 检索边界。
- Ollama embedding provider。
- memory 初始化。
- ReAct 流式分析接口。
