import { useState } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, FormField, LoadingState, PageHeading } from '@/components/WorkspaceUI'
import { useApiQuery } from '@/lib/useApiQuery'
import type { MarketStats, StatsPage } from '@/lib/marketlens'
import { groupTitle } from './MarketHome'
import { formatPrice, marketNumber } from './dashboard/format'

const minimumSample = 5

function isModel(group: MarketStats) {
  return group.currency === 'KZT' && group.comparableGroup.split(':')[1]?.includes('-')
}

export function MarketRadar() {
  const [model, setModel] = useState('')
  const [budget, setBudget] = useState('')
  const query = useApiQuery<StatsPage>('/api/v1/market/stats')
  const groups = query.data?.items.filter(isModel) ?? []
  const group = groups.find(item => item.comparableGroup === model) ?? groups[0]
  const amount = budget !== '' && Number.isFinite(Number(budget)) && Number(budget) >= 0
    ? Number(budget) : null

  return <>
    <PageHeading eyebrow="MarketLens" title="Радар цен"
      description="Сопоставьте бюджет с распределением запрашиваемых цен выбранной модели."
      action={<Link to="/listings">Открыть каталог</Link>} />
    {query.loading && <LoadingState />}
    {query.error && <ErrorState message={query.error} retry={query.refresh} />}
    {query.data?.truncated && <p role="status">В радаре доступны группы из последнего расчёта.</p>}
    {query.data && !group && <EmptyState title="Недостаточно сопоставимых объявлений">
      <p>Радар появится, когда в каталоге наберётся выборка по конкретной модели.</p>
    </EmptyState>}
    {group && <section className="ml-card space-y-5" aria-labelledby="radar-results">
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Модель"><select value={group.comparableGroup} onChange={event => setModel(event.target.value)}>
          {groups.map(item => <option key={item.comparableGroup} value={item.comparableGroup}>{groupTitle(item)}</option>)}
        </select></FormField>
        <FormField label="Бюджет, ₸"><input value={budget} type="number" min={0} step="any"
          onChange={event => setBudget(event.target.value)} inputMode="decimal" /></FormField>
      </div>
      <h2 id="radar-results" className="text-lg font-semibold">{groupTitle(group)}</h2>
      <dl className="ml-metrics">
        <div><dt>Рыночная оценка (медиана)</dt><dd>{formatPrice(group.medianPrice, group.currency)}</dd></div>
        <div><dt>Выборка</dt><dd>{marketNumber.format(group.sampleSize)} объявл.</dd></div>
      </dl>
      {group.sampleSize < minimumSample || group.medianPrice == null || !group.histogram.length
        ? <p role="status">Недостаточно данных для сравнения бюджета.</p>
        : <BudgetDistribution group={group} budget={amount} />}
    </section>}
  </>
}

function BudgetDistribution({ group, budget }: { group: MarketStats; budget: number | null }) {
  const highestCount = Math.max(1, ...group.histogram.map(bin => bin.count))
  const low = group.minPrice
  const high = group.maxPrice
  const position = budget != null && low != null && high != null
    ? high > low ? Math.max(0, Math.min(100, 100 * (budget - low) / (high - low))) : 50
    : null
  return <figure aria-labelledby="radar-distribution" className="space-y-3">
    <figcaption id="radar-distribution" className="font-semibold">Распределение цен</figcaption>
    <div className="relative">
      <ol className="ml-bars" aria-label="Количество объявлений по ценовым интервалам">
        {group.histogram.map((bin, index) => <li key={index}>
          <span className="ml-bar-count">{bin.count}</span>
          <span className="ml-bar" style={{ height: `${Math.max(4, bin.count / highestCount * 100)}%` }} />
          <span className="ml-bar-label">{marketNumber.format(bin.min)}</span>
          <span className="ml-visually-hidden">{formatPrice(bin.min, group.currency)} – {formatPrice(bin.max, group.currency)}: {bin.count} объявл.</span>
        </li>)}
      </ol>
      {position != null && <span aria-hidden="true"
        className="pointer-events-none absolute inset-y-0 border-l-2 border-amber-500 motion-safe:transition-[left]"
        style={{ left: `${position}%` }} />}
    </div>
    {budget != null && <p role="status">
      Бюджет {formatPrice(budget, group.currency)} {low != null && budget < low
        ? 'ниже минимальной цены в выборке.'
        : high != null && budget > high ? 'выше максимальной цены в выборке.' : 'в пределах цен выборки.'}
    </p>}
  </figure>
}
