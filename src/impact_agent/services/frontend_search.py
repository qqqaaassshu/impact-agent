import os
import json
import shutil
import subprocess
from pathlib import Path


IGNORED_DIR_NAMES = {
    ".git",
    ".idea",
    ".next",
    ".nuxt",
    ".turbo",
    ".yarn",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "tmp",
    "temp",
}

RG_SEPARATOR = "|#|"


def search_local_candidates(
    *,
    root_path: str,
    keyword: str,
    file_types: list[str],
    repo_path: str | None = None,
) -> dict:
    repository_root = Path(root_path).expanduser().resolve()
    search_root = resolve_search_root(repository_root, repo_path)
    normalized_file_types = normalize_file_types(file_types)

    rg_result = search_with_rg(
        repository_root=repository_root,
        search_root=search_root,
        keyword=keyword,
        file_types=normalized_file_types,
    )
    if rg_result is not None:
        return rg_result

    return search_with_python(
        repository_root=repository_root,
        search_root=search_root,
        keyword=keyword,
        file_types=normalized_file_types,
    )


def search_local_candidates_many(
    *,
    root_path: str,
    keywords: list[str],
    file_types: list[str],
    repo_path: str | None = None,
) -> dict:
    repository_root = Path(root_path).expanduser().resolve()
    search_root = resolve_search_root(repository_root, repo_path)
    normalized_file_types = normalize_file_types(file_types)
    unique_keywords = [keyword for keyword in dict.fromkeys(keywords) if keyword]

    rg_result = search_many_with_rg(
        repository_root=repository_root,
        search_root=search_root,
        keywords=unique_keywords,
        file_types=normalized_file_types,
    )
    if rg_result is not None:
        return rg_result

    keyword_results = [
        search_with_python(
            repository_root=repository_root,
            search_root=search_root,
            keyword=keyword,
            file_types=normalized_file_types,
        )
        for keyword in unique_keywords
    ]
    return merge_keyword_results(unique_keywords, search_root, "python", keyword_results)


def search_with_rg(
    *,
    repository_root: Path,
    search_root: Path,
    keyword: str,
    file_types: set[str],
) -> dict | None:
    rg_path = shutil.which("rg")
    if not rg_path:
        return None

    command = [
        rg_path,
        "--json",
        "--fixed-strings",
        "--no-ignore-parent",
        "--color",
        "never",
        *build_rg_globs(file_types),
        keyword,
        str(search_root),
    ]

    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None

    if completed.returncode not in {0, 1}:
        return None

    results: list[dict] = []
    matched_files: set[str] = set()
    for raw_line in completed.stdout.splitlines():
        if not raw_line:
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "match":
            continue

        data = event.get("data", {})
        file_path = Path(data.get("path", {}).get("text", "")).resolve()
        if not file_path:
            continue
        matched_files.add(str(file_path))
        line = data.get("lines", {}).get("text", "").rstrip("\r\n")
        results.append(
            {
                "file_path": str(file_path),
                "relative_path": file_path.relative_to(repository_root).as_posix(),
                "line_no": data.get("line_number"),
                "line": line.strip(),
                "keyword": keyword,
                "file_kind": detect_file_kind(file_path),
            }
        )

    return {
        "keyword": keyword,
        "search_root": str(search_root),
        "scanned_files": len(matched_files),
        "search_engine": "rg",
        "results": results,
    }


def search_many_with_rg(
    *,
    repository_root: Path,
    search_root: Path,
    keywords: list[str],
    file_types: set[str],
) -> dict | None:
    rg_path = shutil.which("rg")
    if not rg_path:
        return None
    if not keywords:
        return {
            "keywords": [],
            "search_root": str(search_root),
            "scanned_files": 0,
            "search_engine": "rg",
            "results_by_keyword": {},
        }

    command = [
        rg_path,
        "-n",
        "--fixed-strings",
        "--no-heading",
        "--no-ignore-parent",
        "--field-match-separator",
        RG_SEPARATOR,
        "--color",
        "never",
        *build_rg_globs(file_types),
    ]
    for keyword in keywords:
        command.extend(["-e", keyword])
    command.append(str(search_root))

    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace")
    except OSError:
        return None

    if completed.returncode not in {0, 1}:
        return None

    results_by_keyword: dict[str, list[dict]] = {keyword: [] for keyword in keywords}
    matched_files: set[str] = set()
    for raw_line in completed.stdout.splitlines():
        parsed = parse_rg_line(raw_line)
        if not parsed:
            continue
        file_path_text, line_no, line = parsed
        matched_files.add(file_path_text)
        matched_keywords = matched_keywords_in_line(line, keywords)

        for keyword in matched_keywords:
            results_by_keyword.setdefault(keyword, []).append(
                {
                    "file_path": file_path_text,
                    "relative_path": relative_path_text(file_path_text, repository_root),
                    "line_no": line_no,
                    "line": line.strip(),
                    "keyword": keyword,
                    "file_kind": detect_file_kind(Path(file_path_text)),
                }
            )

    return {
        "keywords": keywords,
        "search_root": str(search_root),
        "scanned_files": len(matched_files),
        "search_engine": "rg",
        "results_by_keyword": results_by_keyword,
    }


