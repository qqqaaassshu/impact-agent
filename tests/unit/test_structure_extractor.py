from impact_agent.indexer.structure_extractor import extract_structure


def test_extract_structure_from_typescript() -> None:
    content = """
import formatPrice, { TAX_RATE, getOrderDetail as fetchOrder } from './order'

export interface Order {
  price: number
}

export function renderOrder(order: Order) {
  const detail = fetchOrder(order.id)
  return formatPrice(detail.price)
}

export { renderOrder as showOrder }
"""

    structure = extract_structure(content)

    assert structure.imports == ["TAX_RATE", "fetchOrder", "formatPrice"]
    assert structure.exports == ["Order", "renderOrder", "showOrder"]
    assert "fetchOrder" in structure.calls
    assert "formatPrice" in structure.calls
    assert "price" in structure.fields
