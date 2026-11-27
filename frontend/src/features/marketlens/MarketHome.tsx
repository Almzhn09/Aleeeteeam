import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3, Coins, Flame, Info, Layers, Percent, Search,
  ShieldAlert, ShieldCheck, Smartphone, Tag,
} from 'lucide-react'
import { ErrorState, LoadingState } from '@/components/WorkspaceUI'
import { useApiQuery } from '@/lib/useApiQuery'
import type { ListingItem, ListingPage, MarketStats } from '@/lib/marketlens'
import { formatPrice, marketCategories, marketNumber, marketTime } from './dashboard/format'

const city = 'Усть-Каменогорск'
const cityParam = new URLSearchParams({ city }).toString()
const apiPath = '/api/v1/market'
const words: Record<string, string> = {
  iphone: 'iPhone', promax: 'Pro Max', pro: 'Pro', max: 'Max', plus: 'Plus', mini: 'mini',
  macbook: 'MacBook', air: 'Air', galaxy: 'Galaxy', ultra: 'Ultra', lite: 'Lite', ipad: 'iPad',
  airpods: 'AirPods', playstation: 'PlayStation', xbox: 'Xbox', jbl: 'JBL', tab: 'Tab',
}

interface TrendPoint { day: string; medianPrice: number; count: number }
interface RadarPage {
  groups: { key: string; sampleSize: number }[]
  sample: { key: string; prices: number[]; medianPrice: number | null; trend?: TrendPoint[] } | null
}

