import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Radar } from 'lucide-react'
import { EmptyState, ErrorState, LoadingState, PageHeading } from '@/components/WorkspaceUI'
import { useApiQuery } from '@/lib/useApiQuery'
import type { MarketStats, StatsPage } from '@/lib/marketlens'
import { formatPrice, marketNumber } from './dashboard/format'
import { groupTitle } from './MarketHome'

/** Same threshold as the analytics engine: fewer peers means no market estimate. */
export const minSample = 4
const isModel = (group: MarketStats) => group.comparableGroup.split(':')[1].includes('-')

/** Page wrapper: reads published stats. Артур can swap the source for a radar API later. */
export function MarketRadarPage() {
  const stats = useApiQuery<StatsPage>('/api/v1/market/stats')
  const groups = (stats.data?.items ?? []).filter(isModel).sort((a, b) => b.sampleSize - a.sampleSize)
  return <>
    <PageHeading eyebrow="MarketLens" title="Радар цен"
      description="Выберите модель и бюджет: покажем, где ваша сумма находится на рынке и сколько предложений в неё попадает." />
    {stats.loading && <LoadingState />}
    {stats.error && <ErrorState message={stats.error} retry={stats.refresh} />}
    {stats.data && !groups.length && <EmptyState title="Пока нет моделей для радара">
      <Link to="/listings">Открыть каталог</Link>
    </EmptyState>}
    {!!groups.length && <MarketRadar groups={groups} />}
  </>
}

export function MarketRadar({ groups }: { groups: MarketStats[] }) {
  const [index, setIndex] = useState(0)
  const group = groups[index] ?? groups[0]
  const low = group.minPrice ?? 0
  const high = Math.max(group.maxPrice ?? low, low + 1)
  const [budgets, setBudgets] = useState<Record<string, number>>({})
  const key = group.comparableGroup + group.currency
  const budget = budgets[key] ?? group.medianPrice ?? Math.round((low + high) / 2)
  const step = Math.max(1, Math.round((high - low) / 100 / 500) * 500)
  const position = Math.min(100, Math.max(0, (budget - low) / (high - low) * 100))
  const largest = Math.max(1, ...group.histogram.map(bin => bin.count))
  const inBudget = group.histogram.reduce((sum, bin) => sum + (bin.max <= budget ? bin.count : 0), 0)
  const enough = group.sampleSize >= minSample && group.medianPrice !== null
  const delta = enough && group.medianPrice ? Math.round((budget - group.medianPrice) / group.medianPrice * 100) : null
  const subcategory = group.comparableGroup.split(':')[0].split('/')[1]
  const catalog = new URLSearchParams({ maxPrice: String(budget), ...(subcategory ? { subcategory } : {}) })

  return <section className="ml-card ml-radar" aria-labelledby="radar-title">
    <div className="ml-card-head">
      <div>
        <h2 id="radar-title"><Radar size={20} aria-hidden="true" /> {groupTitle(group)}</h2>
        <p className="ml-muted">Выборка: {group.sampleSize} объявл.</p>
      </div>
      <label className="ml-select">
        <span className="ml-visually-hidden">Модель</span>
        <select value={index} onChange={event => setIndex(Number(event.target.value))}>
          {groups.map((item, itemIndex) => <option key={item.comparableGroup + item.currency} value={itemIndex}>
            {groupTitle(item)} · {item.sampleSize}
          </option>)}
        </select>
      </label>
    </div>

    {!enough && <p role="status" className="ml-note">Недостаточно сопоставимых объявлений
      (нужно хотя бы {minSample}), поэтому рыночную оценку не показываем.</p>}

    <div className="ml-radar-chart">
      <ol className="ml-bars" aria-label="Количество объявлений по ценовым интервалам" key={key}>
        {group.histogram.map((bin, binIndex) => <li key={binIndex} className={bin.max <= budget ? 'fits' : ''}>
          <span className="ml-bar-count">{bin.count}</span>
          <span className="ml-bar" style={{ height: `${Math.max(4, bin.count / largest * 100)}%` }} />
          <span className="ml-visually-hidden">{formatPrice(bin.min, group.currency)} – {formatPrice(bin.max, group.currency)}: {bin.count} объявл.</span>
        </li>)}
      </ol>
      <span className="ml-budget-marker" style={{ left: `${position}%` }} aria-hidden="true">
        <span>{formatPrice(budget, group.currency)}</span>
      </span>
    </div>

    <label className="ml-budget">
      <span>Бюджет: <strong>{formatPrice(budget, group.currency)}</strong></span>
      <input type="range" min={low} max={high} step={step} value={budget}
        onChange={event => setBudgets(current => ({ ...current, [key]: Number(event.target.value) }))} />
      <span className="ml-budget-scale"><span>{formatPrice(low, group.currency)}</span><span>{formatPrice(high, group.currency)}</span></span>
    </label>

    <dl className="ml-metrics" aria-live="polite">
      <div><dt>Рыночная оценка</dt><dd>{enough ? formatPrice(group.medianPrice, group.currency) : '—'}</dd></div>
      <div><dt>Бюджет к медиане</dt><dd>{delta === null ? '—' : `${delta > 0 ? '+' : ''}${marketNumber.format(delta)}%`}</dd></div>
      <div><dt>Точно в бюджете</dt><dd>{inBudget} из {group.sampleSize}</dd></div>
      <div><dt>Диапазон</dt><dd>{formatPrice(group.minPrice, group.currency)} – {formatPrice(group.maxPrice, group.currency)}</dd></div>
    </dl>
    <Link className="ml-more" to={`/listings?${catalog}`}>Показать объявления до {formatPrice(budget, group.currency)}</Link>
  </section>
}
