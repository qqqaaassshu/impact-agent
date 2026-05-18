from pathlib import Path
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from impact_agent import __version__
from impact_agent.config import get_settings
from impact_agent.indexer.service import build_index
from impact_agent.indexer.store import IndexStore
from impact_agent.models.analysis import AnalyzeRequest
from impact_agent.models.impact import ImpactReport
from impact_agent.models.index import IndexBuildRequest, IndexBuildResult, IndexStatus
from impact_agent.models.search import SearchFileRequest, SearchSymbolRequest, SearchTextRequest
from impact_agent.models.tool import ToolHit
from impact_agent.services.analysis import analyze_requirement, stream_analyze_requirement
from impact_agent.tools.code_search import search_by_file, search_by_symbol, search_by_text


def create_app() -> FastAPI:
    app = FastAPI(title="impact-agent", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:
        settings = get_settings()
        return {
            "status": "ok",
            "version": __version__,
            "data_dir": settings.data_dir,
        }

    @app.get("/api/index/status")
    def index_status() -> IndexStatus:
        settings = get_settings()
        store = IndexStore(Path(settings.data_dir) / "index.sqlite")
        return store.status()

    @app.post("/api/index/build")
    def index_build(request: IndexBuildRequest) -> IndexBuildResult:
        settings = get_settings()
        try:
            return build_index(request.repo_root, settings, include_paths=request.include_paths)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/search/text")
    def search_text(request: SearchTextRequest) -> list[ToolHit]:
        return search_by_text(request.query, limit=request.limit)

    @app.post("/api/search/symbol")
    def search_symbol(request: SearchSymbolRequest) -> list[ToolHit]:
        return search_by_symbol(
            request.symbol,
            symbol_type=request.symbol_type,
            limit=request.limit,
        )

    @app.post("/api/search/file")
    def search_file(request: SearchFileRequest) -> list[ToolHit]:
        return search_by_file(request.file_path, limit=request.limit)

    @app.post("/api/analyze")
    def analyze(request: AnalyzeRequest) -> ImpactReport:
        return analyze_requirement(request)

    @app.post("/api/analyze/stream")
    def analyze_stream(request: AnalyzeRequest) -> StreamingResponse:
        def generate():
            for event in stream_analyze_requirement(request):
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(generate(), media_type="application/x-ndjson")

    return app


app = create_app()
