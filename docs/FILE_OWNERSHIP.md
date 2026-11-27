# Владение файлами

| Ветка | Участник | Файлы |
|---|---|---|
| `feat/core` | Артур | `backend/app/marketlens/` за исключением `parsers/` и `analytics/`, общие API и тесты интеграции, Firebase/Vite, весь `frontend/src/features/marketlens/` включая `dashboard/`, навигация, общие документы |
| `feat/parsers` | Алимжан | `backend/app/marketlens/parsers/`, `backend/tests/marketlens_parsers/` |
| `feat/analytics` | Алинур | `backend/app/marketlens/analytics/`, `backend/tests/marketlens_analytics/` |

Проверяйте свою зону по [плану](TASKS.md). У каждого модуля есть независимый
тестовый вход по контракту. Артур подключает модули в общих точках входа.
Изменения `DATA_CONTRACT.md`, `contracts.py`, `marketlens.ts` и схем
хранилища согласуются до правки. Улан пока вне распределения, отдельная
ветка дашборда для текущего этапа не требуется.
