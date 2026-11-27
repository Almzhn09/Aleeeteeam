import { loadEnv } from 'vite'

const env = loadEnv('marketlens', '..', ['VITE_MARKETLENS_', 'MARKETLENS_FIREBASE_PROJECT_ID'])
const prefix = 'VITE_MARKETLENS_'
const required = ['FIREBASE_API_KEY', 'FIREBASE_AUTH_DOMAIN', 'FIREBASE_PROJECT_ID',
  'FIREBASE_APP_ID', 'API_BASE_URL']
const missing = required.map(name => prefix + name).filter(name => !env[name]?.trim())
if (!env.MARKETLENS_FIREBASE_PROJECT_ID?.trim()) missing.push('MARKETLENS_FIREBASE_PROJECT_ID')
if (missing.length) {
  console.error(`Заполните настройки MarketLens: ${missing.join(', ')}`)
  process.exit(1)
}

const project = env.VITE_MARKETLENS_FIREBASE_PROJECT_ID
const allowedProject = project === 'hackos20' || /^marketlens-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/.test(project)
if (!allowedProject ||
    project.length > 30 || project !== env.MARKETLENS_FIREBASE_PROJECT_ID) {
  console.error('Укажите один выделенный Firebase-проект MarketLens для API и Hosting.')
  process.exit(1)
}
if (env.VITE_MARKETLENS_AUTH_EMULATOR_HOST?.trim()) {
  console.error('Уберите VITE_MARKETLENS_AUTH_EMULATOR_HOST для сборки Hosting.')
  process.exit(1)
}
try {
  const api = new URL(env.VITE_MARKETLENS_API_BASE_URL)
  if (api.protocol !== 'https:' || api.username || api.password ||
    api.pathname !== '/' || api.search || api.hash) throw new Error('Invalid HTTPS origin')
} catch {
  console.error('VITE_MARKETLENS_API_BASE_URL должен быть HTTPS origin API без пути и credentials.')
  process.exit(1)
}
