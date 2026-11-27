export const marketNumber = new Intl.NumberFormat('ru-KZ', { maximumFractionDigits: 2 })
export const marketTime = new Intl.DateTimeFormat('ru-KZ', {
  dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Almaty',
})

export function formatPrice(value: number | null, currency: string | null) {
  const symbol = currency === 'KZT' ? '₸' : currency
  return value === null ? 'Неизвестна' : [marketNumber.format(value), symbol].filter(Boolean).join(' ')
}

export const marketCategories: Record<string, string> = {
  phones: 'Мобильные телефоны',
  laptops: 'Ноутбуки',
  tablets: 'Планшеты',
  'game-consoles': 'Игровые приставки',
  televisions: 'Телевизоры',
  monitors: 'Мониторы',
  cameras: 'Фотоаппараты',
  audio: 'Акустические системы',
  refrigerators: 'Холодильники',
  'washing-machines': 'Стиральные машины',
  vacuums: 'Пылесосы',
  microwaves: 'Микроволновки',
  'coffee-equipment': 'Кофеварки и кофемолки',
  'soft-furniture': 'Мягкая мебель',
  desks: 'Офисные столы',
  bicycles: 'Велосипеды',
  headphones: 'Наушники',
  'fitness-machines': 'Тренажёры',
  'musical-instruments': 'Музыкальные инструменты',
  'power-tools': 'Электроинструменты',
}
