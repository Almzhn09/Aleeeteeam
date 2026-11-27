import { fireEvent, render, screen, waitFor } from '@testing-library/react'
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
    fireEvent.click(screen.getByRole('button', { name: 'Найти' }))
    await waitFor(() => {
      const url = new URL(String(api.mock.lastCall?.[0]), 'https://test.invalid')
      expect(url.searchParams.get('city')).toBe('Алматы')
    })
    fireEvent.click(await screen.findByRole('link', { name: 'Подробнее' }))
    expect(await screen.findByRole('link', { name: 'Открыть источник ↗' }))
      .toHaveAttribute('href', row.listing.url)
    fireEvent.click(screen.getByRole('button', { name: 'Получить пояснение' }))
    expect(await screen.findByText('Локальное пояснение')).toBeInTheDocument()
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
  const api = vi.fn().mockImplementation(async (path: string) => path.includes('/listings?')
    ? { items: [analyzed], nextOffset: null, scanLimited: false, scannedCount: 1 }
    : analyzed)
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
