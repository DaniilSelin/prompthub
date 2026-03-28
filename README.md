
# PromptHub

Система версионного контроля промптов на базе SQLite.

## Структура проекта

```
prompthub/
├── facade/
│   ├── storage.py          # Точка входа: Storage, управление промптами
│   ├── prompt.py           # Объект промпта: версии, теги, diff, rollback
│   └── prompt_group.py     # Групповые операции над промптами
│
├── repository/
│   ├── __init__.py         # Константы, схема БД (Fields, SQL)
│   ├── repo.py             # PromptRepo — все SQL-операции
│   ├── queries.py          # DSL запросов: SearchQuery, InsertQuery, ...
│   └── query_factory.py    # Базовый класс для построения запросов
│
├── core/
│   ├── domain/
│   │   ├── operations.py   # Операции diff: Insert, Delete, Replace
│   │   ├── diff.py         # Результаты сравнения версий
│   │   ├── tag.py          # Модель тега
│   │   ├── model_tariff.py # Модель тарифа LLM
│   │   └── prompt_messages.py  # Представление промпта для LLM
│   └── adapters/
│       ├── base.py         # Абстрактный LLMAdapter
│       ├── openai.py       # Адаптер для OpenAI-формата
│       └── registry.py     # Реестр адаптеров
│
├── infrastructure/
│   ├── pricing_gateway.py  # Получение тарифов через HTTP (OpenRouter API)
│   └── tariff_manager.py   # Запись тарифов в БД
│
├── search/
│   └── filters.py          # DSL фильтров: FieldEquals, TagFilter, ...
│
└── main.py                 # Пример использования

tests/
├── unit/                   # Юнит-тесты (filters, queries)
├── integration/            # Интеграционные тесты (Storage, версии)
├── contract/               # Контрактные тесты
├── TEST_PLAN.md
└── Test_cases.md
```