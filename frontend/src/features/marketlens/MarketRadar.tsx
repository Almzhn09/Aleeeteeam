import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState, PageHeading } from '@/components/WorkspaceUI'
import type { ListingItem, MarketStats } from '@/lib/marketlens'
import { useApiQuery } from '@/lib/useApiQuery'
import { CompareButton } from './MarketComparison'
import { formatPrice, marketCategories } from './dashboard/format'

interface RadarSample {
  key: string
  prices: number[]
  medianPrice: number | null
  histogram: MarketStats['histogram']
  offers: ListingItem[]
}

interface RadarPage {
  groups: { key: string; sampleSize: number }[]
  sample: RadarSample | null
  scanLimited: boolean
}

function modelLabel(key: string) {
  const [scope, model, ...details] = key.split(':')
  const section = marketCategories[scope.split('/')[1]] ?? scope
  const variant = details.length === 3
    ? details[0].replace(/(\d+)gb$/, '$1 ГБ').replace(/(\d+)tb$/, '$1 ТБ').replace(/^(\d+)hz$/, '$1 Гц')
    : ''
  const title = model.replace(/^(\d+)in$/, '$1″').replace(/^apple-iphone-/, 'iPhone-').replace(/-/g, ' ')
  return [title, variant, section].filter(Boolean).join(' · ')
}

export function MarketRadar() {
  const [params, setParams] = useSearchParams()
  const city = params.get('city') ?? 'Усть-Каменогорск'
  const group = params.get('group') ?? ''
  const query = useApiQuery<RadarPage>(`/api/v1/market/radar?${new URLSearchParams({ city, group })}`)
  const data = query.data

  return <>
    <PageHeading eyebrow="Объявления OLX" title="Радар цен"
      description="Выберите модель и проверьте, какие предложения укладываются в ваш бюджет." />
    <div className="panel content-pad ml-radar-controls grid gap-4 sm:grid-cols-2">
      <label className="grid gap-2 text-sm font-semibold">Город
        <select value={city} onChange={event => setParams({ city: event.target.value })}
          className="w-full rounded-lg border bg-background p-2">
          <option value="Усть-Каменогорск">Усть-Каменогорск</option>
          <option value="">Весь Казахстан</option>
        </select>
      </label>
      <label className="grid gap-2 text-sm font-semibold">Модель
        <select value={data?.sample?.key ?? group} disabled={!data?.groups.length}
          onChange={event => setParams({ city, group: event.target.value })}
          className="w-full rounded-lg border bg-background p-2">
          {!data?.sample && <option value={group}>Выбрать модель</option>}
          {data?.groups.map(item => <option value={item.key} key={item.key}>
            {modelLabel(item.key)} ({item.sampleSize})
          </option>)}
        </select>
      </label>
    </div>
    {query.loading && <LoadingState />}
    {query.error && <ErrorState message={query.error} retry={query.refresh} />}
    {data?.scanLimited && <p role="status" className="my-4 text-sm">Радар построен по доступной части каталога.</p>}
    {data && !data.sample && <EmptyState title="Нет цен для выбранной модели">
      Выберите другую модель или откройте каталог.
    </EmptyState>}
    {data?.sample && <BudgetAnalysis key={`${city}:${data.sample.key}`} sample={data.sample} />}
  </>
}

function BudgetAnalysis({ sample }: { sample: RadarSample }) {
  const { prices, histogram, offers } = sample
  const lowest = prices[0]
  const highest = prices[prices.length - 1]
  const [value, setValue] = useState(String(sample.medianPrice ?? lowest))
  const number = Number(value)
  const budget = value !== '' && Number.isFinite(number) && number >= 0 ? number : null
  const inBudget = budget === null ? 0 : prices.filter(price => price <= budget).length
  const visible = offers.filter(item => budget !== null && item.listing.price !== null
    && item.listing.price <= budget).slice(0, 6)
  const maxCount = Math.max(1, ...histogram.map(bin => bin.count))
  const marker = budget === null ? null
    : Math.max(0, Math.min(100, (budget - lowest) / (highest - lowest || 1) * 100))

  return <div className="my-5 grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
    <section className="ml-card ml-radar space-y-5" aria-label="Распределение цен">
      <div>
        <h2>Распределение цен</h2>
        <p className="text-sm text-muted-foreground">{prices.length} предложений с ценой в тенге</p>
      </div>
      <div className="ml-radar-chart">
        <ol className="ml-bars" aria-label="Количество объявлений по диапазонам">
          {histogram.map((bin, index) => {
            const caption = `${formatPrice(bin.min, 'KZT')} – ${formatPrice(bin.max, 'KZT')}: ${bin.count}`
            return <li key={index} title={caption}
              className={budget !== null && bin.max <= budget ? 'fits' : undefined}>
              <span className="ml-bar-count">{bin.count}</span>
              <span className="sr-only">{caption}</span>
              <span aria-hidden="true" className="ml-bar"
                style={{ height: `${Math.max(3, bin.count / maxCount * 100)}%` }} />
            </li>
          })}
        </ol>
        {marker !== null && <span aria-hidden="true"
          className="ml-budget-marker" style={{ left: `${marker}%` }} />}
      </div>
      <p className="flex flex-wrap justify-between gap-2 text-sm text-muted-foreground">
        <span>{formatPrice(lowest, 'KZT')}</span><span>{formatPrice(highest, 'KZT')}</span>
      </p>
      <label className="grid gap-2 text-sm font-semibold">Бюджет, ₸
        <input type="number" min="0" step="any" value={value} onChange={event => setValue(event.target.value)}
          className="rounded-lg border bg-background p-2" />
      </label>
      <input type="range" min="0" max={Math.ceil(highest)} step="1"
        value={Math.min(Math.ceil(highest), Math.max(0, budget ?? 0))}
        aria-label="Изменить бюджет" onChange={event => setValue(event.target.value)}
        className="w-full accent-primary" />
      <p aria-live="polite">{budget === null ? 'Введите бюджет' : `В бюджете ${inBudget} из ${prices.length}`}</p>
      <p className="text-sm text-muted-foreground">{sample.medianPrice === null
        ? 'Пока мало сопоставимых объявлений для рыночного ориентира.'
        : `Медиана цен объявлений: ${formatPrice(sample.medianPrice, 'KZT')}`}</p>
    </section>

    <section className="ml-card ml-radar-offers space-y-4" aria-label="Предложения в бюджете">
      <h2>Предложения в бюджете</h2>
      {!visible.length && <p className="text-sm text-muted-foreground">Нет предложений в пределах бюджета.</p>}
      <ul className="divide-y">
        {visible.map(({ listing }) => <li key={listing.id} className="grid gap-2 py-3 sm:grid-cols-[1fr_auto]">
          <div className="min-w-0">
            <Link className="font-semibold text-primary break-words" to={`/listings/${encodeURIComponent(listing.id)}`}>
              {listing.title}
            </Link>
            <p className="text-sm">{formatPrice(listing.price, listing.currency)}</p>
          </div>
          <CompareButton id={listing.id} />
        </li>)}
      </ul>
    </section>
  </div>
}