/** "electronics/phones:apple-iphone-13:128gb:any:KZT" -> "iPhone 13 (128 ГБ)". */
export function keyTitle(key: string) {
  const [scope, product, ...rest] = key.split(':')
  if (product === 'all') return marketCategories[scope.split('/')[1]] ?? scope
  if (/^\d+in$/.test(product)) return `Экран ${product.replace('in', '″')}`
  const parts = product.split('-')
  const name = (parts.length > 1 ? parts.slice(1) : parts)
    .map(word => words[word] ?? word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
  const variant = rest.length === 3 ? rest[0].replace(/(\d+)gb$/, '$1 ГБ').replace(/(\d+)tb$/, '$1 ТБ') : null
  return variant ? `${name} (${variant})` : name
}

export function groupTitle(group: Pick<MarketStats, 'comparableGroup'>) {
  return keyTitle(group.comparableGroup)
}

function count(page: ListingPage | null) {
  if (!page) return '—'
  if (page.total != null) return marketNumber.format(page.total)
  return page.nextOffset === null ? marketNumber.format(page.items.length) : `${page.items.length}+`
}

const percent = (value: number) =>
  `${value > 0 ? '+' : value < 0 ? '−' : ''}${marketNumber.format(Math.abs(Math.round(value * 10) / 10))}%`

function lastDays(trend: TrendPoint[], days: number) {
  if (!trend.length) return []
  const last = new Date(trend[trend.length - 1].day).getTime()
  return trend.filter(point => last - new Date(point.day).getTime() < days * 86_400_000)
}

/** Change between the first and last point of the trend inside the window. */
function change(trend: TrendPoint[], days: number) {
  const points = lastDays(trend, days)
  if (points.length < 2) return null
  return (points[points.length - 1].medianPrice - points[0].medianPrice) / points[0].medianPrice * 100
}

export function MarketHome() {
  const navigate = useNavigate()
  const all = useApiQuery<ListingPage>(`${apiPath}/listings?view=all&limit=1&${cityParam}`)
  const deals = useApiQuery<ListingPage>(`${apiPath}/listings?view=deals&limit=4&${cityParam}`)
  const risk = useApiQuery<ListingPage>(`${apiPath}/listings?view=risk&limit=1&${cityParam}`)
  const radar = useApiQuery<RadarPage>(`${apiPath}/radar?${new URLSearchParams({ city, group: '' })}`)

  const sample = radar.data?.sample
  const trend = sample?.trend ?? []
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
        <p className="ml-kicker"><KickerMark /> Аналитика объявлений Казахстана</p>
        <h1>Умный поиск <em>выгодных</em> предложений</h1>
        <p className="ml-lead">Анализируем объявления OLX в Усть-Каменогорске.<br />
          Сравниваем цены, находим выгодные предложения и показываем признаки риска.</p>
        <form className="ml-search" role="search" onSubmit={search}>
          <Search size={20} aria-hidden="true" />
          <input name="q" type="search" maxLength={120} aria-label="Поиск объявлений"
            placeholder="Найти товар, например: iPhone 13…" />
          <button type="submit">Найти</button>
        </form>
      </div>
      <HeroArt />
      <ul className="ml-features">
        <li><span><BarChart3 size={22} /></span><div><strong>Реальные цены</strong>и рыночная аналитика</div></li>
        <li><span><ShieldCheck size={22} /></span><div><strong>Проверка</strong>признаков риска</div></li>
        <li><span><Percent size={22} /></span><div><strong>Выгодные предложения</strong>ниже медианы модели</div></li>
      </ul>
    </section>

    <section className="ml-kpis" aria-label="Ключевые показатели">
      <Kpi icon={<Layers size={22} />} tone="green"
        value={all.data ? marketNumber.format(all.data.total ?? all.data.scannedCount) + (all.data.scanLimited ? '+' : '') : '—'}
        label="Объявлений в базе" note={latest ? `Сбор: ${marketTime.format(new Date(latest))}` : 'OLX'} />
      <Kpi icon={<Tag size={22} />} tone="green" value={count(deals.data)} label="Выгодных предложений"
        note={<Link to="/deals">Смотреть</Link>} />
      <Kpi icon={<ShieldAlert size={22} />} tone="red" value={count(risk.data)} label="Требуют проверки"
        note={<Link to="/risk">Смотреть</Link>} />
      <Kpi icon={<Coins size={22} />} tone="amber"
        value={sample?.medianPrice != null ? formatPrice(sample.medianPrice, 'KZT') : '—'}
        label={sample ? `Медиана (${keyTitle(sample.key).replace(/ \((.+)\)$/, ' $1')})` : 'Медианная цена'}
        trend={change(trend, 7)} trendGoodWhenDown />
    </section>

    <div className="ml-columns">
      <TrendChart sampleKey={sample?.key} trend={trend} loading={radar.loading} error={radar.error}
        retry={radar.refresh} />
      <section className="ml-card" aria-labelledby="top-deals">
        <div className="ml-card-head">
          <h2 id="top-deals" className="ml-title-icon"><Flame size={22} aria-hidden="true" /> Топ выгодных предложений</h2>
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

    {categories.length > 0 && <section className="ml-categories-wrap" aria-labelledby="categories">
      <div className="ml-card-head">
        <h2 id="categories" className="ml-section-title">Категории · {city}</h2>
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

function Kpi({ icon, tone, value, label, note, trend, trendGoodWhenDown }: {
  icon: ReactNode; tone: 'green' | 'red' | 'amber'; value: string; label: string; note?: ReactNode
  trend?: number | null; trendGoodWhenDown?: boolean
}) {
  const good = trend != null && (trendGoodWhenDown ? trend <= 0 : trend >= 0)
  return <div className="ml-kpi">
    <span className={`ml-kpi-icon ${tone}`} aria-hidden="true">{icon}</span>
    <div><strong>{value}</strong><span>{label}</span>{note && <small>{note}</small>}</div>
    {trend != null && <span className={`ml-trend ${good ? 'good' : 'bad'}`} title="Изменение медианы за 7 дней">
      {percent(trend)} {trend > 0
        ? <ArrowUpRight size={15} aria-hidden="true" />
        : <ArrowDownRight size={15} aria-hidden="true" />}
      <span className="ml-visually-hidden"> за 7 дней</span>
    </span>}
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
          <span>{listing.source === 'olx' ? 'OLX.kz' : listing.source.toUpperCase()}</span>
          {listing.city && <span>{listing.city}</span>}
        </span>
      </span>
      <span className="ml-deal-price">
        <strong>{formatPrice(listing.price, listing.currency)}</strong>
        {deviation != null && <span className="ml-badge">{percent(Math.round(deviation))} от рынка</span>}
      </span>
      <span className="ml-arrow" aria-hidden="true"><ArrowRight size={18} /></span>
    </Link>
  </li>
}

const ranges = [[7, '7 дней'], [30, '30 дней'], [90, '3 месяца']] as const
const dayLabel = new Intl.DateTimeFormat('ru-RU', { day: '2-digit', month: '2-digit', timeZone: 'UTC' })
const axisNumber = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

function TrendChart({ sampleKey, trend, loading, error, retry }: {
  sampleKey?: string; trend: TrendPoint[]; loading: boolean; error: string | null; retry: () => void
}) {
  const [days, setDays] = useState<number>(7)
  const points = lastDays(trend, days)
  return <section className="ml-card" aria-labelledby="price-chart">
    <div className="ml-card-head">
      <div>
        <h2 id="price-chart" className="ml-title-icon">Динамика средней цены
          <span className="ml-info" title="Медиана цен одной модели по дням сбора OLX">
            <Info size={16} aria-hidden="true" /></span></h2>
        {sampleKey && <p className="ml-muted">{keyTitle(sampleKey)}</p>}
      </div>
      <div className="ml-pills" role="group" aria-label="Период">
        {ranges.map(([value, label]) => <button key={value} type="button" aria-pressed={days === value}
          onClick={() => setDays(value)}>{label}</button>)}
      </div>
    </div>
    {loading && <LoadingState />}
    {error && <ErrorState message={error} retry={retry} />}
    {!loading && !error && !points.length && <p className="ml-muted">Динамика появится после расчёта цен по модели.</p>}
    {points.length > 0 && <LineChart key={days} points={points} delta={change(trend, days)} />}
    {points.length === 1 && <p className="ml-muted ml-chart-note">Пока есть данные только за один день сбора.
      Линия появится после следующих ежедневных обновлений.</p>}
    <Link to="/radar" className="ml-more">Открыть радар цен <ArrowRight size={15} /></Link>
  </section>
}

function niceStep(raw: number) {
  const power = 10 ** Math.floor(Math.log10(Math.max(raw, 1)))
  return [1, 2, 2.5, 5, 10].map(factor => factor * power).find(step => step >= raw) ?? power * 10
}

function LineChart({ points, delta }: { points: TrendPoint[]; delta: number | null }) {
  const width = 600, height = 230, left = 64, right = 28, top = 24, bottom = 34
  const values = points.map(point => point.medianPrice)
  const min = Math.min(...values), max = Math.max(...values)
  const spread = max - min || max * 0.1 || 1
  const step = niceStep(spread / 3)
  const low = Math.floor((min - spread * 0.25) / step) * step
  const high = Math.ceil((max + spread * 0.25) / step) * step
  const ticks = Array.from({ length: Math.round((high - low) / step) + 1 }, (_, index) => low + index * step)
  const x = (index: number) => points.length === 1 ? (left + width - right) / 2
    : left + index * (width - left - right) / (points.length - 1)
  const y = (value: number) => top + (high - value) / (high - low || 1) * (height - top - bottom)
  const line = points.map((point, index) => `${index ? 'L' : 'M'}${x(index)},${y(point.medianPrice)}`).join(' ')
  const area = `${line} L${x(points.length - 1)},${height - bottom} L${x(0)},${height - bottom} Z`
  const last = points[points.length - 1]
  const labelEvery = Math.ceil(points.length / 7)
  const summary = points.map(point => `${dayLabel.format(new Date(point.day))}: ${formatPrice(point.medianPrice, 'KZT')}`)
  return <div className="ml-line">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`Медиана по дням. ${summary.join('; ')}`}>
      <defs>
        <linearGradient id="ml-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#22c55e" stopOpacity="0.24" /><stop offset="1" stopColor="#22c55e" stopOpacity="0" />
        </linearGradient>
      </defs>
      {ticks.map(tick => <g key={tick} className="ml-grid">
        <line x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} />
        <text x={left - 10} y={y(tick) + 4} textAnchor="end">{axisNumber.format(tick)}</text>
      </g>)}
      {points.length > 1 && <path d={area} fill="url(#ml-area)" className="ml-line-area" />}
      {points.length > 1 && <path d={line} className="ml-line-path" pathLength={1} />}
      {points.map((point, index) => <circle key={point.day} cx={x(index)} cy={y(point.medianPrice)}
        r={index === points.length - 1 ? 6 : 4.5} className="ml-line-dot" />)}
      {points.map((point, index) => (index % labelEvery === 0 || index === points.length - 1) &&
        <text key={point.day} x={x(index)} y={height - 10} textAnchor="middle" className="ml-axis-x">
          {dayLabel.format(new Date(point.day))}</text>)}
    </svg>
    <span className="ml-line-tip" aria-hidden="true"
      style={{ left: `${x(points.length - 1) / width * 100}%`, top: `${y(last.medianPrice) / height * 100}%` }}>
      <strong>{formatPrice(last.medianPrice, 'KZT')}</strong>
      {delta != null && <span>{percent(delta)}</span>}
    </span>
  </div>
}

function KickerMark() {
  return <svg width="26" height="20" viewBox="0 0 26 20" aria-hidden="true">
    <rect x="0" y="11" width="6" height="9" rx="1.5" fill="#facc15" />
    <rect x="10" y="6" width="6" height="14" rx="1.5" fill="#22c55e" />
    <rect x="20" y="0" width="6" height="20" rx="1.5" fill="#15803d" />
  </svg>
}

/** Two generic smartphones: the back with a camera block and the front with a green wallpaper. */
function HeroArt() {
  const lenses = [[94, 60], [94, 98], [128, 79]]
  return <div className="ml-hero-art" aria-hidden="true">
    <svg viewBox="0 0 360 330" role="presentation">
      <defs>
        <linearGradient id="ml-metal" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#f4f5f4" /><stop offset="0.45" stopColor="#c9ccca" /><stop offset="1" stopColor="#8d918f" />
        </linearGradient>
        <linearGradient id="ml-back" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#eceeed" /><stop offset="1" stopColor="#b9bdbb" />
        </linearGradient>
        <linearGradient id="ml-wall" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#0f2f1f" /><stop offset="0.45" stopColor="#3f9b6a" />
          <stop offset="0.7" stopColor="#bfe8cf" /><stop offset="1" stopColor="#1d5a3b" />
        </linearGradient>
        <radialGradient id="ml-lens" cx="0.4" cy="0.35" r="0.7">
          <stop offset="0" stopColor="#4b5563" /><stop offset="0.6" stopColor="#111827" /><stop offset="1" stopColor="#000" />
        </radialGradient>
        <filter id="ml-shadow" x="-30%" y="-30%" width="160%" height="160%">
          <feDropShadow dx="0" dy="18" stdDeviation="16" floodColor="#0f2f1f" floodOpacity="0.22" />
        </filter>
      </defs>
      <ellipse cx="200" cy="230" rx="170" ry="120" className="ml-hero-glow" />
      <g filter="url(#ml-shadow)" transform="rotate(-8 130 160)">
        <rect x="58" y="20" width="150" height="290" rx="30" fill="url(#ml-metal)" />
        <rect x="63" y="25" width="140" height="280" rx="26" fill="url(#ml-back)" />
        <rect x="74" y="38" width="76" height="80" rx="20" fill="#d7dad8" stroke="#a9adab" />
        {lenses.map(([cx, cy]) => <g key={`${cx}-${cy}`}>
          <circle cx={cx} cy={cy} r="15" fill="#9ca3a0" /><circle cx={cx} cy={cy} r="11.5" fill="url(#ml-lens)" />
          <circle cx={cx - 3} cy={cy - 4} r="2.5" fill="#fff" opacity="0.5" />
        </g>)}
        <circle cx="132" cy="50" r="5" fill="#f5f5f4" stroke="#a8a29e" />
      </g>
      <g filter="url(#ml-shadow)" transform="rotate(4 250 175)">
        <rect x="170" y="35" width="150" height="290" rx="30" fill="#1f2421" />
        <rect x="176" y="41" width="138" height="278" rx="25" fill="url(#ml-wall)" />
        <path d="M176 220 C230 160 260 260 314 170 L314 294 Q314 319 289 319 L201 319 Q176 319 176 294 Z"
          fill="#14532d" opacity="0.55" />
        <rect x="222" y="52" width="46" height="13" rx="6.5" fill="#0b0f0d" />
      </g>
    </svg>
  </div>
}
