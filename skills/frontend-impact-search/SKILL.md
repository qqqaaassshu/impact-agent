---
name: frontend-impact-search
description: Deterministic frontend repository search workflow for Vue and React impact analysis. Use when Codex needs to scan a local frontend codebase for field rename evidence, collect normalized candidate matches, or drive the code retrieval step before confirmed/excluded/uncertain classification.
---

# Frontend Impact Search

## Overview

Use this skill to run the deterministic local search step for `field_rename` analysis in a Vue or React repository.

Prefer the bundled script over ad hoc shell search so the output shape stays stable across runs.

## Workflow

1. Validate that the request includes `root_path`, `keyword`, and expected `file_types`.
2. Prefer `scripts/local_search.py` for repository scanning.
3. Search the old field name first, then the new field name, then a small set of explicit variants only when needed.
4. Limit the scan to supported file types and the requested `repo_path` when available.
5. Return normalized JSON candidates with file path, relative path, line number, code snippet, and file kind.

## Command

Run the bundled script:

```bash
python skills/frontend-impact-search/scripts/local_search.py --root-path <project-root> --keyword <keyword> --repo-path <repo-path> --file-types .ts .tsx .js .jsx .vue .json
```

## Output Contract

The search result should contain:

- `keyword`
- `search_root`
- `scanned_files`
- `results`

Each result item should contain:

- `file_path`
- `relative_path`
- `line_no`
- `line`
- `keyword`
- `file_kind`

## References

- Read `references/search-patterns.md` when the request is about frontend field rename evidence patterns.
