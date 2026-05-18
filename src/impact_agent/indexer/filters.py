from pathlib import Path


DEFAULT_CODE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".json"}
DEFAULT_EXCLUDED_PARTS = {
    ".git",
    ".impact-agent",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".uv-cache",
    ".venv",
    "node_modules",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "coverage",
    "__fixtures__",
    "__mocks__",
    "__tests__",
    "fixtures",
    "mock",
    "mocks",
    "test",
    "tests",
}
DEFAULT_EXCLUDED_NAMES = {
    ".env",
    ".env.local",
    "mock.js",
    "mock.json",
    "mock.ts",
    "mockData.js",
    "mockData.json",
    "mockData.ts",
    "package-lock.json",
    "pnpm-lock.yaml",
    "setupTests.js",
    "setupTests.jsx",
    "setupTests.ts",
    "setupTests.tsx",
    "yarn.lock",
}


def should_index_file(
    path: Path,
    *,
    code_extensions: set[str] | None = None,
    excluded_parts: set[str] | None = None,
    excluded_names: set[str] | None = None,
) -> bool:
    extensions = code_extensions or DEFAULT_CODE_EXTENSIONS
    parts = excluded_parts or DEFAULT_EXCLUDED_PARTS
    names = excluded_names or DEFAULT_EXCLUDED_NAMES
    lower_name = path.name.lower()

    if path.name in names:
        return False
    if ".test." in lower_name or ".spec." in lower_name:
        return False
    if lower_name.startswith(("mock.", "mock-", "mock_")):
        return False
    if any(part in parts for part in path.parts):
        return False
    return path.suffix in extensions
