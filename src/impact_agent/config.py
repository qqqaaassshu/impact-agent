from pathlib import Path

DEFAULT_FILE_TYPES = [".ts", ".tsx", ".js", ".jsx", ".vue", ".json"]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_ROOT = PROJECT_ROOT / "data" / "knowledge"
