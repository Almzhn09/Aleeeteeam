import { execFileSync } from 'node:child_process'
import { writeFileSync } from 'node:fs'

const git = (...args) => execFileSync('git', args, { encoding: 'utf8' }).trim()
if (git('status', '--porcelain')) {
  console.error('Закоммитьте изменения перед выпуском MarketLens, чтобы release.json указывал точный SHA.')
  process.exit(1)
}

const release = { app: 'MarketLens', commit: git('rev-parse', 'HEAD'), builtAt: new Date().toISOString() }
writeFileSync(new URL('../dist-marketlens/release.json', import.meta.url), JSON.stringify(release) + '\n')
