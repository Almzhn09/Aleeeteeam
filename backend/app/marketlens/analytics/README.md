# Аналитика MarketLens (`feat/analytics`)

Детерминированный расчёт без сети, Firestore и AI. Один и тот же набор Listing
и один и тот же `computed_at` дают одинаковый результат при любом порядке входа.

## Точка вызова

```python
from app.marketlens.analytics import ALGORITHM_VERSION, analyze

analysis = analyze(listings, computed_at=datetime.now(UTC))
analysis.results  # list[AnalysisResult] — по одному на каждый уникальный listing.id
analysis.stats  # list[MarketStats] — группы оценки и обзор по бренду и категории
```

- Вход: любые `Listing` по контракту v1. Повторы одного ID сворачиваются
  до последнего `scrapedAt`; `listingScrapedAt` в результате указывает именно его.
- `computed_at` обязателен и должен содержать часовой пояс.
- `algorithmVersion` = `ALGORITHM_VERSION` (`"v2"`). При смене формулы версия
  поднимается — API может сравнить версию и вернуть `analysis=null`.
- Сохранение: `MarketStore.save_analysis(result)` и `publish_stats(stats, computed_at)` из core
  уже принимают эти объекты без изменений контракта.

Сценарий для интеграции (Артур): после импорта прочитать актуальные карточки
(`scan_listings()` или все реальные записи), вызвать `analyze`, сохранить оба
результата. Тестовые записи в `analyze` можно передавать вместе с реальными —
группы и статистика по `dataset` не смешиваются, но для каталога передавайте
только `real`.

## CLI (из `backend/`)

```bash
uv run --frozen python -m app.marketlens.analytics listings.json \
  --computed-at 2026-11-27T09:05:00Z > analysis.json
```

`listings.json` — экспорт `collect_olx`. Вывод: `{"results": [AnalysisResult],
"stats": [MarketStats]}` в camelCase. В stderr печатается сводка: сколько
карточек получили оценку рынка, выгодных, с риском medium/high и групп.
Firestore не используется.

## Группы сравнения

Группа всегда разделяет `dataset`, категорию/подкатегорию, состояние
(`condition` или `any`) и валюту. Внутри категории модель определяется по
заголовку (латиница и кириллица: «айфон», «самсунг», «редми ноут», «гб»).
Отдельные правила — для iPhone, Samsung Galaxy, Xiaomi/Redmi/Poco и Pixel; для
Huawei, Honor, Realme, OnePlus, Oppo, Vivo, Tecno, Infinix, Nokia и Motorola —
общее «бренд [серия] код [pro|lite|…]», например `tecno-spark20-pro`.

| Уровень | Пример `comparableGroup` | Роль |
|---|---|---|
| variant | `electronics/phones:apple-iphone-13:128gb:any:KZT` | оценка, вес доверия 1.0 |
| model | `electronics/phones:apple-iphone-13:any:KZT` | оценка, вес доверия 0.9 |
| brand | `electronics/phones:apple:any:KZT` | только обзор в `MarketStats` |
| category | `electronics/phones:all:any:KZT` | только обзор в `MarketStats` |

Цена сравнивается только внутри одной модели: сначала с памятью, затем без неё,
если есть хотя бы 4 других объявления с ценой (`MIN_PEERS`). Бренд и категория
в оценку не идут: живая первая страница OLX — всего 30 карточек (27.11.2026),
на них много разных моделей, а сравнение iPhone 15 Pro с Redmi давало бы
ложные выгоды и ложные признаки риска. Город в группу не входит. Без своей
модели оценка не выставляется.

## Формулы

- `marketPrice` — медиана цен других объявлений группы (само объявление
  исключено). `sampleSize` — число этих объявлений.
- `priceDeviationPercent = (price − marketPrice) / marketPrice × 100`,
  `savingsAmount = marketPrice − price` (положительное — экономия).
- `dealScore = clamp(50 − 4/3 × deviation, 0, 100)`: −15 % → 70, 0 % → 50.
- `confidence = min(1, n/10) × вес уровня × согласованность`, где
  согласованность = `max(0.3, 1 − (Q3 − Q1)/(Q3 + Q1))`.
- `isDeal`: отклонение от −40 % до −10 % включительно, `confidence ≥ 0.3`, нет
  признаков копии/блокировки/неисправности. Сильнее −40 % — признак риска,
  а не выгода. Выгода и признаки риска могут совпадать.
- Без цены, с нулевой ценой или без группы цена, отклонение, выгода,
  dealScore и confidence равны null, `sampleSize = 0`.

В выборку рынка не входят: объявления без цены или с ценой 0, другая валюта,
другой dataset, объявления с признаками `replica_mention`, `lock_or_documents`,
`parts_or_damage`. Выбросы цены остаются в выборке — медиана к ним устойчива,
а сами они получают признак риска.

## Признаки риска

| Код | Баллы | Условие |
|---|---|---|
| `price_far_below_market` | 45 | отклонение ≤ −40 % |
| `price_below_market` | 20 | от −40 % до −25 % |
| `price_far_above_market` | 10 | ≥ +60 % |
| `missing_price` | 0 | цена не указана (пояснение, балл не добавляет) |
| `symbolic_price` | 30 | цена 0 |
| `replica_mention` | 30 | «копия», «реплика», «не оригинал» |
| `prepayment_request` | 25 | «предоплата», «перевод на карту» |
| `lock_or_documents` | 25 | «заблокирован», «на iCloud», «без документов» |
| `parts_or_damage` | 15 | «на запчасти», «не включается», «разбит» |
| `urgency_wording` | 10 | «срочно», «только сегодня» |
| `short_description` | 10 | описание есть и короче 20 символов |

`riskScore` — сумма, не больше 100. `riskLevel`: low < 30, medium 30–59,
high ≥ 60; `unknown` и `riskScore = null`, если нет оценки рынка и сумма баллов 0
(например, «Обмен» без цены). Это признаки для проверки, а не вердикт. Текст объявления
используется только детерминированными регулярными выражениями.

`MarketStats` строится по тем же выборкам: mean, median, min, max и гистограмма
из `ceil(√n)` (не больше 10) равных интервалов; последний включает максимум.

## Проверка

```bash
uv run --frozen pytest -q tests/marketlens_analytics
uv run --frozen ruff check app/marketlens/analytics tests/marketlens_analytics
```

40 тестов на фиксированных `fixture-` Listing: определение модели, формула,
малая выборка, запрет сравнения с другими моделями, выброс, копия с предоплатой,
отсутствующая и нулевая цена, смешанные валюты, разделение real/fixture,
повторный расчёт с перемешиванием и дублями, агрегаты, гистограмма, контракт,
CLI.

Остаётся: прогон на живом экспорте. С этой машины OLX отвечает 403 даже на
главную, поэтому `python -m app.marketlens.analytics listings.json` на живой
выборке нужно запустить там, где сбор работает. Чтобы оценка появлялась у
большего числа карточек, сборщику нужно больше одной страницы категории.
