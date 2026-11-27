import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { App } from '@/app/App'
import { AuthContext } from '@/features/auth/AuthProvider'
import type { ListingItem } from '@/lib/marketlens'

const row: ListingItem = {
  listing: {
    id: 'olx:test', externalId: 'test', source: 'olx', dataset: 'real',
    url: 'https://www.olx.kz/example', title: 'Ноутбук для теста', description: null,
    category: 'electronics', subcategory: null, price: 85000, currency: 'KZT',
    city: 'Алматы', images: ['https://photos.example.test/first.jpg', 'https://photos.example.test/second.jpg'], attributes: {}, condition: null,
    publishedAt: null, scrapedAt: '2026-11-27T09:00:00Z', sellerId: null,
  },
  analysis: null,
}

describe('MarketLens workspace', () => {
  it('opens a filtered catalog, follows an item and requests its local explanation', async () => {
    const api = vi.fn().mockImplementation(async (path: string) => {
      if (path.endsWith('/history?limit=100')) return {
        items: [{ scrapedAt: '2026-11-25T09:00:00Z', price: 80000, currency: 'KZT' }],
        truncated: false,
      }
      if (path.endsWith('/history')) return {
        items: [
          { scrapedAt: '2026-11-27T09:00:00Z', price: 85000, currency: 'KZT' },
          { scrapedAt: '2026-11-26T09:00:00Z', price: null, currency: null },
        ],
        truncated: true,
      }
      if (path.endsWith('/explanation')) return {
        provider: 'local', summary: 'Оценка пока недоступна.',
        insights: [], recommendations: [], limitations: ['Цены объявлений'],
      }
      if (path.includes('/listings?')) return {
        items: [row], nextOffset: null, scanLimited: false, scannedCount: 1,
      }
      return row
    })
    render(<AuthContext.Provider value={{
      status: 'authenticated', profile: null, error: null, logout: vi.fn(),
      signIn: vi.fn(), api,
    }}><MemoryRouter initialEntries={['/listings']}><App marketLens /></MemoryRouter></AuthContext.Provider>)

    await screen.findByRole('heading', { name: row.listing.title })
    expect(screen.queryByRole('link', { name: 'Реестр ЖК' })).not.toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Город'), { target: { value: 'Алматы' } })
    const submit = screen.getByRole('button', { name: 'Найти' })
    submit.focus()
    fireEvent.click(submit)
    await waitFor(() => {
      const url = new URL(String(api.mock.lastCall?.[0]), 'https://test.invalid')
      expect(url.searchParams.get('city')).toBe('Алматы')
    })
    expect(submit).toHaveFocus()
    fireEvent.click(await screen.findByRole('link', { name: 'Подробнее' }))
    expect(await screen.findByRole('link', { name: 'Открыть источник ↗' }))
      .toHaveAttribute('href', row.listing.url)
    const photo = screen.getByRole('img', { name: /Фото объявления/ })
    expect(photo).toHaveAttribute('src', row.listing.images[0])
    fireEvent.click(screen.getByRole('button', { name: 'Показать фото 2' }))
    expect(photo).toHaveAttribute('src', row.listing.images[1])
    fireEvent.error(photo)
    expect(photo).toHaveAttribute('src', row.listing.images[0])
    fireEvent.error(photo)
    expect(screen.getByText('Фото недоступно')).toBeVisible()
    const history = await screen.findByRole('region', { name: 'История цен' })
    expect(await within(history).findByText(/85\s000 ₸/)).toBeVisible()
    expect(within(history).getByText('Неизвестна')).toBeVisible()
    expect(within(history).getByText('Показаны последние 2 снимков.')).toBeVisible()
    fireEvent.click(within(history).getByRole('button', { name: 'Показать больше снимков' }))
    expect(await within(history).findByText(/80\s000 ₸/)).toBeVisible()
    fireEvent.click(screen.getByRole('button', { name: 'Получить пояснение' }))
    expect(await screen.findByText('Локальное пояснение')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'К каталогу' })).toHaveAttribute('href', '/listings?city=%D0%90%D0%BB%D0%BC%D0%B0%D1%82%D1%8B')
    expect(api).toHaveBeenCalledWith('/api/v1/market/listings/olx%3Atest/explanation', { method: 'POST' })
  })
})

