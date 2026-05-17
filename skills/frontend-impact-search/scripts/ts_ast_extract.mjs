import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const configFieldNames = new Set(['dataIndex', 'field', 'fieldName', 'key', 'name', 'prop'])

const ts = loadTypescript()
const input = await readInput()

if (!ts) {
  writeJson({
    available: false,
    engine: 'typescript',
    usages: [],
    bindings: [],
    errors: ['typescript_module_not_found'],
  })
  process.exit(0)
}

const fieldName = String(input.fieldName || '')
const sourceFile = ts.createSourceFile(
  input.filePath || 'unknown.ts',
  String(input.content || ''),
  ts.ScriptTarget.Latest,
  true,
  scriptKindForPath(String(input.filePath || 'unknown.ts')),
)

const usages = []
const bindings = []
const seenUsages = new Set()
const seenBindings = new Set()

visit(sourceFile)

writeJson({
  available: true,
  engine: 'typescript',
  usages,
  bindings,
  errors: [],
})

function visit(node) {
  if (ts.isPropertyAccessExpression(node) && node.name?.text === fieldName) {
    addUsage(node.name, 'object_property', 'high')
  }

  if (ts.isElementAccessExpression(node) && isStringLiteralText(node.argumentExpression, fieldName)) {
    addUsage(node.argumentExpression, 'bracket_property', 'high')
  }

  if (ts.isPropertyAssignment(node)) {
    if (nameText(node.name) === fieldName) {
      addUsage(node.name, 'object_field', 'high')
    }
    if (configFieldNames.has(nameText(node.name)) && isStringLiteralText(node.initializer, fieldName)) {
      addUsage(node.initializer, 'config_field', 'high')
    }
  }

  if (ts.isShorthandPropertyAssignment(node) && node.name?.text === fieldName) {
    addUsage(node.name, 'object_field', 'high')
  }

  if ((ts.isPropertySignature(node) || ts.isMethodSignature(node)) && nameText(node.name) === fieldName) {
    addUsage(node.name, 'type_field', 'high')
  }

  if (ts.isJsxAttribute(node)) {
    if (node.name?.text === fieldName) {
      addUsage(node.name, 'jsx_attribute', 'medium')
    }
    if (configFieldNames.has(node.name?.text) && jsxInitializerText(node.initializer) === fieldName) {
      addUsage(node.initializer || node.name, 'config_field', 'high')
    }
  }

  if (ts.isBindingElement(node)) {
    const property = node.propertyName ? nameText(node.propertyName) : nameText(node.name)
    if (property === fieldName) {
      const symbol = bindingNameText(node.name)
      addUsage(node, symbol && symbol !== fieldName ? 'destructuring_alias' : 'destructuring_property', 'high')
      if (symbol) {
        addBinding(node.name, symbol, fieldName, symbol !== fieldName ? 'destructuring_alias' : 'destructuring_property')
      }
    }
  }

  if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name)) {
    const symbol = node.name.text
    if (isStringLiteralText(node.initializer, fieldName)) {
      addBinding(node.name, symbol, fieldName, 'string_literal')
    }
    if (node.initializer && isPropertyAccessToField(node.initializer, fieldName)) {
      addBinding(node.name, symbol, fieldName, 'property_access')
    }
    if (node.initializer && isBracketAccessToField(node.initializer, fieldName)) {
      addBinding(node.name, symbol, fieldName, 'bracket_property')
    }
  }

  ts.forEachChild(node, visit)
}

function addUsage(node, usageType, confidence) {
  const lineNo = lineNumber(node)
  const key = `${lineNo}:${usageType}`
  if (seenUsages.has(key)) return
  seenUsages.add(key)
  usages.push({
    line_no: lineNo,
    usage_type: usageType,
    confidence,
    engine: 'typescript',
  })
}

function addBinding(node, symbol, propertyName, bindingType) {
  const lineNo = lineNumber(node)
  const key = `${lineNo}:${symbol}:${bindingType}`
  if (seenBindings.has(key)) return
  seenBindings.add(key)
  bindings.push({
    line_no: lineNo,
    symbol,
    property_name: propertyName,
    binding_type: bindingType,
    confidence: 'medium',
    engine: 'typescript',
  })
}

function lineNumber(node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1
}

function nameText(node) {
  if (!node) return ''
  if (ts.isIdentifier(node) || ts.isStringLiteral(node) || ts.isNumericLiteral(node)) return node.text
  if (ts.isPrivateIdentifier?.(node)) return node.text
  return node.getText(sourceFile).replace(/^['"]|['"]$/g, '')
}

function bindingNameText(node) {
  if (!node) return ''
  if (ts.isIdentifier(node)) return node.text
  return ''
}

function isStringLiteralText(node, expected) {
  return Boolean(node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) && node.text === expected)
}

function jsxInitializerText(initializer) {
  if (!initializer) return ''
  if (ts.isStringLiteral(initializer)) return initializer.text
  if (ts.isJsxExpression(initializer) && isStringLiteralText(initializer.expression, fieldName)) {
    return initializer.expression.text
  }
  return ''
}

function isPropertyAccessToField(node, expected) {
  return ts.isPropertyAccessExpression(node) && node.name?.text === expected
}

function isBracketAccessToField(node, expected) {
  return ts.isElementAccessExpression(node) && isStringLiteralText(node.argumentExpression, expected)
}

function scriptKindForPath(filePath) {
  const suffix = path.extname(filePath).toLowerCase()
  if (suffix === '.tsx') return ts.ScriptKind.TSX
  if (suffix === '.jsx') return ts.ScriptKind.JSX
  if (suffix === '.js') return ts.ScriptKind.JS
  return ts.ScriptKind.TS
}

function loadTypescript() {
  const candidates = [
    path.join(process.cwd(), 'node_modules', 'typescript', 'lib', 'typescript.js'),
    path.join(process.cwd(), 'web', 'node_modules', 'typescript', 'lib', 'typescript.js'),
  ]

  for (const candidate of candidates) {
    if (!fs.existsSync(candidate)) continue
    return require(candidate)
  }

  try {
    return require('typescript')
  } catch {
    return null
  }
}

async function readInput() {
  let raw = ''
  for await (const chunk of process.stdin) {
    raw += chunk
  }
  return raw ? JSON.parse(raw) : {}
}

function writeJson(value) {
  process.stdout.write(JSON.stringify(value))
}
