#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path


def _bootstrap_repo_src() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    src_root = repo_root / "src"
    if str(src_root) not in sys.path:
        sys.path.insert(0, str(src_root))


def main() -> None:
    parser = argparse.ArgumentParser(description="Search a local frontend repository for impact evidence.")
    parser.add_argument("--root-path", required=True, help="Repository root path")
    parser.add_argument("--keyword", required=True, help="Keyword to search")
    parser.add_argument("--repo-path", default=None, help="Optional subdirectory under the repository root")
    parser.add_argument(
        "--file-types",
        nargs="+",
        default=[".ts", ".tsx", ".js", ".jsx", ".vue", ".json"],
        help="Allowed file extensions",
    )
    args = parser.parse_args()

    _bootstrap_repo_src()

    from impact_agent.services.frontend_search import search_local_candidates

    result = search_local_candidates(
        root_path=args.root_path,
        keyword=args.keyword,
        file_types=args.file_types,
        repo_path=args.repo_path,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
