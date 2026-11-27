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

it('shows live counts, top deals and the price trend on the home page', async () => {
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
    if (path.includes('view=all')) return {
      items: [row], nextOffset: 1, scanLimited: false, total: 30, scannedCount: 806,
      subcategoryCounts: { tablets: 20, laptops: 10 },
      subcategoryPhotos: { tablets: row.listing.images[0] },
      latestScrapedAt: row.listing.scrapedAt,
    }
    if (path.includes('view=deals')) return { items: [deal], nextOffset: null, scanLimited: false, scannedCount: 30 }
    if (path.includes('view=risk')) return { items: [], nextOffset: null, scanLimited: false, scannedCount: 30 }
    if (path.includes('/radar?')) return {
      groups: [{ key: 'electronics/phones:apple-iphone-13:any:KZT', sampleSize: 7 }],
      sample: {
        key: 'electronics/phones:apple-iphone-13:any:KZT', prices: [272000, 325000], medianPrice: 325000,
        trend: [{ day: '2026-11-26', medianPrice: 330000, count: 6 }, { day: '2026-11-27', medianPrice: 325000, count: 7 }],
      },
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
  const tabletTile = screen.getByRole('link', { name: 'Планшеты · 20 объявлений' })
  const tileUrl = new URL(tabletTile.getAttribute('href') ?? '', 'https://test.invalid')
  expect(tileUrl.searchParams.get('city')).toBe('Усть-Каменогорск')
  expect(tileUrl.searchParams.get('subcategory')).toBe('tablets')
  expect(tabletTile.querySelector('img')).toHaveAttribute('src', row.listing.images[0])
  expect(within(kpis).getByText(/^Сбор:/)).toBeVisible()
  expect(within(kpis).getByText(/−1,5%/)).toHaveTextContent('за 7 дней')
  expect(api.mock.calls.filter(([path]) => String(path).includes('view=all'))).toHaveLength(1)
  expect(await screen.findByRole('link', { name: /iPhone 13 128GB/ })).toHaveAttribute('href', '/listings/olx%3Adeal')
  expect(screen.getByText('−16% от рынка')).toBeVisible()
  expect(screen.getByRole('img', { name: /26\.11: 330\s000 ₸; 27\.11: 325\s000 ₸/ })).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: '30 дней' }))
  expect(screen.getByRole('button', { name: '30 дней' })).toHaveAttribute('aria-pressed', 'true')
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

it('uses observed prices to update the radar budget and available offers', async () => {
  const key = 'electronics/phones:apple-iphone-13:128gb:any:KZT'
  const api = vi.fn().mockResolvedValue({
    groups: [{ key, sampleSize: 2 }, { key: 'electronics/monitors:27in:280hz:any:KZT', sampleSize: 1 }],
    sample: {
      key, prices: [85000, 100000], medianPrice: null,
      histogram: [{ min: 85000, max: 100000, count: 2 }],
      offers: [row],
    },
    scanLimited: false,
  })
  render(<AuthContext.Provider value={{
    status: 'authenticated', profile: null, error: null, logout: vi.fn(),
    signIn: vi.fn(), api,
  }}><MemoryRouter initialEntries={['/radar']}><App marketLens /></MemoryRouter></AuthContext.Provider>)

  expect(await screen.findByText('В бюджете 1 из 2')).toBeVisible()
  expect(screen.getByRole('option', { name: '27″ · 280 Гц · Мониторы (1)' })).toBeInTheDocument()
  expect(screen.getByText('Пока мало сопоставимых объявлений для рыночного ориентира.')).toBeVisible()
  expect(screen.getByRole('link', { name: row.listing.title })).toBeVisible()
  fireEvent.change(screen.getByLabelText('Бюджет, ₸'), { target: { value: '70000' } })
  expect(screen.getByText('В бюджете 0 из 2')).toBeVisible()
  expect(screen.queryByRole('link', { name: row.listing.title })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Бюджет, ₸'), { target: { value: '100000' } })
  expect(screen.getByText('В бюджете 2 из 2')).toBeVisible()
})
