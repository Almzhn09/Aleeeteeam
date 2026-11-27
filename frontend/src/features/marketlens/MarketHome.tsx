import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowRight, BarChart3, Coins, Layers, Percent, Search, ShieldAlert, ShieldCheck, Smartphone, Tag,
} from 'lucide-react'
import { ErrorState, LoadingState } from '@/components/WorkspaceUI'
import { useApiQuery } from '@/lib/useApiQuery'
import type { ListingItem, ListingPage, MarketStats, StatsPage } from '@/lib/marketlens'
import { formatPrice, marketCategories, marketNumber } from './dashboard/format'

const apiPath = '/api/v1/market'
const compact = new Intl.NumberFormat('ru-KZ', { notation: 'compact', maximumFractionDigits: 1 })
const words: Record<string, string> = {
  iphone: 'iPhone', promax: 'Pro Max', pro: 'Pro', max: 'Max', plus: 'Plus', mini: 'mini',
  macbook: 'MacBook', air: 'Air', galaxy: 'Galaxy', ultra: 'Ultra', lite: 'Lite',
}

/** "electronics/phones:apple-iphone-13:128gb:any:KZT" -> "iPhone 13 · 128 ГБ". */
export function groupTitle(group: MarketStats) {
  const [scope, product, ...rest] = group.comparableGroup.split(':')
  if (product === 'all') return marketCategories[scope.split('/')[1]] ?? group.category
  const parts = product.split('-')
  const name = (parts.length > 1 ? parts.slice(1) : parts)
    .map(word => words[word] ?? word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
  const variant = rest.length === 3 ? rest[0].replace(/(\d+)gb$/, '$1 ГБ').replace(/(\d+)tb$/, '$1 ТБ') : null
  return variant ? `${name} · ${variant}` : name
}

const isModel = (group: MarketStats) => group.comparableGroup.split(':')[1].includes('-')

function count(page: ListingPage | null) {
  if (!page) return '—'
  return page.nextOffset === null ? marketNumber.format(page.items.length) : `${page.items.length}+`
}

export function MarketHome() {
  const navigate = useNavigate()
  const all = useApiQuery<ListingPage>(`${apiPath}/listings?view=all&limit=1`)
  const deals = useApiQuery<ListingPage>(`${apiPath}/listings?view=deals&limit=100`)
  const risk = useApiQuery<ListingPage>(`${apiPath}/listings?view=risk&limit=100`)
  const stats = useApiQuery<StatsPage>(`${apiPath}/stats`)

  const groups = [...(stats.data?.items ?? [])].sort((a, b) => b.sampleSize - a.sampleSize)
  const models = groups.filter(isModel)
  const featured = models[0] ?? groups[0]

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const q = String(new FormData(event.currentTarget).get('q') ?? '').trim()
    navigate(q ? `/listings?${new URLSearchParams({ q })}` : '/listings')
  }

  return <div className="ml-home">
    <section className="ml-hero">
      <div className="ml-hero-text">
        <p className="ml-kicker"><BarChart3 size={18} aria-hidden="true" /> Аналитика объявлений Казахстана</p>
        <h1>Умный поиск <em>выгодных</em> предложений</h1>
        <p className="ml-lead">Анализируем объявления OLX: сравниваем цену с похожими предложениями,
          находим выгодные и показываем признаки, которые стоит проверить.</p>
        <form className="ml-search" role="search" onSubmit={search}>
          <Search size={20} aria-hidden="true" />
          <input name="q" type="search" maxLength={120} aria-label="Поиск объявлений"
            placeholder="Найти товар, например: iPhone 13" />
          <button type="submit">Найти</button>
        </form>
      </div>
      <HeroArt />
      <ul className="ml-features">
        <li><span><BarChart3 size={20} /></span><div><strong>Реальные цены</strong>и рыночная оценка</div></li>
        <li><span><ShieldCheck size={20} /></span><div><strong>Проверка</strong>признаков риска</div></li>
        <li><span><Percent size={20} /></span><div><strong>Выгодные предложения</strong>ниже медианы модели</div></li>
      </ul>
    </section>

    <section className="ml-kpis" aria-label="Ключевые показатели">
      <Kpi icon={<Layers size={22} />} tone="green" value={all.data ? marketNumber.format(all.data.scannedCount) + (all.data.scanLimited ? '+' : '') : '—'}
        label="Объявлений в базе" note="OLX" />
      <Kpi icon={<Tag size={22} />} tone="green" value={count(deals.data)} label="Выгодных предложений"
        note={<Link to="/deals">Смотреть</Link>} />
      <Kpi icon={<ShieldAlert size={22} />} tone="red" value={count(risk.data)} label="Требуют проверки"
        note={<Link to="/risk">Смотреть</Link>} />
      <Kpi icon={<Coins size={22} />} tone="amber"
        value={featured ? formatPrice(featured.medianPrice, featured.currency) : '—'}
        label={featured ? `Медиана (${groupTitle(featured)})` : 'Медианная цена'}
        note={featured ? `${featured.sampleSize} объявл.` : undefined} />
    </section>

    <div className="ml-columns">
      <PriceChart groups={models.length ? models : groups} loading={stats.loading} error={stats.error}
        retry={stats.refresh} />
      <section className="ml-card" aria-labelledby="top-deals">
        <div className="ml-card-head">
          <h2 id="top-deals">Топ выгодных предложений</h2>
          <Link to="/deals" className="ml-more">Смотреть все <ArrowRight size={15} /></Link>
        </div>
        {deals.loading && <LoadingState />}
        {deals.error && <ErrorState message={deals.error} retry={deals.refresh} />}
        {deals.data?.items.length === 0 && <p className="ml-muted">Пока нет предложений заметно ниже
          медианы своей модели. Они появятся, когда в выборке будет больше объявлений.</p>}
        <ul className="ml-deals">
          {deals.data?.items.slice(0, 4).map(item => <DealRow key={item.listing.id} item={item} />)}
        </ul>
      </section>
    </div>
  </div>
}

