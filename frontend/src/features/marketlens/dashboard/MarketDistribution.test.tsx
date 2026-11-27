import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { MarketStats } from '@/lib/marketlens'
import { MarketDistribution } from './MarketDistribution'

const phones: MarketStats = {
  dataset: 'fixture', computedAt: '2026-11-27T09:00:00Z', comparableGroup: 'Смартфоны',
  category: 'electronics', currency: 'KZT', sampleSize: 3,
  meanPrice: 120000, medianPrice: 100000, minPrice: 90000, maxPrice: 170000,
  histogram: [{ min: 90000, max: 110000, count: 2 }, { min: 110000, max: 170000, count: 1 }],
}

describe('MarketDistribution', () => {
  it('uses the selected group currency and server distribution', () => {
    const other = { ...phones, currency: 'USD', sampleSize: 1, medianPrice: null, histogram: [] }
    render(<MarketDistribution groups={[phones, other]} />)
    const chart = screen.getByRole('figure', { name: 'Распределение цен' })
    expect(within(chart).getAllByRole('listitem')).toHaveLength(2)
    expect(within(chart).getByText('2 объявл.')).toBeVisible()
    expect(within(chart).getByText(/90\s000 KZT/)).toBeVisible()

    const selector = screen.getByRole('combobox', { name: 'Сопоставимая группа' })
    fireEvent.change(selector, { target: { value: JSON.stringify(['Смартфоны', 'USD']) } })
    expect(screen.getByText('Предложений в выборке: 1')).toBeVisible()
    expect(screen.getByText('Неизвестна')).toBeVisible()
    expect(within(chart).getByText('Ценовые интервалы пока недоступны.')).toBeVisible()
  })

  it('explains the empty state while the analytics feed is absent', () => {
    render(<MarketDistribution groups={[]} />)
    expect(screen.getByRole('heading', { name: 'Статистика пока недоступна' })).toBeVisible()
    expect(screen.queryByRole('figure')).not.toBeInTheDocument()
  })
})
