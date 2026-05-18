import sqlite3
from pathlib import Path

from impact_agent.models.index import IndexStatus, IndexedFile
from impact_agent.models.tool import ToolHit


SCHEMA = """
CREATE TABLE IF NOT EXISTS index_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_root TEXT NOT NULL,
    status TEXT NOT NULL,
    indexed_files INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS indexed_files (
    file TEXT PRIMARY KEY,
    repo_root TEXT NOT NULL,
    language TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    file_hash TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS indexed_chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repo_root TEXT NOT NULL,
    file TEXT NOT NULL,
    symbol TEXT,
    kind TEXT NOT NULL,
    line_start INTEGER,
    line_end INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
"""


class IndexStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA)
            _migrate_indexed_chunks(conn)

    def replace_files(self, repo_root: Path, files: list[IndexedFile], status: str = "ready") -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM indexed_files WHERE repo_root = ?", (str(repo_root),))
            conn.execute("DELETE FROM indexed_chunks WHERE repo_root = ?", (str(repo_root),))
            conn.executemany(
                """
                INSERT INTO indexed_files (file, repo_root, language, size_bytes, file_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (item.file, str(repo_root), item.language, item.size_bytes, item.file_hash)
                    for item in files
                ],
            )
            conn.execute(
                """
                INSERT INTO index_runs (repo_root, status, indexed_files)
                VALUES (?, ?, ?)
                """,
                (str(repo_root), status, len(files)),
            )

    def replace_index(
        self,
        repo_root: Path,
        files: list[IndexedFile],
        chunks: list[ToolHit],
        status: str = "ready",
    ) -> None:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM indexed_files WHERE repo_root = ?", (str(repo_root),))
            conn.execute("DELETE FROM indexed_chunks WHERE repo_root = ?", (str(repo_root),))
            conn.executemany(
                """
                INSERT INTO indexed_files (file, repo_root, language, size_bytes, file_hash)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (item.file, str(repo_root), item.language, item.size_bytes, item.file_hash)
                    for item in files
                ],
            )
            conn.executemany(
                """
                INSERT INTO indexed_chunks (
                    repo_root, file, symbol, kind, line_start, line_end,
                    metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(repo_root),
                        item.file,
                        item.symbol,
                        item.kind,
                        item.line_start,
                        item.line_end,
                        _metadata_to_json(item.metadata),
                    )
                    for item in chunks
                ],
            )
            conn.execute(
                """
                INSERT INTO index_runs (repo_root, status, indexed_files)
                VALUES (?, ?, ?)
                """,
                (str(repo_root), status, len(files)),
            )

    def status(self) -> IndexStatus:
        self.initialize()
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT repo_root, status, indexed_files, created_at
                FROM index_runs
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

        if row is None:
            return IndexStatus(status="empty")

        repo_root, status, indexed_files, created_at = row
        return IndexStatus(
            status=status,
            repo_root=repo_root,
            indexed_files=indexed_files,
            last_built_at=created_at,
        )

    def active_repo_root(self) -> str | None:
        return self.status().repo_root

    def search_text(self, query: str, limit: int = 20) -> list[ToolHit]:
        self.initialize()
        pattern = f"%{query}%"
        repo_root = self.active_repo_root()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT file, symbol, kind, line_start, line_end, metadata_json
                FROM indexed_chunks
                WHERE repo_root = ?
                    AND (file LIKE ? OR symbol LIKE ? OR metadata_json LIKE ?)
                ORDER BY file
                LIMIT ?
                """,
                (repo_root, pattern, pattern, pattern, limit),
            ).fetchall()
        return [_row_to_hit(row) for row in rows]

    def search_symbol(self, symbol: str, limit: int = 20) -> list[ToolHit]:
        self.initialize()
        repo_root = self.active_repo_root()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT file, symbol, kind, line_start, line_end, metadata_json
                FROM indexed_chunks
                WHERE repo_root = ? AND symbol = ?
                ORDER BY
                    CASE kind
                        WHEN 'function' THEN 0
                        WHEN 'class' THEN 1
                        WHEN 'const' THEN 2
                        WHEN 'interface' THEN 3
                        WHEN 'type' THEN 4
                        WHEN 'import' THEN 5
                        ELSE 6
                    END,
                    file
                LIMIT ?
                """,
                (repo_root, symbol, limit),
            ).fetchall()

        if rows:
            hits = [_row_to_hit(row) for row in rows]
            return sorted(hits, key=lambda hit: _usage_rank(hit, symbol))
        return self.search_text(symbol, limit=limit)

    def search_usage(self, symbol: str, limit: int = 20) -> list[ToolHit]:
        self.initialize()
        repo_root = self.active_repo_root()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT file, symbol, kind, line_start, line_end, metadata_json
                FROM indexed_chunks
                WHERE repo_root = ? AND metadata_json LIKE ?
                ORDER BY
                    CASE kind
                        WHEN 'file' THEN 1
                        ELSE 0
                    END,
                    file
                LIMIT ?
                """,
                (repo_root, f"%{symbol}%", limit),
            ).fetchall()

        if rows:
            return [_row_to_hit(row) for row in rows]
        return self.search_text(symbol, limit=limit)

    def search_file(self, file_path: str, limit: int = 20) -> list[ToolHit]:
        self.initialize()
        pattern = f"%{file_path}%"
        repo_root = self.active_repo_root()
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT file, symbol, kind, line_start, line_end, metadata_json
                FROM indexed_chunks
                WHERE repo_root = ? AND file LIKE ?
                ORDER BY file
                LIMIT ?
                """,
                (repo_root, pattern, limit),
            ).fetchall()
        return [_row_to_hit(row) for row in rows]


def _metadata_to_json(metadata: dict) -> str:
    import json

    return json.dumps(metadata, ensure_ascii=False)


def _migrate_indexed_chunks(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(indexed_chunks)").fetchall()
    if not any(column[1] == "content" for column in columns):
        return

    conn.execute("DROP TABLE indexed_chunks")
    conn.execute(
        """
        CREATE TABLE indexed_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_root TEXT NOT NULL,
            file TEXT NOT NULL,
            symbol TEXT,
            kind TEXT NOT NULL,
            line_start INTEGER,
            line_end INTEGER,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        )
        """
    )



def _row_to_hit(row: tuple) -> ToolHit:
    import json

    file, symbol, kind, line_start, line_end, metadata_json = row
    return ToolHit(
        file=file,
        symbol=symbol,
        kind=kind,
        line_start=line_start,
        line_end=line_end,
        content="",
        metadata=json.loads(metadata_json),
        score=None,
    )


def _usage_rank(hit: ToolHit, symbol: str) -> tuple[int, str]:
    metadata = hit.metadata
    calls = metadata.get("calls", [])
    imports = metadata.get("imports", [])
    fields = metadata.get("fields", [])
    exports = metadata.get("exports", [])

    if symbol in calls:
        return (0, hit.file)
    if symbol in imports:
        return (1, hit.file)
    if symbol in fields:
        return (2, hit.file)
    if symbol in exports or hit.symbol == symbol:
        return (4, hit.file)
    return (3, hit.file)