function Kpi({ icon, tone, value, label, note }: {
  icon: ReactNode; tone: 'green' | 'red' | 'amber'; value: string; label: string; note?: ReactNode
}) {
  return <div className="ml-kpi">
    <span className={`ml-kpi-icon ${tone}`} aria-hidden="true">{icon}</span>
    <div><strong>{value}</strong><span>{label}</span>{note && <small>{note}</small>}</div>
  </div>
}

function DealRow({ item }: { item: ListingItem }) {
  const { listing, analysis } = item
  const image = listing.images.find(url => url.startsWith('https://'))
  const deviation = analysis?.priceDeviationPercent
  return <li>
    <Link to={`/listings/${encodeURIComponent(listing.id)}`} state={{ catalog: '/deals' }} className="ml-deal">
      <span className="ml-thumb">{image
        ? <img src={image} alt="" loading="lazy" referrerPolicy="no-referrer" />
        : <Smartphone size={28} aria-hidden="true" />}</span>
      <span className="ml-deal-body">
        <strong>{listing.title}</strong>
        <span className="ml-chips">
          <span>{listing.source.toUpperCase()}</span>{listing.city && <span>{listing.city}</span>}
        </span>
      </span>
      <span className="ml-deal-price">
        <strong>{formatPrice(listing.price, listing.currency)}</strong>
        {deviation != null && <span className="ml-badge">{marketNumber.format(Math.round(deviation))}% от рынка</span>}
      </span>
      <span className="ml-arrow" aria-hidden="true"><ArrowRight size={18} /></span>
    </Link>
  </li>
}

