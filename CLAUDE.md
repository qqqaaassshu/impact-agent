# CLAUDE.md

This file gives Claude Code the project-specific context needed to work safely in this repository.

## Project Summary

`impact-agent` is a local frontend impact-analysis Agent.

The user provides a local frontend repository path and a natural-language requirement change. The system builds a code index, runs RAG retrieval plus ReAct-style tool use, and returns a reviewable list of candidate impacted files/symbols with reasons and evidence.

V1 is implemented and runnable.

## Current V1 Stack

- Backend: Python, FastAPI, Pydantic.
- Frontend: Vue 3, Vite, TypeScript, plain CSS.
- Metadata store: SQLite under `.impact-agent/`.
- Vector store: Chroma under `.impact-agent/chroma`.
- Chat model: OpenAI-compatible provider, currently used with DeepSeek.
- Embedding model: Ollama provider, currently used with `bge-m3:latest`.
- Tests: pytest, ruff, Vite build.

## Important Architecture Rules

- API routes live in `src/impact_agent/api` and should stay thin.
- Business analysis logic belongs in `src/impact_agent/services`.
- ReAct orchestration belongs in `src/impact_agent/orchestrator`.
- Search tools belong in `src/impact_agent/tools`.
- Provider-specific model logic belongs in `src/impact_agent/providers`.
- Indexing, filtering, SQLite metadata and Chroma writes belong in `src/impact_agent/indexer`.
- Do not bypass provider adapters to call a model directly from business logic.
- Do not let the orchestrator read/write filesystem or database details directly.
- Tools return evidence; final conclusions are assembled by the service layer.

## Storage Rules

- Chroma stores chunk content and embeddings.
- SQLite stores index status, indexed files, chunk metadata, analysis history and feedback skeleton.
- SQLite must not depend on `indexed_chunks.content`.
- Retrieval must be scoped to the latest active indexed repository.
- `.env`, `.impact-agent/`, Chroma files, SQLite files, caches and build outputs must not be committed.

## Indexing Rules

Index frontend code only:

- `.js`
- `.jsx`
- `.ts`
- `.tsx`
- `.vue`
- `.json`

Default excludes include:

- dependencies and build output: `node_modules`, `dist`, `build`, `.next`, `.nuxt`, `coverage`
- local data and caches: `.git`, `.impact-agent`, `.venv`, `.uv-cache`, pytest/ruff caches
- non-business test/mock files: `tests`, `fixtures`, `mock`, `mocks`, `__tests__`, `__mocks__`, `*.test.*`, `*.spec.*`, `mock.*`, `setupTests.*`
- secrets and lockfiles: `.env`, `.env.*`, package lockfiles

For large repositories, prefer `include_paths` such as `jsyh-mobile/src` instead of indexing the whole repository.

## Runtime Commands

Backend:

```bash
UV_CACHE_DIR=.uv-cache uv run uvicorn --app-dir src impact_agent.api.app:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd web
npm run dev -- --host 127.0.0.1 --port 5173
```

Tests:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check .
cd web && npm run build
```

## Environment

Use `.env.example` as the template. Do not commit `.env`.

Expected local embedding setup:

```bash
EMBEDDING_PROVIDER=ollama
EMBEDDING_BASE_URL=http://127.0.0.1:11434
EMBEDDING_MODEL_NAME=bge-m3:latest
```

Expected DeepSeek-compatible chat setup:

```bash
CHAT_MODEL_PROVIDER=openai_compatible
CHAT_MODEL_BASE_URL=https://api.deepseek.com/v1
CHAT_MODEL_NAME=deepseek-chat
CHAT_MODEL_API_KEY=...
```

## User Preferences

- Write code only after thinking through module boundaries.
- After code changes, self-review for redundancy and structure.
- Prefer clear, small modules over premature abstractions.
- Keep behavior evidence-based; do not present unsupported conclusions as certain.
- The UI should show the analysis process, not just a loading state.
- Impact items must explain why a file/symbol may be affected.

## V1 Validation Baseline

Before committing meaningful changes, run:

```bash
uv run --extra dev pytest
uv run --extra dev ruff check .
cd web && npm run build
```

Current V1 baseline:

- `pytest`: 28 passed.
- `ruff`: all checks passed.
- `vite build`: passed.
