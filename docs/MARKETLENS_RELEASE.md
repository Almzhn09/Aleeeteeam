# Облачный релиз MarketLens

Для репетиции используйте [локальное окружение](MARKETLENS_LOCAL.md).
Для облачной публикации используйте проект `hackos20` или отдельный проект
с ID `marketlens-…`. Для выпуска нужны
Firebase Auth (Email/Password), Firestore, Hosting, Cloud Run,
Cloud Build и Artifact Registry. Укажите выделенную серверную учётную запись
с доступом к Firestore и чтению пользователей Firebase Auth. Оператору,
который назначает роль `analyst`, нужен отдельный доступ на изменение
пользователей. Используйте Application Default Credentials или доверенную
серверную идентичность. Ключи в Git и клиентской сборке не требуются.

В `hackos20` Firestore уже находится в `nam5`. Это мультирегион базы.
Для Cloud Run и Artifact Registry укажите поддерживаемый регион отдельно,
например `us-central1`.

## Собрать и развернуть API

Из корня репозитория задайте параметры уже созданных облачных ресурсов:

```bash
PROJECT_ID=marketlens-example
REGION=YOUR_REGION
REPOSITORY=YOUR_ARTIFACT_REGISTRY_REPOSITORY
SERVICE_ACCOUNT=YOUR_MARKETLENS_SERVICE_ACCOUNT_EMAIL
IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/api:$(git rev-parse --short HEAD)"
```

Скопируйте `deploy/marketlens-cloud-run.env.example.yaml` в
`deploy/marketlens-cloud-run.env.yaml` и замените ID и CORS-origin на свои.
Затем соберите и опубликуйте API в указанном проекте.

```bash
gcloud builds submit --project "$PROJECT_ID" \
  --config deploy/marketlens-cloudbuild.yaml --substitutions "_IMAGE=$IMAGE"

gcloud run deploy marketlens-api --project "$PROJECT_ID" --region "$REGION" \
  --image "$IMAGE" --port 8000 --service-account "$SERVICE_ACCOUNT" \
  --env-vars-file deploy/marketlens-cloud-run.env.yaml --allow-unauthenticated
```

Внешняя доступность Cloud Run нужна для запросов браузера. Маршруты каталога,
аналитики и объяснений требуют Firebase Bearer-токен и роль. Заполните
`VITE_MARKETLENS_API_BASE_URL` HTTPS-адресом этого сервиса. Поля Gemini
могут оставаться пустыми. Если подключаете Gemini, передавайте ключ только
серверу через Secret Manager. Перед каждым вызовом Gemini сервер резервирует
запрос на сутки по UTC. Лимиты по умолчанию — 20 запросов на пользователя и
100 на проект. Переменные `MARKETLENS_AI_DAILY_USER_LIMIT` и
`MARKETLENS_AI_DAILY_GLOBAL_LIMIT` меняют эти значения. При исчерпании квоты
или недоступности счётчиков доступно локальное пояснение. Gemini объясняет
результаты словами. Цифры и графики интерфейс берёт из расчётов сервера.

### Внешние пояснения через OpenAI

Для OpenAI задайте `MARKETLENS_OPENAI_MODEL` с названием модели,
поддерживающей Structured Outputs в Chat Completions. Привяжите секрет
`MARKETLENS_OPENAI_API_KEY` из Secret Manager как одноимённую переменную
Cloud Run. Сервисной учётной записи API нужен доступ к этому секрету.

При наличии обеих настроек OpenAI имеет приоритет перед Gemini. Запрос
содержит только рассчитанные показатели, цену и валюту. Для OpenAI
выключено сохранение ответа через параметр `store`. Оба провайдера
используют один лимит на пояснения. При ошибке или исчерпанной квоте API
возвращает локальное пояснение.

## Собрать и развернуть Hosting и Firestore

Заполните корневой `.env.marketlens.local` по шаблону
`marketlens.env.example`. Серверный и браузерный project ID должны совпадать.
Настройте разрешённый домен в Firebase Auth. Из корня репозитория:

```bash
(cd frontend && npm ci && npm run build:marketlens:hosting)
firebase deploy --project "$PROJECT_ID" --config firebase.marketlens.json \
  --only firestore,hosting
```

