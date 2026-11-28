import { useId, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Activity, ArrowRight, BarChart3, Coins, Flame, Layers, Percent, Search, ShieldAlert, ShieldCheck, Smartphone, Tag,
} from 'lucide-react'
import { ErrorState, LoadingState } from '@/components/WorkspaceUI'
import { useApiQuery } from '@/lib/useApiQuery'
import type { ListingItem, ListingPage, MarketStats, StatsPage } from '@/lib/marketlens'
import { formatPrice, marketCategories, marketNumber, marketTime } from './dashboard/format'

const city = 'Усть-Каменогорск'
const cityParam = new URLSearchParams({ city }).toString()
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
  if (page.total != null) return marketNumber.format(page.total)
  return page.nextOffset === null ? marketNumber.format(page.items.length) : `${page.items.length}+`
}

export function MarketHome() {
  const navigate = useNavigate()
  const all = useApiQuery<ListingPage>(`${apiPath}/listings?view=all&limit=1&${cityParam}`)
  const deals = useApiQuery<ListingPage>(`${apiPath}/listings?view=deals&limit=4&${cityParam}`)
  const risk = useApiQuery<ListingPage>(`${apiPath}/listings?view=risk&limit=1&${cityParam}`)
  const stats = useApiQuery<StatsPage>(`${apiPath}/stats`)

  const groups = [...(stats.data?.items ?? [])].sort((a, b) => b.sampleSize - a.sampleSize)
  const models = groups.filter(isModel)
  const featured = models[0] ?? groups[0]
  const categories = Object.entries(all.data?.subcategoryCounts ?? {})
    .sort(([nameA, totalA], [nameB, totalB]) => totalB - totalA || nameA.localeCompare(nameB))
  const latest = all.data?.latestScrapedAt

  function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const q = String(new FormData(event.currentTarget).get('q') ?? '').trim()
    navigate(q ? `/listings?${new URLSearchParams({ q })}` : '/listings')
  }

  return <div className="ml-home">
    <section className="ml-hero">
      <div className="ml-hero-text">
        <p className="ml-kicker"><span aria-hidden="true"><i /><i /><i /></span> Аналитика объявлений Казахстана</p>
        <h1>Умный поиск <em>выгодных и безопасных</em> предложений</h1>
        <p className="ml-lead">Анализируем объявления OLX.<br /> Сравниваем цены, находим выгодные предложения и признаки риска.</p>
        <form className="ml-search" role="search" onSubmit={search}>
          <Search size={20} aria-hidden="true" />
          <input name="q" type="search" maxLength={120} aria-label="Поиск объявлений"
            placeholder="Найти товар, например: iPhone 15…" />
          <button type="submit">Найти</button>
        </form>
      </div>
      <div className="ml-hero-art" aria-hidden="true">
        <img src={`${import.meta.env.BASE_URL}marketlens/hero-phones.webp`} alt="" fetchPriority="high" />
      </div>
      <ul className="ml-features">
        <li><span><BarChart3 size={20} /></span><div><strong>Реальные цены</strong>и рыночная оценка</div></li>
        <li><span><ShieldCheck size={20} /></span><div><strong>Проверка</strong>признаков риска</div></li>
        <li><span><Percent size={20} /></span><div><strong>Выгодные предложения</strong>ниже медианы модели</div></li>
      </ul>
    </section>

    <section className="ml-kpis" aria-label="Ключевые показатели">
      <Kpi icon={<Layers size={22} />} tone="green" value={all.data ? marketNumber.format(all.data.total ?? all.data.scannedCount) + (all.data.scanLimited ? '+' : '') : '—'}
        label="Объявлений в городе" note="OLX" />
      <Kpi icon={<Tag size={22} />} tone="green" value={count(deals.data)} label="Выгодных предложений"
        note={<Link to="/deals">Смотреть</Link>} />
      <Kpi icon={<ShieldAlert size={22} />} tone="red" value={count(risk.data)} label="Требуют проверки"
        note={<Link to="/risk">Смотреть</Link>} />
      <Kpi icon={<Coins size={22} />} tone="amber"
        value={featured ? formatPrice(featured.medianPrice, featured.currency) : '—'}
        label={featured ? `Медиана (${groupTitle(featured)})` : 'Медианная цена'}
        note={featured ? `${featured.sampleSize} объявл. · весь каталог` : undefined} />
    </section>

    <div className="ml-columns">
      <PriceChart groups={models.length ? models : groups} loading={stats.loading} error={stats.error}
        retry={stats.refresh} />
      <section className="ml-card" aria-labelledby="top-deals">
        <div className="ml-card-head">
          <h2 id="top-deals"><Flame size={20} aria-hidden="true" /> Топ выгодных предложений</h2>
          <Link to="/deals" className="ml-more">Смотреть все <ArrowRight size={15} /></Link>
        </div>
        {deals.loading && <LoadingState />}
        {deals.error && <ErrorState message={deals.error} retry={deals.refresh} />}
        {deals.data?.items.length === 0 && <p className="ml-muted">Пока нет предложений заметно ниже
          медианы своей модели. Они появятся, когда в выборке будет больше объявлений.</p>}
        <ul className="ml-deals">
          {deals.data?.items.slice(0, 2).map(item => <DealRow key={item.listing.id} item={item} />)}
        </ul>
      </section>
    </div>
    <div className="ml-city">
      <h2 className="ml-section-title"><Activity size={18} aria-hidden="true" /> Пульс города · {city}</h2>
      {latest && <p className="ml-muted">Последний сбор: {marketTime.format(new Date(latest))}</p>}
    </div>
    {categories.length > 0 && <section className="ml-categories-wrap" aria-labelledby="categories">
      <div className="ml-card-head">
        <h2 id="categories" className="ml-section-title">Категории</h2>
        <Link to="/listings" className="ml-more">Весь каталог <ArrowRight size={15} /></Link>
      </div>
      <ul className="ml-categories">
        {categories.map(([slug, total]) => <CategoryTile key={slug} slug={slug} total={total}
          cover={all.data?.subcategoryPhotos?.[slug]} />)}
      </ul>
    </section>}
  </div>
}

