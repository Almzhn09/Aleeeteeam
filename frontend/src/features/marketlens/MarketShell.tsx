import { useState, type ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { Columns2, LogOut, Moon, Sun } from 'lucide-react'
import { useComparison } from './MarketComparison'
import './marketlens.css'

const links = [
  { to: '/', label: 'Главная' },
  { to: '/radar', label: 'Аналитика' },
  { to: '/listings', label: 'Объявления' },
  { to: '/deals', label: 'Выгодные' },
  { to: '/risk', label: 'Проверка' },
]

export function MarketShell({ userName, onLogout, onSkip, children }: {
  userName?: string
  onLogout?: () => void
  onSkip: () => void
  children: ReactNode
}) {
  const { ids } = useComparison()
  const [theme, setTheme] = useState(() => localStorage.getItem('marketlens-theme') === 'dark' ? 'dark' : 'light')

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    setTheme(next)
    localStorage.setItem('marketlens-theme', next)
  }

  return <div className="ml-shell" data-theme={theme}>
    <a href="#main-content" className="skip-link" onClick={event => { event.preventDefault(); onSkip() }}>К содержимому</a>
    <header className="ml-header">
      <div className="ml-container ml-header-row">
        <MarketLogo />
        {onLogout && <nav aria-label="Основная навигация" className="ml-nav">
          {links.map(({ to, label }) => <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) => `ml-nav-link${isActive ? ' active' : ''}`}>{label}</NavLink>)}
        </nav>}
        <div className="ml-user">
          {onLogout && <NavLink to="/compare" className="ml-icon-button"
            aria-label={ids.length ? `Сравнение (${ids.length})` : 'Сравнение'} title="Сравнение">
            <Columns2 size={18} aria-hidden="true" />
            {ids.length > 0 && <span className="ml-count" aria-hidden="true">{ids.length}</span>}
          </NavLink>}
          <button type="button" className="ml-icon-button" onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Включить светлую тему' : 'Включить тёмную тему'}>
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>
          {onLogout && <button type="button" className="ml-logout" onClick={onLogout}
            aria-label="Выйти" title={userName}>
            <LogOut size={15} aria-hidden="true" /><span>Выйти</span>
          </button>}
        </div>
      </div>
    </header>
    <main id="main-content" className="ml-container ml-main" tabIndex={-1}>{children}</main>
  </div>
}

function MarketLogo() {
  return <Link to="/" className="ml-logo">
    <span className="ml-logo-mark" aria-hidden="true" />
    MarketLens
  </Link>
}
