import { createContext, useContext, useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { EmptyState, ErrorState, LoadingState, PageHeading, SourceLink } from '@/components/WorkspaceUI'
import { Button } from '@/components/ui/button'
import type { ListingItem } from '@/lib/marketlens'
import { useApiQuery } from '@/lib/useApiQuery'
import { formatPrice } from './dashboard/format'
import { PriceComparison } from './dashboard/PriceComparison'

const maxSelection = 3
const ComparisonContext = createContext({
  ids: [] as string[],
  toggle: (_id: string) => {},
})

export function ComparisonProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<string[]>([])
  function toggle(id: string) {
    setIds(current => current.includes(id)
      ? current.filter(value => value !== id)
      : current.length < maxSelection ? [...current, id] : current)
  }
  return <ComparisonContext.Provider value={{ ids, toggle }}>{children}</ComparisonContext.Provider>
}

export function useComparison() {
  return useContext(ComparisonContext)
}

export function CompareButton({ id }: { id: string }) {
  const { ids, toggle } = useComparison()
  const selected = ids.includes(id)
  return <Button variant="outline" type="button" aria-pressed={selected}
    disabled={!selected && ids.length >= maxSelection} onClick={() => toggle(id)}>
    {selected ? 'Убрать из сравнения' : 'Сравнить'}
  </Button>
}

export function MarketComparison() {
  const { ids } = useComparison()
  return <>
    <PageHeading eyebrow="MarketLens" title="Сравнение объявлений"
      description="Сопоставьте до трёх карточек по цене, рыночной оценке и признакам риска."
      action={<Link to="/listings">Открыть каталог</Link>} />
    {!ids.length && <EmptyState title="Выбери объявления в каталоге">
      <Link to="/listings">Перейти к объявлениям</Link>
    </EmptyState>}
    {!!ids.length && <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {ids.map(id => <ComparisonCard key={id} id={id} />)}
    </div>}
  </>
}

function ComparisonCard({ id }: { id: string }) {
  const href = '/listings/' + encodeURIComponent(id)
  const query = useApiQuery<ListingItem>('/api/v1/market' + href)
  const item = query.data
  const image = item?.listing.images.find(url => url.startsWith('https://'))
  return <article className="panel content-pad min-w-0 space-y-4">
    {query.loading && <LoadingState />}
    {query.error && <ErrorState message={query.error} retry={query.refresh} />}
    {item && <>
      {image && <img src={image} alt="" loading="lazy" referrerPolicy="no-referrer"
        className="aspect-video w-full rounded-xl bg-muted object-contain" />}
      <p className="ml-chips"><span>{item.listing.source.toUpperCase()}</span>
        {item.listing.city && <span>{item.listing.city}</span>}</p>
      <h2 className="break-words"><Link to={href}>{item.listing.title}</Link></h2>
      <p className="text-xl font-bold">{formatPrice(item.listing.price, item.listing.currency)}</p>
      <PriceComparison item={item} />
      <SourceLink url={item.listing.url} />
      {!!item.analysis?.riskReasons.length && <ul className="list-disc pl-5 text-sm">
        {item.analysis.riskReasons.map((reason, index) =>
          <li key={`${reason.code}-${index}`}>{reason.description}</li>)}
      </ul>}
    </>}
    <CompareButton id={id} />
  </article>
}