it('shows the server comparison and reasons on a deal without asking Gemini', async () => {
  const analyzed: ListingItem = {
    ...row,
    analysis: {
      listingId: row.listing.id, listingScrapedAt: row.listing.scrapedAt,
      computedAt: '2026-11-27T10:00:00Z', algorithmVersion: 'test',
      comparableGroup: 'phones', marketPrice: 100000, priceDeviationPercent: -15,
      savingsAmount: 15000, dealScore: 70, riskScore: 50, riskLevel: 'medium',
      riskReasons: [{ code: 'gap', description: 'Цена заметно ниже медианы.' }],
      confidence: 0.7, sampleSize: 12, isDeal: true,
    },
  }
  const api = vi.fn().mockImplementation(async (path: string) => {
    if (path.endsWith('/history')) return { items: [], truncated: false }
    if (path.includes('/listings?')) return { items: [analyzed], nextOffset: null, scanLimited: false, scannedCount: 1 }
    return analyzed
  })
  render(<AuthContext.Provider value={{
    status: 'authenticated', profile: null, error: null, logout: vi.fn(),
    signIn: vi.fn(), api,
  }}><MemoryRouter initialEntries={['/deals']}><App marketLens /></MemoryRouter></AuthContext.Provider>)

  expect(await screen.findByText(/Выгода по оценке/)).toBeVisible()
  expect(api).toHaveBeenCalledWith(expect.stringContaining('view=deals'), expect.any(Object))
  fireEvent.click(screen.getByRole('link', { name: 'Подробнее' }))
  expect(await screen.findByRole('region', { name: 'Сравнение цены' })).toHaveTextContent('-15%')
  expect(screen.getByText('Цена заметно ниже медианы.')).toBeVisible()
  expect(api.mock.calls.every(([path]) => !String(path).endsWith('/explanation'))).toBe(true)
})

it('restores filters from a shared URL and keeps them when paging and returning', async () => {
  const api = vi.fn().mockImplementation(async (path: string) => {
    if (path.endsWith('/history')) return { items: [], truncated: false }
    if (!path.includes('/listings?')) return row
    const offset = new URL(path, 'https://test.invalid').searchParams.get('offset')
    return { items: [row], nextOffset: offset === '24' ? 48 : null, scanLimited: false, scannedCount: 52 }
  })
  render(<AuthContext.Provider value={{
    status: 'authenticated', profile: null, error: null, logout: vi.fn(),
    signIn: vi.fn(), api,
  }}><MemoryRouter initialEntries={['/risk?city=Astana&sort=price_desc&offset=24']}>
    <App marketLens />
  </MemoryRouter></AuthContext.Provider>)

  expect(await screen.findByLabelText('Город')).toHaveValue('Astana')
  expect(screen.getByLabelText('Сортировка')).toHaveValue('price_desc')
  fireEvent.click(await screen.findByRole('button', { name: 'Дальше' }))
  await waitFor(() => expect(api).toHaveBeenLastCalledWith(
    '/api/v1/market/listings?city=Astana&sort=price_desc&view=risk&offset=48', expect.any(Object),
  ))
  fireEvent.click(await screen.findByRole('link', { name: 'Подробнее' }))
  const back = await screen.findByRole('link', { name: 'К каталогу' })
  expect(back).toHaveAttribute('href', '/risk?city=Astana&sort=price_desc&offset=48')
  fireEvent.click(back)
  expect(await screen.findByLabelText('Город')).toHaveValue('Astana')
  fireEvent.click(screen.getByRole('button', { name: 'Сбросить' }))
  await waitFor(() => expect(api).toHaveBeenLastCalledWith(
    '/api/v1/market/listings?view=risk&offset=0', expect.any(Object),
  ))
})

it('shows live counts, top deals and price distribution on the home page', async () => {
  const deal: ListingItem = {
    listing: { ...row.listing, id: 'olx:deal', title: 'iPhone 13 128GB', subcategory: 'phones', price: 272000 },
    analysis: {
      listingId: 'olx:deal', listingScrapedAt: row.listing.scrapedAt, computedAt: row.listing.scrapedAt,
      algorithmVersion: 'v3', comparableGroup: 'electronics/phones:apple-iphone-13:any:KZT',
      marketPrice: 325000, priceDeviationPercent: -16.3, savingsAmount: 53000, dealScore: 72,
      riskScore: 0, riskLevel: 'low', riskReasons: [], confidence: 0.5, sampleSize: 6, isDeal: true,
    },
  }
  const api = vi.fn().mockImplementation(async (path: string) => {
    if (path.includes('view=all')) return { items: [row], nextOffset: 1, scanLimited: false, scannedCount: 30 }
    if (path.includes('view=deals')) return { items: [deal], nextOffset: null, scanLimited: false, scannedCount: 30 }
    if (path.includes('view=risk')) return { items: [], nextOffset: null, scanLimited: false, scannedCount: 30 }
    if (path.endsWith('/stats')) return {
      truncated: false,
      items: [{
        dataset: 'real', computedAt: row.listing.scrapedAt, comparableGroup: 'electronics/phones:apple-iphone-13:any:KZT',
        category: 'electronics', currency: 'KZT', sampleSize: 7, meanPrice: 320000, medianPrice: 325000,
        minPrice: 272000, maxPrice: 350000, histogram: [{ min: 272000, max: 311000, count: 2 }, { min: 311000, max: 350000, count: 5 }],
      }],
    }
    return { items: [row], nextOffset: null, scanLimited: false, scannedCount: 1 }
  })
  render(<AuthContext.Provider value={{
    status: 'authenticated', profile: null, error: null, logout: vi.fn(), signIn: vi.fn(), api,
  }}><MemoryRouter initialEntries={['/']}><App marketLens /></MemoryRouter></AuthContext.Provider>)

  expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent('Умный поиск выгодных')
  const kpis = screen.getByRole('region', { name: 'Ключевые показатели' })
  expect(await within(kpis).findByText('30')).toBeVisible()
  expect(within(kpis).getByText('Медиана (iPhone 13)')).toBeVisible()
  expect(await screen.findByRole('link', { name: /iPhone 13 128GB/ })).toHaveAttribute('href', '/listings/olx%3Adeal')
  expect(screen.getByText('-16% от рынка')).toBeVisible()
  expect(screen.getByText('iPhone 13 · 7 объявл.')).toBeVisible()
  fireEvent.change(screen.getByRole('searchbox', { name: 'Поиск объявлений' }), { target: { value: 'iphone 13' } })
  fireEvent.click(screen.getByRole('button', { name: 'Найти' }))
  await waitFor(() => expect(api).toHaveBeenLastCalledWith(
    '/api/v1/market/listings?q=iphone+13&view=all&offset=0', expect.any(Object),
  ))
})