MarketLens публикуется из `frontend/dist-marketlens`. Команда
`build:marketlens:hosting` требует чистого рабочего дерева и записывает SHA
в `release.json`. После публикации сравните поле `commit` в ответе
`https://PROJECT_ID.web.app/release.json` с SHA релизной ветки и тегом образа API. Конфигурация разворачивает
закрытые правила клиента и индекс истории цен. Дождитесь готовности индекса,
затем войдите под пользователем с ролью `analyst` и откройте карточку.

## Обновить данные и проверить релиз

Запустите доверенный импорт с правом записи в этот проект. Для OLX требуется
подтверждённое разрешение. Из `backend/`:

```bash
uv run --frozen python -m app.marketlens.update_olx --authorized --limit 30
```

После обновления версии расчёта пересчитайте уже импортированные карточки
через `python -m app.marketlens.refresh_analytics` в том же окружении.
Проверьте `/api/v1/health`, ответ 401 каталога без токена, вход, график,
историю цен, ссылку на оригинал и локальное пояснение. Для отката API
используйте предыдущую ревизию Cloud Run и соответствующую версию Hosting.

## Локальная приёмка 27 ноября 2026 года

На исходниках `222b513` сбор OLX, импорт и расчёт через два эмулятора
обработали 30 уникальных объявлений и 6 рыночных групп без Gemini.
В Chromium проверены вход аналитика, обзор, каталог, карточка, история,
ссылка на оригинал, локальное пояснение и навигация по подборкам.
Проверка каталога при ширине 390 px прошла без горизонтальной прокрутки.
В живой выборке подборки были пустыми. Критерии включения карточек покрыты
автоматическими тестами.

Прошли 632 теста backend, 25 интеграционных тестов с эмуляторами и 144 теста
frontend. Скрипт [локальной приёмки](MARKETLENS_LOCAL.md) повторяет проверки
защиты API, фильтров, подборок и истории на заполненном каталоге.

## Ежедневное обновление OLX в hackos20

После подтверждения разрешения на регулярный сбор запустите из корня
репозитория в авторизованном Google Cloud Shell:

```bash
bash deploy/marketlens-olx-schedule.sh --authorized
```

Скрипт собирает образ из текущего коммита и один раз запускает импорт
в Cloud Run Job. Работающий API при этом сохраняет свою версию. После успешного запуска он настраивает Cloud Scheduler
на 09:00 по времени Алматы. Один запуск обрабатывает до 12 страниц каждой из двух категорий OLX
в Усть-Каменогорске и сохраняет до 400 телефонов и 400 ноутбуков.
Охват всего города по этим двум категориям оценить нельзя. После успешного
включения городского расписания скрипт ставит прежнее расписание iPhone 15
на паузу, если оно было активно.
При отказе OLX, включая HTTP 403, расписание не создаётся и не обновляется.
Проверьте условия доступа к источнику по выводу пробного запуска.
Состояние выполнения проверяйте в Cloud Run Jobs. Вызов Cloud Scheduler
подтверждает запуск задания, завершение импорта отражается в логах задания.

Cloud Run Job и Cloud Scheduler используют биллинг проекта. Для паузы:

```bash
gcloud scheduler jobs pause marketlens-olx-oskemen-daily \
  --project=hackos20 --location=us-central1
```

## Выпуск расширенной витрины

Проверенная выборка содержит 360 новых объявлений Усть-Каменогорска, по
20 в каждой из 18 категорий. Смартфоны и ноутбуки уже есть в каталоге.
JSON для выпуска передаётся через закрытый репозиторий команды.

Из чистого checkout согласованного коммита запустите в Cloud Shell:

```bash
bash deploy/marketlens-expansion-release.sh /путь/к/новым-объявлениям.json
```

Необязательный второй аргумент — подготовленный скрипт добавления фото
в существующие карточки. Релиз обновляет образ API, импортирует объявления,
пересчитывает аналитику и публикует Hosting. Правила Firestore и расписание
сбора остаются без изменений. В конце скрипт сверяет публичный маркер
`release.json` с SHA текущего checkout.
