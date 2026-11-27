# Локальное окружение MarketLens

Firebase Auth и Firestore работают на loopback в отдельном проекте
`demo-marketlens-local`. Понадобятся Python 3.12, uv, Node.js 24 и Java 21.
Настройте зависимости backend и frontend по README.

Из корня репозитория запустите эмуляторы:

```bash
npm exec --yes --package firebase-tools@15.34.0 -- firebase emulators:start \
  --only auth,firestore --project demo-marketlens-local --config firebase.marketlens.local.json
```

В терминале backend задайте следующие переменные. Для команды назначения
роли, импорта и запуска API используйте то же окружение.

```bash
cd backend
export MARKETLENS_FIREBASE_ENABLED=true MARKETLENS_FIREBASE_PROJECT_ID=demo-marketlens-local
export FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9199 FIRESTORE_EMULATOR_HOST=127.0.0.1:8188
export MARKETLENS_GEMINI_API_KEY= MARKETLENS_GEMINI_MODEL=
```

Создайте временную учётную запись в Auth Emulator. Используйте уникальный
локальный пароль и введите его снова при входе в веб-интерфейс.

```bash
uv run --frozen python - <<'PY'
from getpass import getpass

from firebase_admin import auth

from app.marketlens.runtime import marketlens_runtime
from app.marketlens.settings import MarketLensSettings

runtime = marketlens_runtime(MarketLensSettings())
try:
    user = auth.create_user(
        email="tester@example.test", password=getpass("Local password: "), app=runtime.app()
    )
    print(user.uid)
finally:
    runtime.close()
PY
uv run --frozen python -m app.cli.role UID analyst --marketlens \
  --project-confirm demo-marketlens-local
uv run --frozen uvicorn app.marketlens.main:create_marketlens_app --factory --port 8010
```

В терминале frontend запустите dev-сервер:

```bash
cd frontend
export VITE_MARKETLENS_FIREBASE_PROJECT_ID=demo-marketlens-local
export VITE_MARKETLENS_FIREBASE_API_KEY=local-demo VITE_MARKETLENS_FIREBASE_APP_ID=local-demo
export VITE_MARKETLENS_FIREBASE_AUTH_DOMAIN=localhost
export VITE_MARKETLENS_AUTH_EMULATOR_HOST=127.0.0.1:9199
npm run dev -- --mode marketlens --host 127.0.0.1 --port 5174
```

Откройте приложение на порту 5174 и войдите как `tester@example.test`.
Для заполнения каталога импортируйте разрешённую выборку реальных объявлений
по [контракту](DATA_CONTRACT.md). Импорт из отдельного backend-терминала требует
тех же переменных. Повторный импорт файла должен сохранить ноль новых снимков.

```bash
uv run --frozen python -m app.marketlens.import_listings /path/to/listings.json
uv run --frozen python -m app.marketlens.refresh_analytics
```

Сверьте количество карточек, цены, город и ссылки с оригиналами. При отсутствии
расчётов карточка показывает неизвестную оценку, а кнопка пояснения возвращает
локальный ответ. Без явного экспорта состояние эмуляторов исчезает при остановке.
