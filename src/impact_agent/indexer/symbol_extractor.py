import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedSymbol:
    name: str
    kind: str
    line_start: int
    line_end: int
    content: str


SYMBOL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("function", re.compile(r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")),
    ("class", re.compile(r"\b(?:export\s+)?class\s+([A-Za-z_$][\w$]*)")),
    ("const", re.compile(r"\b(?:export\s+)?const\s+([A-Za-z_$][\w$]*)")),
    ("let", re.compile(r"\b(?:export\s+)?let\s+([A-Za-z_$][\w$]*)")),
    ("var", re.compile(r"\b(?:export\s+)?var\s+([A-Za-z_$][\w$]*)")),
    ("type", re.compile(r"\b(?:export\s+)?type\s+([A-Za-z_$][\w$]*)")),
    ("interface", re.compile(r"\b(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)")),
)

IMPORT_PATTERN = re.compile(r"\bimport\s+(?:type\s+)?(?:\{([^}]+)\}|([A-Za-z_$][\w$]*))")


def extract_symbols(content: str, *, context_radius: int = 3) -> list[ExtractedSymbol]:
    lines = content.splitlines()
    symbols: list[ExtractedSymbol] = []

    for line_number, line in enumerate(lines, start=1):
        for kind, pattern in SYMBOL_PATTERNS:
            for match in pattern.finditer(line):
                symbols.append(
                    _symbol_from_match(
                        name=match.group(1),
                        kind=kind,
                        lines=lines,
                        line_number=line_number,
                        context_radius=context_radius,
                    )
                )

        for imported_name in _extract_import_names(line):
            symbols.append(
                _symbol_from_match(
                    name=imported_name,
                    kind="import",
                    lines=lines,
                    line_number=line_number,
                    context_radius=0,
                )
            )

    return _dedupe_symbols(symbols)


def _extract_import_names(line: str) -> list[str]:
    match = IMPORT_PATTERN.search(line)
    if not match:
        return []

    named_imports = match.group(1)
    default_import = match.group(2)
    if default_import:
        return [default_import]
    if not named_imports:
        return []

    names: list[str] = []
    for item in named_imports.split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        names.append(cleaned.split(" as ")[-1].strip())
    return names


def _symbol_from_match(
    *,
    name: str,
    kind: str,
    lines: list[str],
    line_number: int,
    context_radius: int,
) -> ExtractedSymbol:
    start = max(1, line_number - context_radius)
    end = min(len(lines), line_number + context_radius)
    content = "\n".join(lines[start - 1 : end])
    return ExtractedSymbol(
        name=name,
        kind=kind,
        line_start=start,
        line_end=end,
        content=content,
    )


def _dedupe_symbols(symbols: list[ExtractedSymbol]) -> list[ExtractedSymbol]:
    seen: set[tuple[str, str, int]] = set()
    unique: list[ExtractedSymbol] = []
    for symbol in symbols:
        key = (symbol.name, symbol.kind, symbol.line_start)
        if key in seen:
            continue
        seen.add(key)
        unique.append(symbol)
    return unique
