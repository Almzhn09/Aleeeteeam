import type { ListingItem } from '@/lib/marketlens'
import { formatPrice, marketNumber } from './format'

export function PriceComparison({ item }: { item: ListingItem }) {
  const { analysis, listing } = item
  const { currency, price } = listing

  return <section aria-label="Сравнение цены" className="rounded-lg border border-border p-3">
    <h3 className="font-semibold">Сравнение с рынком</h3>
    <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
      <div><dt className="text-muted-foreground">Цена объявления</dt><dd>{formatPrice(price, currency)}</dd></div>
      <div><dt className="text-muted-foreground">Оценка рынка</dt><dd>{formatPrice(analysis?.marketPrice ?? null, currency)}</dd></div>
      {analysis && <div><dt className="text-muted-foreground">Сопоставимых объявлений</dt><dd>{analysis.sampleSize}</dd></div>}
      {analysis?.confidence != null && <div>
        <dt className="text-muted-foreground">Доверие к оценке</dt>
        <dd>{marketNumber.format(analysis.confidence * 100)}%</dd>
      </div>}
      {analysis?.priceDeviationPercent != null && <div><dt className="text-muted-foreground">Отклонение цены</dt>
        <dd>{analysis.priceDeviationPercent > 0 ? '+' : ''}{marketNumber.format(analysis.priceDeviationPercent)}%</dd>
      </div>}
      {analysis?.savingsAmount != null && analysis.savingsAmount > 0 && <div>
        <dt className="text-muted-foreground">Потенциальная экономия</dt><dd>{formatPrice(analysis.savingsAmount, currency)}</dd>
      </div>}
    </dl>
    {analysis?.marketPrice == null && <p className="mt-2 text-sm text-muted-foreground">Рыночная оценка пока недоступна.</p>}
  </section>
}
