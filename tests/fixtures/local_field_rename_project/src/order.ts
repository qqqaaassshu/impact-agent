export const order = {
  amount: 100,
  totalAmount: 100,
};

export function renderAmountRow(record: { amount: number }) {
  return `<span>${record.amount}</span>`;
}
