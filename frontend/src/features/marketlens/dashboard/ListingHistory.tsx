import { ErrorState, LoadingState } from '@/components/WorkspaceUI'
import type { PriceHistory } from '@/lib/marketlens'
import { useApiQuery } from '@/lib/useApiQuery'
import { formatPrice, marketTime } from './format'

export function ListingHistory({ path }: { path: string }) {
  const { data, error, loading, refresh } = useApiQuery<PriceHistory>(`${path}/history`)

  return <section className="panel content-pad space-y-3" aria-labelledby="listing-history">
    <h2 id="listing-history" className="text-lg font-semibold">История цен</h2>
    <p className="text-sm text-muted-foreground">Цены объявления на момент сбора, время Казахстана.</p>
    {loading && <LoadingState />}
    {error && <ErrorState message={error} retry={refresh} />}
    {data && (data.items.length === 0 ? <p>Снимков пока нет.</p> : <>
      <ol className="divide-y divide-border">
        {data.items.map(item => <li key={item.scrapedAt} className="flex flex-wrap justify-between gap-x-3 py-2">
          <time dateTime={item.scrapedAt}>{marketTime.format(new Date(item.scrapedAt))}</time>
          <span className="font-medium tabular-nums">{formatPrice(item.price, item.currency)}</span>
        </li>)}
      </ol>
      {data.truncated && <p className="text-sm text-muted-foreground">Показаны последние {data.items.length} снимков.</p>}
    </>)}
  </section>
}
