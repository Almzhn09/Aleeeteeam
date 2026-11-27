import { useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  DetailLink, EmptyState, ErrorState, FormField, LoadingState, PageHeading, SourceLink,
} from '@/components/WorkspaceUI'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { useApiQuery } from '@/lib/useApiQuery'
import { errorMessage } from '@/lib/labels'
import { ListingHistory } from './dashboard/ListingHistory'
import { MarketDistribution } from './dashboard/MarketDistribution'
import { PriceComparison } from './dashboard/PriceComparison'
import { formatPrice, marketNumber } from './dashboard/format'
import type {
  CatalogView, Explanation, ListingItem, ListingPage, RiskLevel, StatsPage,
} from '@/lib/marketlens'

const apiPath = '/api/v1/market'
const viewLabels = { all: 'Каталог', deals: 'Выгодные предложения', risk: 'Подозрительные объявления' }
const riskLabels: Record<RiskLevel, string> = {
  unknown: 'Не оценён', low: 'Низкий', medium: 'Средний', high: 'Высокий',
}
function ListingCard({ item, detailed = false }: { item: ListingItem; detailed?: boolean }) {
  const { listing, analysis } = item
  const image = listing.images.find(url => url.startsWith('https://'))
  return <article className="panel overflow-hidden">
    {image && <img src={image} alt="" className="aspect-video w-full bg-muted object-contain"
      loading="lazy" referrerPolicy="no-referrer" />}
    <div className="content-pad space-y-3">
      <p className="text-sm text-muted-foreground">{[listing.source.toUpperCase(), listing.city, listing.category].filter(Boolean).join(' · ')}</p>
      <h2 className="text-lg font-semibold break-words">{listing.title}</h2>
      <p className="text-2xl font-semibold">{formatPrice(listing.price, listing.currency)}</p>
      {listing.description && <p className={detailed ? 'whitespace-pre-wrap break-words' : 'line-clamp-2 break-words'}>{listing.description}</p>}
      {detailed ? <PriceComparison item={item} /> : <dl className="grid grid-cols-2 gap-3 text-sm">
        <div><dt className="text-muted-foreground">Оценка рынка</dt><dd>{formatPrice(analysis?.marketPrice ?? null, listing.currency)}</dd></div>
        {analysis?.priceDeviationPercent != null && <div><dt className="text-muted-foreground">Отклонение цены</dt>
          <dd>{analysis.priceDeviationPercent > 0 ? '+' : ''}{marketNumber.format(analysis.priceDeviationPercent)}%</dd>
        </div>}
      </dl>}
      <p className="text-sm">Риск: <strong>{riskLabels[analysis?.riskLevel ?? 'unknown']}</strong></p>
      {analysis?.isDeal && <p className="text-sm font-semibold text-primary">
        {analysis.savingsAmount != null && analysis.savingsAmount > 0
          ? `Выгода по оценке: ${formatPrice(analysis.savingsAmount, listing.currency)}`
          : 'Выгодное предложение по оценке'}
      </p>}
      {detailed && analysis && analysis.riskReasons.length > 0 && <div>
        <h3 className="font-semibold">Признаки для проверки</h3>
        <ul className="list-disc pl-5">{analysis.riskReasons.map((reason, index) => <li key={`${reason.code}-${index}`}>{reason.description}</li>)}</ul>
      </div>}
      <div className="flex flex-wrap gap-4">
        {!detailed && <DetailLink to={`/listings/${encodeURIComponent(listing.id)}`}>Подробнее</DetailLink>}
        <SourceLink url={listing.url} />
      </div>
    </div>
  </article>
}

