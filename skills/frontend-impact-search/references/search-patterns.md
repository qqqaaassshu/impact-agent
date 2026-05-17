# Search Patterns

Use this reference when classifying frontend field rename search results.

## Confirmed affected signals

Treat a hit as likely affected when the old field appears in executable or declarative frontend code:

- Vue template binding, interpolation, prop binding, event payload, table column, or form item
- React JSX expression, prop, state mapping, table column, or form item
- Object property access such as `row.amount` or `record["amount"]`
- TypeScript interface, type alias, schema, DTO, API response type, or request type
- mock, fixture, example response, or local data mapper used by runtime code
- column configuration, form schema, field mapping, export config, or validation rule

## Excluded signals

Treat a hit as excluded when there is enough evidence that it is not runtime impact:

- Line is clearly a comment, including `//`, `/*`, `*`, or `<!--`
- Match only appears in documentation text unrelated to executable config
- Match is a substring of another unrelated identifier
- Match appears in generated build output or dependency files that should not be scanned

When excluding a comment hit, preserve the evidence and set the reason to comment-related exclusion.

## Uncertain signals

Treat a hit as uncertain when static analysis cannot safely decide:

- Dynamic field access such as `row[fieldName]`
- Field name passed through variables or constants
- Field alias created through destructuring or mapper functions
- Generic helper calls such as `getValue(record, field)`
- Configuration arrays where the field meaning depends on runtime composition
- Context is too small or the file cannot be read

Uncertain does not mean safe. It means the Agent cannot honestly confirm or exclude the impact from local evidence alone.

## Variable propagation

For simple local propagation, the scanner may identify patterns such as:

- `const fieldName = "amount"`
- `let field = "amount"`
- `{ prop: "amount" }`
- `fieldName: "amount"`

Then it may look for uses of that variable in a limited same-file window.

Derived hits should be marked as `variable_propagation_reference` and treated conservatively. They can be sent to LLM context review, but the LLM must only judge existing evidence and must not add new files.

## LLM review rules

LLM review is only for selected high-risk uncertain evidence.

Allowed:

- Decide whether a dynamic reference is likely related to the field rename
- Explain why an uncertain evidence remains uncertain
- Reclassify an existing evidence when the local context is enough

Not allowed:

- Scan additional files
- Add new evidence IDs
- Invent impact paths without code evidence
- Override deterministic exclusions such as clear comment hits without reason

## Risk hints

Risk increases when confirmed or uncertain hits appear in:

- API request or response mapping
- Type definitions shared by many components
- table column or form schema configuration
- data export or import mapping
- validation rules
- reusable hooks, composables, or utility mappers

Risk is lower when all hits are comments, isolated mocks, or clearly unrelated substrings.
