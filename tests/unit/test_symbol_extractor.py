from impact_agent.indexer.symbol_extractor import extract_symbols


def test_extract_symbols_from_typescript() -> None:
    content = """
import { formatPrice as fp } from './format'

export interface Order {
  price: number
}

export function getOrderDetail() {
  return { price: 100 }
}

const totalPrice = 100
"""

    symbols = extract_symbols(content)
    names = {(symbol.name, symbol.kind) for symbol in symbols}

    assert ("fp", "import") in names
    assert ("Order", "interface") in names
    assert ("getOrderDetail", "function") in names
    assert ("totalPrice", "const") in names