function PriceChart({ groups, loading, error, retry }: {
  groups: MarketStats[]; loading: boolean; error: string | null; retry: () => void
}) {
  const [selected, setSelected] = useState(0)
  const group = groups[selected] ?? groups[0]
  const largest = Math.max(1, ...(group?.histogram.map(bin => bin.count) ?? []))
  return <section className="ml-card" aria-labelledby="price-chart">
    <div className="ml-card-head">
      <div>
        <h2 id="price-chart">Распределение цен</h2>
        {group && <p className="ml-muted">{groupTitle(group)} · {group.sampleSize} объявл.</p>}
      </div>
      {groups.length > 1 && <div className="ml-pills" role="group" aria-label="Группа сравнения">
        {groups.slice(0, 4).map((item, index) => <button key={item.comparableGroup + item.currency}
          type="button" aria-pressed={index === selected} onClick={() => setSelected(index)}>
          {groupTitle(item)}
        </button>)}
      </div>}
    </div>
    {loading && <LoadingState />}
    {error && <ErrorState message={error} retry={retry} />}
    {!loading && !error && !group && <p className="ml-muted">Статистика появится после расчёта аналитики.</p>}
    {group && <>
      <ol className="ml-bars" aria-label="Количество объявлений по ценовым интервалам">
        {group.histogram.map((bin, index) => <li key={index}>
          <span className="ml-bar-count">{bin.count}</span>
          <span className="ml-bar" style={{ height: `${Math.max(4, bin.count / largest * 100)}%` }} />
          <span className="ml-bar-label">{compact.format(bin.min)}</span>
          <span className="ml-visually-hidden">{formatPrice(bin.min, group.currency)} – {formatPrice(bin.max, group.currency)}: {bin.count} объявл.</span>
        </li>)}
      </ol>
      <dl className="ml-metrics">
        {([['Средняя', group.meanPrice], ['Медиана', group.medianPrice], ['Минимум', group.minPrice], ['Максимум', group.maxPrice]] as const)
          .map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{formatPrice(value, group.currency)}</dd></div>)}
      </dl>
    </>}
  </section>
}

function HeroArt() {
  return <div className="ml-hero-art" aria-hidden="true">
    <svg viewBox="0 0 320 300" role="presentation">
      <defs>
        <linearGradient id="ml-screen" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#e9f6ee" /><stop offset="1" stopColor="#b9e2c8" />
        </linearGradient>
      </defs>
      <circle cx="170" cy="150" r="130" fill="#e3f2e8" />
      <rect x="95" y="25" width="150" height="260" rx="28" fill="#1f2a24" />
      <rect x="103" y="33" width="134" height="244" rx="22" fill="url(#ml-screen)" />
      <rect x="148" y="42" width="44" height="8" rx="4" fill="#1f2a24" />
      {[60, 95, 75, 130, 110, 150].map((height, index) =>
        <rect key={index} x={118 + index * 18} y={230 - height} width="11" height={height} rx="4"
          fill={index === 5 ? '#166534' : '#4ade80'} opacity={index === 5 ? 1 : 0.55} />)}
      <rect x="40" y="70" width="96" height="40" rx="12" fill="#fff" stroke="#d7e8dd" />
      <circle cx="60" cy="90" r="9" fill="#dcfce7" /><path d="M55 90l4 4 7-8" stroke="#166534" strokeWidth="2.5" fill="none" />
      <rect x="76" y="83" width="48" height="6" rx="3" fill="#cfe3d6" /><rect x="76" y="94" width="32" height="6" rx="3" fill="#e5efe8" />
      <rect x="205" y="190" width="96" height="40" rx="12" fill="#fff" stroke="#d7e8dd" />
      <circle cx="225" cy="210" r="9" fill="#dcfce7" /><path d="M221 213l8-8M221 205h8v8" stroke="#166534" strokeWidth="2.5" fill="none" />
      <rect x="241" y="203" width="48" height="6" rx="3" fill="#cfe3d6" /><rect x="241" y="214" width="32" height="6" rx="3" fill="#e5efe8" />
    </svg>
  </div>
}