export function MarketCatalog({ view }: { view: CatalogView }) {
  const [filters, setFilters] = useState('')
  const [offset, setOffset] = useState(0)
  const params = new URLSearchParams(filters)
  params.set('view', view)
  params.set('offset', String(offset))
  const query = useApiQuery<ListingPage>(`${apiPath}/listings?${params}`)

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const values = new URLSearchParams()
    for (const [key, value] of new FormData(event.currentTarget)) {
      if (typeof value === 'string' && value.trim()) values.set(key, value.trim())
    }
    setFilters(values.toString())
    setOffset(0)
  }

  return <>
    <PageHeading eyebrow="Рынок Казахстана" title={viewLabels[view]}
      description={view === 'risk' ? 'Признаки риска помогают выбрать, что проверить у продавца.' : 'Запрашиваемые цены и результаты сравнения предложений.'} />
    <form onSubmit={submit} className="panel content-pad mb-5 grid grid-cols-1 items-end gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <FormField label="Поиск"><input name="q" maxLength={120} type="search" /></FormField>
      <FormField label="Категория"><input name="category" maxLength={120} /></FormField>
      <FormField label="Город"><input name="city" maxLength={120} /></FormField>
      <FormField label="Источник"><select name="source">
        <option value="">Все источники</option><option value="olx">OLX</option>
        <option value="krisha">Krisha</option><option value="kolesa">Kolesa</option>
      </select></FormField>
      <FormField label="От, ₸"><input name="minPrice" type="number" min={0} step="any" /></FormField>
      <FormField label="До, ₸"><input name="maxPrice" type="number" min={0} step="any" /></FormField>
      <FormField label="Сортировка"><select name="sort">
        <option value="">По умолчанию</option><option value="newest">Свежие наблюдения</option>
        <option value="price_asc">Сначала дешевле, ₸</option><option value="price_desc">Сначала дороже, ₸</option>
      </select></FormField>
      <Button type="submit">Найти</Button>
    </form>
    {query.loading && <LoadingState />}
    {query.error && <ErrorState message={query.error} retry={query.refresh} />}
    {query.data?.scanLimited && <p className="mb-3 text-sm" role="status">Поиск охватывает первые {query.data.scannedCount} объявлений.</p>}
    {query.data?.items.length === 0 && <EmptyState title="Объявления не найдены" />}
    {!!query.data?.items.length && <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {query.data.items.map(item => <ListingCard key={item.listing.id} item={item} />)}
    </div>}
    {query.data && (offset > 0 || query.data.nextOffset !== null) && <div className="my-4 flex gap-3">
      <Button disabled={offset === 0} variant="outline" onClick={() => setOffset(Math.max(0, offset - 24))}>Назад</Button>
      <Button disabled={query.data.nextOffset === null} onClick={() => setOffset(query.data?.nextOffset ?? offset)}>Дальше</Button>
    </div>}
  </>
}

export function MarketListing() {
  const { id } = useParams()
  const path = id ? `${apiPath}/listings/${encodeURIComponent(id)}` : null
  const query = useApiQuery<ListingItem>(path)
  const { api } = useAuth()
  const [explanation, setExplanation] = useState<Explanation | null>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function requestExplanation() {
    setPending(true)
    setError(null)
    try {
      setExplanation(await api<Explanation>(`${path}/explanation`, { method: 'POST' }))
    } catch (failure) {
      setError(errorMessage(failure))
    } finally {
      setPending(false)
    }
  }

  return <>
    <PageHeading eyebrow="Каталог" title="Объявление" description="Цена, рыночное сравнение и исходная публикация."
      action={<Link to="/listings">К каталогу</Link>} />
    {query.loading && <LoadingState />}
    {query.error && <ErrorState message={query.error} retry={query.refresh} />}
    {query.data && <div className="grid gap-4 lg:grid-cols-2">
      <ListingCard item={query.data} detailed />
      <div className="grid content-start gap-4">
        {path && <ListingHistory path={path} />}
        <section className="panel content-pad space-y-3">
          <h2 className="text-lg font-semibold">Пояснение оценки</h2>
          <Button disabled={pending} onClick={() => { void requestExplanation() }}>
            {pending ? 'Загружаем…' : 'Получить пояснение'}
          </Button>
          {error && <p role="alert">{error}</p>}
          {explanation && <div className="space-y-2" aria-live="polite">
            <p className="text-sm text-muted-foreground">{explanation.provider === 'gemini' ? 'Пояснение Gemini' : 'Локальное пояснение'}</p>
            <p>{explanation.summary}</p>
            {[
              ['Наблюдения', explanation.insights],
              ['Рекомендации', explanation.recommendations],
              ['Ограничения', explanation.limitations],
            ].map(([heading, lines]) => Array.isArray(lines) && lines.length > 0 && <div key={String(heading)}>
              <h3 className="font-semibold">{heading}</h3>
              <ul className="list-disc pl-5">{lines.map((line, index) => <li key={index}>{line}</li>)}</ul>
            </div>)}
          </div>}
        </section>
      </div>
    </div>}
  </>
}

export function MarketOverview() {
  const query = useApiQuery<StatsPage>(`${apiPath}/stats`)
  return <>
    <PageHeading eyebrow="Рынок Казахстана" title="Обзор рынка"
      description="Сопоставимые предложения по собранным объявлениям."
      action={<DetailLink to="/listings">Открыть каталог</DetailLink>} />
    {query.loading && <LoadingState />}
    {query.error && <ErrorState message={query.error} retry={query.refresh} />}
    {query.data?.truncated && <p role="status">Показаны первые {query.data.items.length} групп.</p>}
    {query.data && <MarketDistribution groups={query.data.items} />}
  </>
}
