---
name: frontend-impact-search
description: Use this skill when scanning a local Vue or React frontend repository for field rename impact evidence. It defines the workflow for deterministic code search, evidence normalization, and uncertainty handling; it should not be used as an LLM-only whole-repo scanner.
metadata:
  short-description: Search frontend repos for field rename impact evidence
---

# Frontend Impact Search

Use this skill for `field_rename` impact analysis in local Vue / React repositories. The Skill package owns the executable search and AST analysis capabilities; the application calls it through a runtime adapter and consumes structured observations.

## Inputs

Required:

- `repo_root`: absolute project root
- `requirement`: natural language field rename requirement
- `old_name` and `new_name`: preferred when already parsed by the Agent

Optional:

- `repo_path`: relative subdirectory to scan
- `file_extensions`: default `.ts,.tsx,.js,.jsx,.vue,.json`
- `max_results`: cap for raw search results

## Workflow

1. Validate that `repo_root` exists and that `repo_path`, if present, stays inside it.
2. Generate deterministic search clues from `old_name` and `new_name`.
3. Run deterministic local search before any LLM review.
4. Normalize each hit into evidence candidates with file path, line number, matched keyword, and surrounding context.
5. Mark comments as comment hits; do not treat them as confirmed impact.
6. Run AST analysis for recalled JS / TS files when structural evidence is needed.
7. Mark dynamic references and variable propagation as uncertain unless later evidence confirms them.
8. Return candidates and AST observations to the Agent; the Skill does not produce the final risk conclusion.

## Actions

`local_search`

- Input: `repo_root`, `keyword`, `repo_path`, `file_extensions`
- Output: normalized keyword hits with file path, relative path, line number, line text, keyword, and file kind

`local_search_many`

- Input: `repo_root`, `keywords`, `repo_path`, `file_extensions`
- Output: grouped keyword hits for one search round

`ast_analyze`

- Input: `file_path`, `content`, `field_name`
- Output: structured usages and bindings, including object property access, bracket access, type fields, config fields, destructuring, and simple symbol bindings

## Local Script

Use the bundled script when a direct command-line scan is needed:

```powershell
python skills/frontend-impact-search/scripts/local_search.py --repo-root "D:\Wrok\product" --keyword amount --keyword totalAmount
```

The main application invokes this Skill through `FrontendImpactSearchSkill`, then consumes the returned observation in the Agent strategy.

## Boundaries

- The Skill defines the workflow and evidence contract.
- The search engine performs file scanning and context extraction.
- The Agent classifies evidence and builds the final report.
- The LLM may review a small number of uncertain candidates, but must not scan the whole repository or add new hit files.

## References

Read [references/search-patterns.md](references/search-patterns.md) when you need detailed classification hints for Vue, React, comments, dynamic fields, or variable propagation.

Read [references/ast-patterns.md](references/ast-patterns.md) when you need AST-specific usage and binding rules.
