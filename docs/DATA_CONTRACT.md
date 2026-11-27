# Контракт MarketLens v1

Имена JSON camelCase. Отсутствующие данные — null, коллекции без элементов —
[] или {}. Время — RFC 3339 UTC, цена — число в указанных единицах валюты.
Для идентификатора используется `source:externalId`. Один ID принадлежит
одному происхождению данных. Для тестовых ID используйте префикс externalId
`fixture-`. API каталога отдаёт только реальные записи.

```json
{
  "id": "olx:fixture-42",
  "externalId": "fixture-42",
  "source": "olx",
  "dataset": "fixture",
  "url": "https://www.olx.kz/",
  "title": "Учебный смартфон",
  "description": null,
  "category": "electronics",
  "subcategory": "phones",
  "price": 85000,
  "currency": "KZT",
  "city": "Алматы",
  "images": [],
  "attributes": {},
  "condition": "used",
  "publishedAt": null,
  "scrapedAt": "2026-11-27T09:00:00Z",
  "sellerId": null
}
```

Адаптер `ListingParser` объявляет `source` и `collect(request)`, возвращающий
Iterable[Listing]. `CollectionRequest` передаёт category, limit, pages
(по умолчанию 1), необязательные query и city. Для общей выдачи лимит
составляет 3 страницы, для city=ust-kamenogorsk — 12 страниц. Парсер
возвращает только проверяемые нормализованные записи, ограничивает выдачу,
дедуплицирует по ID и сообщает о недоступности источника ошибкой. Оригинальная
ссылка HTTPS принадлежит указанному источнику. sellerId сохраняется только
при публичной доступности и конкретной необходимости.

```json
{
  "listingId": "olx:fixture-42",
  "listingScrapedAt": "2026-11-27T09:00:00Z",
  "computedAt": "2026-11-27T09:05:00Z",
  "algorithmVersion": "v2",
  "comparableGroup": "phones:example:used:almaty:KZT",
  "marketPrice": 100000,
  "priceDeviationPercent": -15,
  "savingsAmount": 15000,
  "dealScore": 70,
  "riskScore": 30,
  "riskLevel": "low",
  "riskReasons": [{"code": "price_gap", "description": "Цена ниже медианы выборки"}],
  "confidence": 0.7,
  "sampleSize": 12,
  "isDeal": true
}
```

Пример расчёта синтетический. Баллы 0–100, confidence 0–1.
riskLevel: unknown | low | medium | high. Положительное savingsAmount означает
экономию. priceDeviationPercent = (price − marketPrice) / marketPrice × 100.
Без положительной базы сравнения поля цены и отклонения остаются null.
Фильтр выгодных использует isDeal, подозрительных — medium/high.
Алинур владеет выбором групп, порогами и формулой; группы разделяют валюту,
категорию и происхождение. При слабой выборке оценки могут отсутствовать.

`listings/{id}` содержит Listing. `listingSnapshots` хранит listingId,
scrapedAt, dataset, price и currency отдельно от исходной карточки.
`analysisResults/{id}` содержит AnalysisResult, связанный с scrapedAt.
API возвращает analysis=null при несовпадении версии снимка или алгоритма. `marketStats` хранит
текущий набор MarketStats в документе _current. Каждый MarketStats содержит dataset, computedAt, comparableGroup, category, currency,
sampleSize, meanPrice, medianPrice, minPrice, maxPrice и histogram
(массив min/max/count). `ingestionRuns` зарезервирована под итог запуска
(source, startedAt, finishedAt, status, collectedCount, uniqueCount).
История — упорядоченные снимки с временем, ценой и валютой.

## HTTP

Префикс /api/v1/market; Firebase Bearer. GET /listings принимает q, category, subcategory,
city, minPrice, maxPrice, source, view=all|deals|risk, sort=default|newest|price_asc|price_desc, limit, offset.
Для сортировки по цене сначала идут объявления с известной ценой в KZT, затем остальные.
По умолчанию deals упорядочен по убыванию dealScore, risk — по убыванию riskScore. Возвращает
{items, nextOffset, scannedCount, scanLimited, total, subcategoryCounts, subcategoryPhotos, latestScrapedAt}; каждый item — {listing, analysis}.
GET /listings/{id} возвращает такой же item.
GET /listings/{id}/history отдаёт {items, truncated}, каждый снимок содержит
scrapedAt, price и currency. По умолчанию 20 последних снимков, от новых к старым.
Параметр limit принимает значения от 1 до 100. GET /stats возвращает
{items, truncated}. POST /listings/{id}/explanation возвращает
{provider, summary, insights, recommendations, limitations}. provider —
local, gemini или openai. Каталог читает все реальные записи пакетами Firestore в порядке document ID.
`offset` применяется после фильтрации и сортировки. subcategoryCounts содержит
размеры подкатегорий для заданных фильтров, кроме самой подкатегории и подборки.
subcategoryPhotos возвращает первое доступное фото в каждой из этих подкатегорий.
latestScrapedAt — время последнего наблюдения среди объявлений, подходящих под те же фильтры.

GET /radar принимает необязательные city и group. Возвращает
{groups, sample, scanLimited}. Группы содержат key и sampleSize. Первая группа
по умолчанию имеет самую большую выборку. Sample содержит key, prices,
histogram, medianPrice и offers (до 24 карточек в порядке цены). В выборку
входят известные положительные цены в KZT для одной модели или варианта.
Можно выбрать как модель целиком, так и вариант с конкретной памятью.
При менее чем пяти ценах medianPrice равна null. Гистограмма и список
известных цен доступны при любом размере выборки.
