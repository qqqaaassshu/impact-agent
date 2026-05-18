from pathlib import Path
import hashlib

import chromadb

from impact_agent.config import Settings
from impact_agent.models.tool import ToolHit
from impact_agent.providers.factory import create_embedding_provider


class ChromaVectorStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = chromadb.PersistentClient(path=str(Path(settings.data_dir) / "chroma"))
        self.collection = self.client.get_or_create_collection(name=_collection_name(settings))
        self.embedding_provider = create_embedding_provider(settings)

    def replace_chunks(self, repo_root: Path, chunks: list[ToolHit]) -> None:
        repo_id = str(repo_root)
        existing = self.collection.get(where={"repo_root": repo_id})
        if existing.get("ids"):
            self.collection.delete(ids=existing["ids"])

        if not chunks:
            return

        ids = [_chunk_id(repo_id, index) for index, _ in enumerate(chunks)]
        documents = [_embedding_text(chunk) for chunk in chunks]
        embeddings = self.embedding_provider.embed_documents(documents)
        metadatas = [_metadata(repo_id, chunk) for chunk in chunks]

        self.collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def semantic_search(
        self,
        query: str,
        limit: int = 20,
        repo_root: str | None = None,
    ) -> list[ToolHit]:
        query_embedding = self.embedding_provider.embed_query(query)
        where = {"repo_root": repo_root} if repo_root else None
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=limit,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        hits: list[ToolHit] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        for document, metadata, distance in zip(documents, metadatas, distances, strict=False):
            enriched_metadata = dict(metadata)
            enriched_metadata["distance"] = float(distance)
            hits.append(
                ToolHit(
                    file=str(enriched_metadata.get("file", "")),
                    symbol=enriched_metadata.get("symbol") or None,
                    kind=str(enriched_metadata.get("kind", "chunk")),
                    line_start=_optional_int(enriched_metadata.get("line_start")),
                    line_end=_optional_int(enriched_metadata.get("line_end")),
                    content=document,
                    metadata=enriched_metadata,
                    score=None,
                )
            )
        return hits


def _chunk_id(repo_id: str, index: int) -> str:
    return f"{repo_id}:{index}"


def _collection_name(settings: Settings) -> str:
    digest = hashlib.sha1(str(Path(settings.data_dir).resolve()).encode("utf-8")).hexdigest()[:12]
    return f"impact_agent_chunks_{digest}"


def _embedding_text(chunk: ToolHit) -> str:
    symbol = f"symbol: {chunk.symbol}\n" if chunk.symbol else ""
    return f"file: {chunk.file}\nkind: {chunk.kind}\n{symbol}{chunk.content}"


def _metadata(repo_id: str, chunk: ToolHit) -> dict:
    metadata = {
        "repo_root": repo_id,
        "file": chunk.file,
        "symbol": chunk.symbol or "",
        "kind": chunk.kind,
        "line_start": chunk.line_start or 0,
        "line_end": chunk.line_end or 0,
    }
    for key in ("language", "symbol_kind"):
        if key in chunk.metadata:
            metadata[key] = chunk.metadata[key]
    return metadata


def _optional_int(value) -> int | None:
    if value in (None, 0, ""):
        return None
    return int(value)
