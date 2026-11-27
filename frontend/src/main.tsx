import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { App } from './app/App'
import './index.css'
import { AuthProvider } from './features/auth/AuthProvider'

const marketLens = import.meta.env.MODE === 'marketlens'

createRoot(document.getElementById('root')!).render(
  <StrictMode><BrowserRouter><AuthProvider><App marketLens={marketLens} /></AuthProvider></BrowserRouter></StrictMode>,
)
