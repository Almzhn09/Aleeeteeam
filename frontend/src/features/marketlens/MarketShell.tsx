import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { LogOut, TrendingUp } from 'lucide-react'
import { useComparison } from './MarketComparison'
import './marketlens.css'

const links = [
  { to: '/', label: 'Обзор рынка' },
  { to: '/listings', label: 'Каталог' },
  { to: '/radar', label: 'Радар цен' },
  { to: '/compare', label: 'Сравнение' },
]

export function MarketShell({ userName, onLogout, onSkip, children }: {
  userName: string
  onLogout: () => void
  onSkip: () => void
  children: ReactNode
}) {
  const { ids } = useComparison()
  return <div className="ml-shell">
    <a href="#main-content" className="skip-link" onClick={event => { event.preventDefault(); onSkip() }}>К содержимому</a>
    <header className="ml-header">
      <div className="ml-container ml-header-row">
        <MarketLogo />
        <nav aria-label="Основная навигация" className="ml-nav">
          {links.map(({ to, label }) => <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) => `ml-nav-link${isActive ? ' active' : ''}`}>{label}{to === '/compare' && ids.length > 0 && ` (${ids.length})`}</NavLink>)}
        </nav>
        <div className="ml-user">
          <span className="ml-user-name">{userName}</span>
          <button type="button" className="ml-logout" onClick={onLogout} aria-label="Выйти">
            <LogOut size={17} /><span>Выйти</span>
          </button>
        </div>
      </div>
    </header>
    <main id="main-content" className="ml-container ml-main" tabIndex={-1}>{children}</main>
  </div>
}

export function MarketLogo() {
  return <Link to="/" className="ml-logo">
    <span className="ml-logo-mark" aria-hidden="true"><TrendingUp size={20} strokeWidth={2.6} /></span>
    MarketLens
  </Link>
}
