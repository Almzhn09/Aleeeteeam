import { useState } from 'react'
import { EmptyState, FormField } from '@/components/WorkspaceUI'
import type { MarketStats } from '@/lib/marketlens'
import { formatPrice, marketNumber } from './format'

const categories: Record<string, string> = { electronics: 'Электроника' }

export function MarketDistribution({ groups }: { groups: MarketStats[] }) {
  const [selected, setSelected] = useState('')
  const groupKey = (group: MarketStats) => JSON.stringify([group.comparableGroup, group.currency])
  const group = groups.find(item => groupKey(item) === selected) ?? groups[0]
  if (!group) return <EmptyState title="Статистика пока недоступна">
    <p>Распределение появится после расчёта по сопоставимым объявлениям.</p>
  </EmptyState>

  const largestBin = Math.max(1, ...group.histogram.map(bin => bin.count))
  const metrics = [
    ['Средняя цена', group.meanPrice],
    ['Медиана', group.medianPrice],
    ['Минимум', group.minPrice],
    ['Максимум', group.maxPrice],
  ] as const

  return <section className="panel content-pad space-y-5" aria-labelledby="market-prices">
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 id="market-prices" className="text-lg font-semibold">Цены объявлений</h2>
        <p className="text-sm text-muted-foreground">Предложений в выборке: {marketNumber.format(group.sampleSize)}</p>
      </div>
      <FormField label="Сопоставимая группа">
        <select value={groupKey(group)} onChange={event => setSelected(event.target.value)}>
          {groups.map(item => <option value={groupKey(item)} key={groupKey(item)}>
            {categories[item.category] ?? item.category} · {item.comparableGroup} · {item.currency}
          </option>)}
        </select>
      </FormField>
    </div>
    <dl className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {metrics.map(([label, amount]) => <div key={label} className="rounded-lg border border-border p-3">
        <dt className="text-sm text-muted-foreground">{label}</dt>
        <dd className="text-lg font-semibold tabular-nums">{formatPrice(amount, group.currency)}</dd>
      </div>)}
    </dl>
    <figure aria-labelledby="price-distribution">
      <figcaption id="price-distribution" className="font-semibold">Распределение цен</figcaption>
      {group.histogram.length ? <ol className="mt-3 space-y-3">
        {group.histogram.map((bin, index) => <li key={index} className="space-y-1">
          <div className="flex flex-wrap justify-between gap-x-4 text-sm">
            <span>{formatPrice(bin.min, group.currency)} – {formatPrice(bin.max, group.currency)}</span>
            <span className="tabular-nums">{marketNumber.format(bin.count)} объявл.</span>
          </div>
          <div aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${bin.count / largestBin * 100}%` }} />
          </div>
        </li>)}
      </ol> : <p className="mt-2 text-sm text-muted-foreground">Ценовые интервалы пока недоступны.</p>}
    </figure>
  </section>
}
