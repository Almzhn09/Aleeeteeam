export const marketNumber = new Intl.NumberFormat('ru-KZ', { maximumFractionDigits: 2 })

export function formatPrice(value: number | null, currency: string | null) {
  return value === null ? 'Неизвестна' : [marketNumber.format(value), currency].filter(Boolean).join(' ')
}