def parse_rg_line(raw_line: str) -> tuple[str, int, str] | None:
    parts = raw_line.split(RG_SEPARATOR, 2)
    if len(parts) != 3:
        return None
    file_path_text, line_no_text, line = parts
    if not line_no_text.isdigit():
        return None
    return file_path_text, int(line_no_text), line


def matched_keywords_in_line(line: str, keywords: list[str]) -> list[str]:
    matched: list[str] = []
    for keyword in sorted(keywords, key=len, reverse=True):
        if keyword in line:
            matched.append(keyword)
    return matched


def relative_path_text(file_path_text: str, repository_root: Path) -> str:
    root_text = str(repository_root)
    if file_path_text.startswith(root_text):
        return file_path_text[len(root_text) :].lstrip("\\/").replace("\\", "/")
    return Path(file_path_text).name


def merge_keyword_results(keywords: list[str], search_root: Path, search_engine: str, keyword_results: list[dict]) -> dict:
    results_by_keyword = {result["keyword"]: result["results"] for result in keyword_results}
    scanned_files = sum(int(result.get("scanned_files", 0)) for result in keyword_results)
    return {
        "keywords": keywords,
        "search_root": str(search_root),
        "scanned_files": scanned_files,
        "search_engine": search_engine,
        "results_by_keyword": results_by_keyword,
    }


def build_rg_globs(file_types: set[str]) -> list[str]:
    globs: list[str] = []
    for suffix in sorted(file_types):
        globs.extend(["-g", f"*{suffix}"])
    for ignored in sorted(IGNORED_DIR_NAMES):
        globs.extend(["-g", f"!{ignored}/**"])
    return globs


def search_with_python(
    *,
    repository_root: Path,
    search_root: Path,
    keyword: str,
    file_types: set[str],
) -> dict:
    results: list[dict] = []
    scanned_files = 0

    for file_path in iter_source_files(search_root, file_types):
        scanned_files += 1
        content = read_text_file(file_path)
        if content is None:
            continue

        for line_no, line in enumerate(content.splitlines(), start=1):
            if keyword not in line:
                continue
            results.append(
                {
                    "file_path": str(file_path),
                    "relative_path": file_path.relative_to(repository_root).as_posix(),
                    "line_no": line_no,
                    "line": line.strip(),
                    "keyword": keyword,
                    "file_kind": detect_file_kind(file_path),
                }
            )

    return {
        "keyword": keyword,
        "search_root": str(search_root),
        "scanned_files": scanned_files,
        "search_engine": "python",
        "results": results,
    }


def resolve_search_root(root_path: Path, repo_path: str | None) -> Path:
    if not repo_path:
        return root_path
    candidate = (root_path / repo_path).resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"扫描子路径不存在：{repo_path}。请留空扫描工程根目录，或填写真实存在的前端子目录。")
    return candidate


def normalize_file_types(file_types: list[str]) -> set[str]:
    normalized: set[str] = set()
    for file_type in file_types:
        suffix = file_type if file_type.startswith(".") else f".{file_type}"
        normalized.add(suffix)
    return normalized


def iter_source_files(search_root: Path, file_types: set[str]):
    for current_root, dir_names, file_names in os.walk(search_root):
        dir_names[:] = [name for name in dir_names if name not in IGNORED_DIR_NAMES]
        root_path = Path(current_root)
        for file_name in file_names:
            file_path = root_path / file_name
            if file_path.suffix not in file_types:
                continue
            yield file_path


def read_text_file(file_path: Path) -> str | None:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None


def detect_file_kind(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".vue":
        return "vue_sfc"
    if suffix in {".tsx", ".jsx"}:
        return "jsx_component"
    if suffix == ".json":
        return "json_config"
    return "source_module"
