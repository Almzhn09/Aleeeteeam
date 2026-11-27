export const marketNumber = new Intl.NumberFormat('ru-KZ', { maximumFractionDigits: 2 })
export const marketTime = new Intl.DateTimeFormat('ru-KZ', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Almaty',
})

export function formatPrice(value: number | null, currency: string | null) {
  return value === null ? 'Неизвестна' : [marketNumber.format(value), currency].filter(Boolean).join(' ')
}
