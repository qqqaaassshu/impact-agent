export function getValue(data: Record<string, unknown>, fieldName: string) {
  return data[fieldName];
}

export function readDynamicAmount(data: Record<string, unknown>) {
  const fieldName = "amount";
  return getValue(data, fieldName);
}
