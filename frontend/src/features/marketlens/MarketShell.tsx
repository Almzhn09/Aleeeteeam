import { useEffect, useState, type ReactNode } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { Moon, Sun } from 'lucide-react'
import { useComparison } from './MarketComparison'
import './marketlens.css'

const links = [
  { to: '/', label: 'Обзор рынка' },
  { to: '/listings', label: 'Каталог' },
  { to: '/radar', label: 'Радар цен' },
  { to: '/compare', label: 'Сравнение' },
]
// Подборки /deals и /risk остаются рабочими URL и подсвечивают «Каталог».
const catalogPaths = ['/listings', '/deals', '/risk']
const themeKey = 'marketlens-theme'

function initialDark() {
  try {
    const saved = localStorage.getItem(themeKey)
    if (saved) return saved === 'dark'
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
  } catch {
    return false
  }
}

export function MarketShell({ userName, onLogout, onSkip, children }: {
  userName: string
  onLogout: () => void
  onSkip: () => void
  children: ReactNode
}) {
  const { ids } = useComparison()
  const { pathname } = useLocation()
  const [dark, setDark] = useState(initialDark)
  useEffect(() => {
    try { localStorage.setItem(themeKey, dark ? 'dark' : 'light') } catch { /* private mode */ }
  }, [dark])
  const inCatalog = catalogPaths.some(path => pathname === path || pathname.startsWith('/listings/'))
  return <div className={`ml-shell${dark ? ' ml-dark' : ''}`}>
    <a href="#main-content" className="skip-link" onClick={event => { event.preventDefault(); onSkip() }}>К содержимому</a>
    <header className="ml-header">
      <div className="ml-container ml-header-row">
        <MarketLogo />
        <nav aria-label="Основная навигация" className="ml-nav">
          {links.map(({ to, label }) => <NavLink key={to} to={to} end={to === '/'}
            aria-label={to === '/compare' && ids.length ? `${label} (${ids.length})` : undefined}
            className={({ isActive }) => `ml-nav-link${isActive || (to === '/listings' && inCatalog) ? ' active' : ''}`}>
            {label}{to === '/compare' && ids.length > 0 && <>{' '}
              <span className="ml-count" aria-hidden="true" key={ids.length}>{ids.length}</span>
            </>}
          </NavLink>)}
        </nav>
        <div className="ml-user">
          <button type="button" className="ml-theme" onClick={() => setDark(value => !value)}
            aria-label={dark ? 'Светлая тема' : 'Тёмная тема'} aria-pressed={dark}>
            {dark ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          <span className="ml-user-name">{userName}</span>
          <button type="button" className="ml-logout" onClick={onLogout} aria-label="Выйти">Выйти</button>
        </div>
      </div>
    </header>
    <main id="main-content" className="ml-container ml-main" tabIndex={-1}>{children}</main>
  </div>
}

export function MarketLogo() {
  return <Link to="/" className="ml-logo">
    <svg className="ml-logo-mark" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M4 26 L13 6 Q14 4 16 4 L19 4 L10 24 Q9 26 7 26 Z" fill="#14532d" />
      <path d="M15 26 L24 6 Q25 4 27 4 L30 4 L21 24 Q20 26 18 26 Z" fill="#16a34a" />
    </svg>
    MarketLens
  </Link>
}
