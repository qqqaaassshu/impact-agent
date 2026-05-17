# Frontend Search Patterns

Use these patterns when collecting candidates for `field_rename`.

## High-priority evidence

- Vue template field bindings
- React JSX expressions
- Object property access
- Type and interface fields
- API mapping fields
- Mock and fixture keys
- Schema and form/table config keys

## Scan order

1. Search `old_name`
2. Search `new_name`
3. Search only a few explicit variants when the request provides enough context

## Exclusion hints

These matches should not be upgraded to confirmed evidence without code context:

- Plain copy text
- Comments
- Unrelated substrings
- Dynamic field names without enough local evidence
