# AST Patterns

Use this reference for the `ast_analyze` action in the `frontend-impact-search` Skill.

## Usage signals

`type_field`

- TypeScript `interface` or `type` field definitions
- Example: `amount?: number`

`object_property`

- Dot property access
- Example: `order.amount`

`bracket_property`

- Literal bracket property access
- Example: `order["amount"]`

`object_field`

- Object literal field definitions
- Example: `{ amount: 0 }`

`config_field`

- Common frontend field configuration keys
- Example: `{ dataIndex: "amount" }`
- Example: `<Column dataIndex="amount" />`

`destructuring_property`

- Destructuring without alias
- Example: `const { amount } = order`

`destructuring_alias`

- Destructuring with alias
- Example: `const { amount: orderAmount } = order`

## Binding signals

Bindings describe symbols that carry the target field value or reference.

Supported binding types:

- `string_literal`: `const fieldName = "amount"`
- `string_config`: `{ prop: "amount" }`
- `property_access`: `const value = order.amount`
- `bracket_property`: `const value = order["amount"]`
- `destructuring_property`: `const { amount } = order`
- `destructuring_alias`: `const { amount: orderAmount } = order`

## Agent handling rules

Confirmed structural usages can be classified as confirmed affected.

Bindings should not be treated as final impact by themselves. They should be used to derive limited same-file relation evidence and usually remain reviewable when the relation is dynamic.

The AST action must only analyze files already selected by deterministic search or a bounded Agent decision. It must not perform full repository traversal.
