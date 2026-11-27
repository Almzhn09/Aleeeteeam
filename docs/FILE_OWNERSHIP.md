# Владение файлами

| Ветка | Участник | Файлы |
|---|---|---|
| feat/core | Артур | backend/app/marketlens/ за исключением parsers/ и analytics/, backend/app/main.py, backend/tests/test_marketlens_core.py, frontend/src/app/MarketLensApp.tsx, frontend/src/features/marketlens/ за исключением dashboard/, frontend/src/lib/marketlens.ts, frontend/src/main.tsx, Firebase/Vite конфигурация, общие документы |
| feat/parsers | Алимжан | backend/app/marketlens/parsers/, backend/tests/marketlens_parsers/ |
| feat/analytics | Алинур | backend/app/marketlens/analytics/, backend/tests/marketlens_analytics/ |
| feat/dashboard | Улан | frontend/src/features/marketlens/dashboard/ и тесты внутри неё |

Артур подключает модули в общих точках входа. Изменения DATA_CONTRACT.md,
contracts.py, marketlens.ts и схем хранилища согласуются до правки.
Для общей интеграции сначала согласуйте версию ветки feat/core, затем
подключайте изменения из независимых веток. Существующие модули Saq остаются
доступны для повторного использования. Их изменения в рамках общего MVP
согласует Артур.
