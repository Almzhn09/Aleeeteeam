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
    city: 'Алматы', images: [], attributes: {}, condition: null,
    publishedAt: null, scrapedAt: '2026-11-27T09:00:00Z', sellerId: null,
  },
  analysis: null,
}

describe('MarketLens workspace', () => {
  it('opens a filtered catalog, follows an item and requests its local explanation', async () => {
    const api = vi.fn().mockImplementation(async (path: string) => {
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
    const history = await screen.findByRole('region', { name: 'История цен' })
    expect(await within(history).findByText(/85\s000 KZT/)).toBeVisible()
    expect(within(history).getByText('Неизвестна')).toBeVisible()
    expect(within(history).getByText('Показаны последние 2 снимков.')).toBeVisible()
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
