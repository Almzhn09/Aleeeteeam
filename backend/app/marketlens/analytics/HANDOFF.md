# Аналитика готова · заметка для команды

От Алинура (`feat/analytics`). Подробности: [README модуля](README.md).

## Артуру — подключение одной строкой

```python
from app.marketlens.analytics import analyze_store

summary = analyze_store(MarketStore(runtime.db()))
# {"listings": N, "scanLimited": bool, "savedResults": N, "savedStats": N}
```

Удобное место — конец `import_listings.main()` после сохранения карточек:
тогда каталог сразу получает `analysis`, а дашборд — `marketStats`.
Используются только публичные методы `MarketStore`, контракт и схема не менялись.
Для проверки версии в API есть `ALGORITHM_VERSION` (`"v1"`).

Группы: `electronics/phones:<модель>[:<память>]:<состояние>:<валюта>`; на дашборде
всегда есть обзор категории `electronics/phones:all:any:KZT`.

## Алиму — OLX 403

27.11.2026 `collect_olx --authorized` вернул HTTP 403 и с локальной машины
(не только из облачного прокси). Похоже, OLX блокирует сам клиент, а не сеть.
Обход User-Agent'ом не делали — нужен разрешённый способ доступа. Как только
будет живой `listings.json`, прогоните:

```bash
uv run --frozen python -m app.marketlens.analytics listings.json > analysis.json
```

и пришлите результат — по нему подстроим распознавание моделей и порог группы.
