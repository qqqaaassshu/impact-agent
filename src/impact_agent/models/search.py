from pydantic import BaseModel


class SearchTextRequest(BaseModel):
    query: str
    limit: int | None = None


class SearchSymbolRequest(BaseModel):
    symbol: str
    symbol_type: str | None = None
    limit: int | None = None


class SearchFileRequest(BaseModel):
    file_path: str
    limit: int | None = None