function CategoryTile({ slug, total, cover }: { slug: string; total: number; cover?: string }) {
  const [broken, setBroken] = useState<string>()
  const image = cover?.startsWith('https://') && cover !== broken ? cover : undefined
  const title = marketCategories[slug] ?? slug.charAt(0).toUpperCase() + slug.slice(1)
  return <li>
    <Link to={`/listings?${new URLSearchParams({ city, subcategory: slug })}`} className="ml-category"
      aria-label={`${title} · ${marketNumber.format(total)} объявлений`}>
      <span className="ml-category-photo">{image
        ? <img src={image} alt="" loading="lazy" referrerPolicy="no-referrer" onError={() => setBroken(image)} />
        : <Layers size={28} aria-hidden="true" />}</span>
      <strong>{title}</strong>
      <span className="ml-muted">{marketNumber.format(total)} объявл.</span>
    </Link>
  </li>
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
  const [failedImage, setFailedImage] = useState<string>()
  const image = listing.images.find(url => url.startsWith('https://'))
  const deviation = analysis?.priceDeviationPercent
  return <li>
    <Link to={`/listings/${encodeURIComponent(listing.id)}`} state={{ catalog: '/deals' }} className="ml-deal">
      <span className="ml-thumb">
        <Smartphone size={26} aria-hidden="true" />
        {image && image !== failedImage && <img src={image} alt="" loading="lazy" referrerPolicy="no-referrer"
          onError={() => setFailedImage(image)} />}
      </span>
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

  return <section className="ml-card" aria-labelledby="price-chart">
    <div className="ml-card-head">
      <div>
        <h2 id="price-chart">Распределение цен</h2>
        {group && <p className="ml-muted">{groupTitle(group)} · {group.sampleSize} объявл.</p>}
      </div>
      {groups.length > 1 && <div className="ml-pills" role="group" aria-label="Группа сравнения">
        {groups.slice(0, 3).map((item, index) => <button key={item.comparableGroup + item.currency}
          type="button" aria-pressed={index === selected} onClick={() => setSelected(index)}>
          {groupTitle(item)}
        </button>)}
      </div>}
    </div>
    {loading && <LoadingState />}
    {error && <ErrorState message={error} retry={retry} />}
    {!loading && !error && !group && <p className="ml-muted">Статистика появится после расчёта аналитики.</p>}
    {group && group.histogram.length > 0 && <DistributionPlot group={group} />}
    {group && group.histogram.length === 0 && <p className="ml-muted">Пока нет цен для этой группы.</p>}
    <div className="ml-chart-footer">
      {group?.medianPrice != null && <span>Медиана <strong>{formatPrice(group.medianPrice, group.currency)}</strong></span>}
      <Link to="/radar" className="ml-more">Радар цен <ArrowRight size={15} /></Link>
    </div>
  </section>
}

function DistributionPlot({ group }: { group: MarketStats }) {
  const fillId = useId()
  const height = 116
  const width = 480
  const step = Math.max(1, Math.ceil(Math.max(...group.histogram.map(bin => bin.count)) / 3))
  const max = step * 3
  const points = group.histogram.map((bin, index) => ({
    x: width * (index + 0.5) / group.histogram.length,
    y: height * (1 - bin.count / max),
  }))
  const line = points.map(({ x, y }) => `${x},${y}`).join(' ')
  const area = `${points[0].x},${height} ${line} ${points.at(-1)?.x},${height}`
  return <figure className="ml-plot" aria-label="Количество объявлений по ценовым интервалам">
    <div className="ml-plot-axis" aria-hidden="true">
      {[max, 2 * step, step, 0].map(value => <span key={value}>{marketNumber.format(value)}</span>)}
    </div>
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" aria-hidden="true">
      <defs><linearGradient id={fillId} x2="0" y2="1">
        <stop stopColor="var(--ml-chart)" stopOpacity=".24" />
        <stop offset="1" stopColor="var(--ml-chart)" stopOpacity=".04" />
      </linearGradient></defs>
      <polygon points={area} fill={`url(#${fillId})`} />
      <polyline points={line} fill="none" stroke="var(--ml-chart)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
      {points.map(({ x, y }) => <circle key={x} cx={x} cy={y} r="3.5" fill="var(--ml-chart)" />)}
    </svg>
    <ol className="ml-plot-labels">
      {group.histogram.map(bin => <li key={bin.min}>
        <span aria-hidden="true">{compact.format(bin.min)}</span>
        <span className="sr-only">{formatPrice(bin.min, group.currency)} – {formatPrice(bin.max, group.currency)}: {bin.count} объявл.</span>
      </li>)}
    </ol>
  </figure>
}
