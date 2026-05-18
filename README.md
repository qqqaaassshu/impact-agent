# impact-agent

需求变更影响范围分析 Agent。开发在改前端需求前，用自然语言描述变更，系统基于本地代码索引、RAG 检索和 ReAct 工具推理，输出可复核的候选影响范围。

## V1 状态

V1 已实现一条可跑通的本地分析链路：

- 前端 WebApp：Vue 3 + Vite。
- 后端 API：FastAPI。
- 代码索引：扫描本地前端仓库，提取文件、符号和轻量结构信息。
- 向量检索：Chroma 存储 chunk content 与 embedding。
- 元数据存储：SQLite 存储索引状态、文件、chunk 元数据、分析历史和反馈骨架。
- Embedding：默认支持 Ollama，本地已按 `bge-m3` 适配。
- Chat model：OpenAI-compatible provider，当前用于接入 DeepSeek。
- ReAct：模型按 JSON 决策调用检索工具，多轮查证后生成候选影响清单。
- 流式过程：`/api/analyze/stream` 会实时输出模型决策、工具调用、命中数量和最终报告。
- 结果解释：每个候选影响项包含原因、证据位置和命中的代码片段。

当前重点是“分析前帮开发找到可能受影响的位置”，不是自动改代码。

## 能力边界

V1 支持：

- 本地单仓库。
- 前端代码：JavaScript、TypeScript、Vue、React、JSON。
- 可选扫描子路径，例如只扫 `jsyh-mobile/src`。
- Chroma 语义检索和 SQLite 精确元数据检索。
- 最新索引仓库隔离，检索只针对最后一次构建的仓库。
- 默认排除依赖、构建产物、mock、fixtures、tests、`*.test.*`、`*.spec.*`、`setupTests.*` 等非业务代码。
- WebApp 展示索引状态、索引搜索、分析过程和候选影响清单。

V1 暂不支持：

- 自动修改代码。
- 自动创建 PR / MR。
- 跨仓库影响分析。
- Java 后端接口契约分析。
- 生产级权限、任务队列和审计。
- Markdown / Word 报告导出。
- 完整 AST 级调用图。

## 架构

```text
web/ Vue App
  |
  | HTTP
  v
FastAPI
  |
  +-- indexer
  |   +-- scanner / filters
  |   +-- symbol_extractor
  |   +-- structure_extractor
  |   +-- SQLite metadata store
  |   +-- Chroma vector store
  |
  +-- tools
  |   +-- search_by_text
  |   +-- search_by_symbol
  |   +-- search_by_file
  |   +-- search_by_usage
  |
  +-- orchestrator
      +-- ReactRunner
      +-- OpenAI-compatible chat provider
      +-- streaming analysis events
```

存储职责：

- Chroma：保存 chunk content、embedding 和语义检索元数据。
- SQLite：保存索引状态、文件元数据、chunk metadata、分析历史和反馈。SQLite 不保存 `indexed_chunks.content`。

## 快速开始

复制环境变量示例：

```bash
cp .env.example .env
```

`.env` 中需要配置：

```bash
CHAT_MODEL_PROVIDER=openai_compatible
CHAT_MODEL_BASE_URL=https://api.deepseek.com/v1
CHAT_MODEL_NAME=deepseek-chat
CHAT_MODEL_API_KEY=你的 key

EMBEDDING_PROVIDER=ollama
EMBEDDING_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL_NAME=bge-m3:latest
```

启动后端：

```bash
UV_CACHE_DIR=.uv-cache uv run uvicorn --app-dir src impact_agent.api.app:app --host 127.0.0.1 --port 8000
```

启动前端：

```bash
cd web
npm run dev -- --host 127.0.0.1 --port 5173
```

打开：

```text
http://127.0.0.1:5173
```

推荐先用子路径构建索引，避免全仓 embedding 太慢：

```text
仓库路径：/Users/huchunming/Documents/工作/qts_v102
扫描子路径：jsyh-mobile/src
```

## API

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

构建索引：

```bash
curl -s -X POST http://127.0.0.1:8000/api/index/build \
  -H 'Content-Type: application/json' \
  -d '{"repo_root":"/path/to/repo","include_paths":["src"]}'
```

搜索：

```bash
curl -s -X POST http://127.0.0.1:8000/api/search/text \
  -H 'Content-Type: application/json' \
  -d '{"query":"price","limit":5}'
```

流式分析：

```bash
curl -s -N -X POST http://127.0.0.1:8000/api/analyze/stream \
  -H 'Content-Type: application/json' \
  -d '{"repo_root":"/path/to/repo","requirement":"price 字段从分改成元","limit":5}'
```

## 目录结构

```text
src/impact_agent/
  api/                  FastAPI routes
  indexer/              文件扫描、过滤、chunk、SQLite、Chroma
  memory/               分析历史和人工反馈骨架
  models/               Pydantic 数据模型
  orchestrator/         ReAct runner 和状态定义
  providers/            chat / embedding provider adapter
  services/             分析服务
  tools/                Agent 检索工具

web/
  src/                  Vue 3 WebApp

tests/
  fixtures/             小型前端样例
  unit/                 单元测试
```

## 测试

```bash
uv run --extra dev pytest
uv run --extra dev ruff check .
cd web && npm run build
```

V1 当前验证结果：

```text
28 passed
ruff check passed
vite build passed
```

## 后续方向

- 索引任务后台化，增加构建进度和取消能力。
- 更完整的 AST / TS Compiler API / Vue SFC 解析。
- 更精细的影响传播：组件引用、路由、store、接口调用链。
- 人工反馈进入排序和记忆。
- 报告导出和 CI / MR 集成。
