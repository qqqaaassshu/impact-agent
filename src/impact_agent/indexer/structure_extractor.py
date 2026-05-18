import re
from dataclasses import dataclass, field


IDENTIFIER = r"[A-Za-z_$][\w$]*"

IMPORT_LINE_PATTERN = re.compile(r"\bimport\s+(?:type\s+)?(.+?)\s+from\s+['\"]")
EXPORT_DECL_PATTERN = re.compile(
    rf"\bexport\s+(?:async\s+)?(?:function|class|const|let|var|type|interface)\s+({IDENTIFIER})"
)
EXPORT_NAMED_PATTERN = re.compile(r"\bexport\s+\{([^}]+)\}")
CALL_PATTERN = re.compile(rf"\b({IDENTIFIER})\s*\(")
PROPERTY_PATTERN = re.compile(rf"(?:\.({IDENTIFIER})|['\"]({IDENTIFIER})['\"]\s*:)")

IGNORED_CALLS = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "function",
    "return",
}


@dataclass(frozen=True)
class CodeStructure:
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    fields: list[str] = field(default_factory=list)


def extract_structure(content: str) -> CodeStructure:
    return CodeStructure(
        imports=_dedupe(_extract_imports(content)),
        exports=_dedupe(_extract_exports(content)),
        calls=_dedupe(_extract_calls(content)),
        fields=_dedupe(_extract_fields(content)),
    )


def _extract_imports(content: str) -> list[str]:
    imports: list[str] = []
    for match in IMPORT_LINE_PATTERN.finditer(content):
        clause = match.group(1).strip()
        named_match = re.search(r"\{([^}]+)\}", clause)
        if named_match:
            imports.extend(_split_named_items(named_match.group(1)))
            clause = clause[: named_match.start()].rstrip(" ,")
        if re.fullmatch(IDENTIFIER, clause):
            imports.append(clause)
    return imports


def _extract_exports(content: str) -> list[str]:
    exports: list[str] = []
    for match in EXPORT_DECL_PATTERN.finditer(content):
        exports.append(match.group(1))
    for match in EXPORT_NAMED_PATTERN.finditer(content):
        exports.extend(_split_named_items(match.group(1)))
    return exports


def _extract_calls(content: str) -> list[str]:
    calls: list[str] = []
    declared = set(_extract_exports(content))
    declared.update(match.group(1) for _, pattern in _declaration_patterns() for match in pattern.finditer(content))
    for match in CALL_PATTERN.finditer(content):
        name = match.group(1)
        if name not in IGNORED_CALLS and name not in declared:
            calls.append(name)
    return calls


def _extract_fields(content: str) -> list[str]:
    fields: list[str] = []
    for match in PROPERTY_PATTERN.finditer(content):
        field = match.group(1) or match.group(2)
        if field:
            fields.append(field)
    return fields


def _split_named_items(raw_items: str) -> list[str]:
    names: list[str] = []
    for item in raw_items.split(","):
        cleaned = item.strip()
        if not cleaned:
            continue
        names.append(cleaned.split(" as ")[-1].strip())
    return names


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _declaration_patterns() -> tuple[tuple[str, re.Pattern[str]], ...]:
    return (
        ("function", re.compile(rf"\b(?:export\s+)?(?:async\s+)?function\s+({IDENTIFIER})")),
        ("class", re.compile(rf"\b(?:export\s+)?class\s+({IDENTIFIER})")),
        ("const", re.compile(rf"\b(?:export\s+)?const\s+({IDENTIFIER})")),
        ("let", re.compile(rf"\b(?:export\s+)?let\s+({IDENTIFIER})")),
        ("var", re.compile(rf"\b(?:export\s+)?var\s+({IDENTIFIER})")),
    )