it('compares up to three listings, keeps selection across routes and allows removal', async () => {
  const items = [1, 2, 3, 4].map(index => ({
    ...row,
    listing: { ...row.listing, id: `olx:test-${index}`, title: `Объявление ${index}` },
  }))
  const api = vi.fn().mockImplementation(async (path: string) => {
    if (path.includes('/listings?')) return {
      items, nextOffset: null, scanLimited: false, scannedCount: items.length,
    }
    const id = decodeURIComponent(path.split('/').at(-1) ?? '')
    return items.find(item => item.listing.id === id)
  })
  render(<AuthContext.Provider value={{
    status: 'authenticated', profile: null, error: null, logout: vi.fn(),
    signIn: vi.fn(), api,
  }}><MemoryRouter initialEntries={['/listings']}><App marketLens /></MemoryRouter></AuthContext.Provider>)

  const buttons = await screen.findAllByRole('button', { name: 'Сравнить' })
  buttons.slice(0, 3).forEach(button => fireEvent.click(button))
  expect(buttons[3]).toBeDisabled()
  fireEvent.click(screen.getByRole('link', { name: 'Сравнение (3)' }))
  expect(await screen.findByRole('link', { name: 'Объявление 1' })).toBeVisible()
  expect(await screen.findByRole('link', { name: 'Объявление 3' })).toBeVisible()
  expect(screen.queryByRole('link', { name: 'Объявление 4' })).not.toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: 'Убрать из сравнения' })[0])
  expect(screen.queryByRole('link', { name: 'Объявление 1' })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'Сравнение (2)' })).toBeVisible()
})

it('shows model prices on the radar and positions the chosen budget', async () => {
  const group = {
    dataset: 'real', computedAt: '2026-11-27T10:00:00Z', category: 'electronics',
    comparableGroup: 'electronics/phones:apple-iphone-13:any:KZT', currency: 'KZT',
    sampleSize: 12, meanPrice: 140000, medianPrice: 135000, minPrice: 100000, maxPrice: 200000,
    histogram: [{ min: 100000, max: 150000, count: 8 }, { min: 150000, max: 200000, count: 4 }],
  }
  const api = vi.fn().mockResolvedValue({ items: [group], truncated: false })
  render(<AuthContext.Provider value={{
    status: 'authenticated', profile: null, error: null, logout: vi.fn(), signIn: vi.fn(), api,
  }}><MemoryRouter initialEntries={['/radar']}><App marketLens /></MemoryRouter></AuthContext.Provider>)
  expect(await screen.findByRole('combobox', { name: 'Модель' })).toHaveValue(group.comparableGroup)
  expect(screen.getByText(/135\s000 ₸/)).toBeVisible()
  expect(screen.getByText('12 объявл.')).toBeVisible()
  fireEvent.change(screen.getByLabelText('Бюджет, ₸'), { target: { value: '90000' } })
  expect(screen.getByRole('status')).toHaveTextContent('ниже минимальной цены')
  expect(screen.getByRole('figure', { name: 'Распределение цен' })).toBeVisible()
})

it('does not substitute category averages when the radar has no model sample', async () => {
  const api = vi.fn().mockResolvedValue({
    items: [{ comparableGroup: 'electronics/phones:all:any:KZT', currency: 'KZT' }],
    truncated: false,
  })
  render(<AuthContext.Provider value={{
    status: 'authenticated', profile: null, error: null, logout: vi.fn(), signIn: vi.fn(), api,
  }}><MemoryRouter initialEntries={['/radar']}><App marketLens /></MemoryRouter></AuthContext.Provider>)
  expect(await screen.findByText('Недостаточно сопоставимых объявлений')).toBeVisible()
  expect(screen.queryByLabelText('Бюджет, ₸')).not.toBeInTheDocument()
})
