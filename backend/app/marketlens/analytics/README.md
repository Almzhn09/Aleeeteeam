# Аналитика MarketLens (`feat/analytics`)

Детерминированный расчёт без сети, Firestore и AI. Один и тот же набор Listing
и один и тот же `computed_at` дают одинаковый результат при любом порядке входа.

## Точка вызова

```python
from app.marketlens.analytics import ALGORITHM_VERSION, analyze

analysis = analyze(listings, computed_at=datetime.now(UTC))
analysis.results  # list[AnalysisResult] — по одному на каждый уникальный listing.id
analysis.stats  # list[MarketStats] — группы, использованные в оценке, и обзор категории
```

- Вход: любые `Listing` по контракту v1. Повторы одного ID сворачиваются
  до последнего `scrapedAt`; `listingScrapedAt` в результате указывает именно его.
- `computed_at` обязателен и должен содержать часовой пояс.
- `algorithmVersion` = `ALGORITHM_VERSION` (`"v1"`). При смене формулы версия
  поднимается — API может сравнить версию и вернуть `analysis=null`.
- Сохранение: `MarketStore.save_analysis(result)` и `save_stats(stats)` из core
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
"stats": [MarketStats]}` в camelCase. Firestore не используется.

## Группы сравнения

Группа всегда разделяет `dataset`, категорию/подкатегорию, состояние
(`condition` или `any`) и валюту. Внутри категории модель определяется по
заголовку (латиница и кириллица: «айфон», «самсунг», «редми ноут», «гб»).
Уровни от точного к общему:

| Уровень | Пример `comparableGroup` | Вес доверия |
|---|---|---|
| variant | `electronics/phones:apple-iphone-13:128gb:any:KZT` | 1.0 |
| model | `electronics/phones:apple-iphone-13:any:KZT` | 0.9 |
| brand | `electronics/phones:apple:any:KZT` | 0.6 |
| category | `electronics/phones:all:any:KZT` | 0.4 |

Выбирается первый уровень, где есть не меньше 5 других объявлений с ценой
(`MIN_PEERS`). Город в группу не входит: на одной странице OLX выборка по городу
слишком мала. Если подходящего уровня нет, оценка не выставляется.

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
| `missing_price` | 20 | цена не указана |
| `symbolic_price` | 30 | цена 0 |
| `replica_mention` | 30 | «копия», «реплика», «не оригинал» |
| `prepayment_request` | 25 | «предоплата», «перевод на карту» |
| `lock_or_documents` | 25 | «заблокирован», «на iCloud», «без документов» |
| `parts_or_damage` | 15 | «на запчасти», «не включается», «разбит» |
| `urgency_wording` | 10 | «срочно», «только сегодня» |
| `short_description` | 10 | описание есть и короче 20 символов |

`riskScore` — сумма, не больше 100. `riskLevel`: low < 30, medium 30–59,
high ≥ 60; `unknown` и `riskScore = null`, если нет ни оценки рынка, ни одного
признака. Это признаки для проверки, а не вердикт. Текст объявления
используется только детерминированными регулярными выражениями.

`MarketStats` строится по тем же выборкам: mean, median, min, max и гистограмма
из `ceil(√n)` (не больше 10) равных интервалов; последний включает максимум.

## Проверка

```bash
uv run --frozen pytest -q tests/marketlens_analytics
uv run --frozen ruff check app/marketlens/analytics tests/marketlens_analytics
```

31 тест на фиксированных `fixture-` Listing: определение модели, формула,
малая выборка, переход к более общей группе, выброс, копия с предоплатой,
отсутствующая и нулевая цена, смешанные валюты, разделение real/fixture,
повторный расчёт с перемешиванием и дублями, агрегаты, гистограмма, контракт,
CLI.

Остаётся: прогон на живом экспорте OLX. 27.11.2026 `collect_olx --authorized` с
локальной машины получил HTTP 403, как и из облака; нужен разрешённый доступ к
источнику. Затем проверить долю заголовков, где модель распознана, и подобрать
`MIN_PEERS` под реальный размер страницы. Вызов `analyze` после импорта и
сохранение в Firestore — в зоне core.
