# Тест-план проекта PromptHub

## 1. Цель документа
Определить актуальную стратегию проверки всех вариантов использования (ВИ-1 ... ВИ-17) для текущей реализации библиотеки и зафиксировать незакрытые шаги тестирования.

## 2. Объект тестирования
Проект: библиотека хранения и версионирования промптов на SQLite.

Ключевые подсистемы:
- Инициализация хранилища и схема БД.
- CRUD промптов.
- Версионирование (snapshot + delta).
- Тегирование и модельные теги.
- Поиск и фильтрация.
- Получение промпта для использования.
- Обновление тарифов моделей.

## 3. Источник  поведения
Приоритет интерпретации поведения:
1. Код публичного API: Storage и Prompt.
2. Интеграционные и контрактные тесты.
3. Требования.

Основные API текущей реализации:
- Storage: create_prompt, get_prompt, fetch_prompt, delete_prompt, list_prompts, list_all_tags, search_by_tags, update_tariffs, add_model_tags, remove_model_tags.
- Prompt: add_version, rollback, list_versions, get_version_content, add_prompt_tag, remove_prompt_tag, add_model_tag, remove_model_tag, compare_versions_structured.

## 4. Тестовая стратегия
Уровни тестирования:
- Unit: DSL фильтров, query builder, токенизаторы, gateway тарифов, адаптеры.
- Integration: facade -> repository -> SQLite.
- Contract: фиксация обязательного поведения публичных методов.
- Regression: повторный прогон критичного набора после изменений.

Типы проверок:
- Позитивные сценарии.
- Негативные сценарии (валидация, отсутствующие сущности).
- Граничные сценарии (пустые данные, дубликаты, неизвестные тарифы/провайдеры).
- Конкурентный доступ для add_version.

## 5. Критерии входа и выхода
Критерии входа:
- Актуальная схема БД.
- Доступен запуск pytest из корня проекта.

Критерии выхода:
- Документация по ВИ синхронизирована с текущим кодом.
- Для каждого ВИ указан статус покрытия: Полное/Частичное/Нет покрытия.
- Выполнен полный прогон тестов и проведена проверка корректности результатов.

## 6. Матрица покрытия ВИ 

| ВИ | Сценарий | Текущее API | Автотесты | Статус покрытия | Незакрытые шаги |
| --- | --- | --- | --- | --- | --- |
| ВИ-1 | Инициализировать хранилище | Storage(path) | integration: test_uc01_001..004 | Полное | Опционально: отдельный smoke на реальные FS-права без monkeypatch. |
| ВИ-2 | Создать промпт | Storage.create_prompt | integration: test_uc02_001..005; contract: test_uc02_002 | Полное | Опционально: расширить набор невалидных форматов messages. |
| ВИ-3 | Изменить промпт | Prompt.add_version | integration: test_uc03_001, test_uc03_003, test_uc03_005; unit: test_uc03_002; contract: test_uc03_004 | Полное | Опционально: stress-кейс на очень длинный content. |
| ВИ-4 | Удалить промпт | Storage.delete_prompt | integration: test_uc04_001, test_uc04_002; contract: test_uc13_003, test_uc13_004 | Полное | Нет обязательных незакрытых шагов. |
| ВИ-5 | Просмотреть список всех промптов | Storage.list_prompts | contract: test_uc05_001, test_uc05_002; integration: test_costs.py, test_storage_facade.py | Полное | Нет обязательных незакрытых шагов. |
| ВИ-6 | Просмотреть историю версий | Prompt.list_versions | contract: test_uc06_001, test_uc06_003; integration: test_uc06_002 | Полное | Нет обязательных незакрытых шагов. |
| ВИ-7 | Сравнить версии | Prompt.compare_versions_structured | integration: test_uc07_002..006; unit: test_uc07_003; contract: test_uc07_002_compare_versions_returns_structured_diff | Полное | Нет обязательных незакрытых шагов. |
| ВИ-8 | Восстановить из версии | Prompt.rollback | contract: test_uc08_001, test_uc08_002; integration: test_uc08_003..006 | Полное | Нет обязательных незакрытых шагов. |
| ВИ-9 | Добавить тег к промпту | Prompt.add_prompt_tag | integration: test_uc09_001, test_uc09_002 | Полное | Нет обязательных незакрытых шагов. |
| ВИ-10 | Удалить тег с промпта | Prompt.remove_prompt_tag | integration: test_uc10_001, test_uc10_002 | Полное | Нет обязательных незакрытых шагов. |
| ВИ-11 | Добавить model tag | Storage.add_model_tags | integration: test_uc11_001..003 + test_costs.py | Полное | Нет обязательных незакрытых шагов. |
| ВИ-12 | Удалить model tag | Storage.remove_model_tags | integration: test_uc12_001, test_uc12_002 | Полное | Нет обязательных незакрытых шагов. |
| ВИ-13 | Просмотреть все теги | Storage.list_all_tags | integration: test_uc13_001, test_uc13_002 | Полное | Нет обязательных незакрытых шагов. |
| ВИ-14 | Найти промпты по тегам | Storage.search_by_tags; PromptGroup.with_tag/without_tag | integration: test_uc14_001..003; unit: filters + queries_condition/base | Полное | Нет обязательных незакрытых шагов. |
| ВИ-15 | Найти промпт по названию | Storage.get_prompt | integration: test_uc15_001 (косвенно), test_uc15_002 | Частичное | Soft-поиск metadata/None отсутствует в текущем API (требует отдельного метода). |
| ВИ-16 | Получить промпт для использования | Storage.fetch_prompt | contract: test_uc16_004; integration: test_uc16_001..008 | Полное | Нет обязательных незакрытых шагов. |
| ВИ-17 | Обновить тарифы моделей | Storage.update_tariffs | unit: test_pricing_gateway.py; integration: test_uc17_001..004 | Полное | Нет обязательных незакрытых шагов. |

## 7. Набор проверок по каждому ВИ

### ВИ-1. Инициализация хранилища
Проверки:
- Создание новой БД при отсутствии файла.
- Создание таблиц и индексов.
- PRAGMA journal_mode=WAL и PRAGMA foreign_keys=ON на connection Storage.
- Повторная инициализация без потери данных.
- Ошибка открытия БД (через monkeypatch sqlite3.connect).

### ВИ-2. Создание промпта
Проверки:
- Успешное создание prompt и первой версии (через messages или add_version).
- Уникальность имени (KeyError).
- Атомарность create_prompt при сбое add_version.
- Метаданные prompt (created_at).

### ВИ-3. Изменение промпта
Проверки:
- Инкремент seq и связь parent_version_id.
- Построение changeset insert/delete/replace.
- Snapshot каждые N версий.
- Отсутствие новой версии при идентичном content.
- Конкурентная запись: уникальные seq без коллизий.

### ВИ-4. Удаление промпта
Проверки:
- Каскадное удаление prompt_versions и prompt_tags после удаления prompt.
- Поведение Storage.delete_prompt для несуществующего имени (KeyError).

### ВИ-5. Список всех промптов с ценой
Проверки:
- Базовый список prompt с metadata.
- Перемодельный token_count и cost.
- Отсутствие тарифа -> cost=None и warning.
- Отсутствие токенизатора -> fallback token_count=0 и warning.
- Prompt без model_tags -> model_tags=None и costs=None.

### ВИ-6. История версий
Проверки:
- Возврат списка версий по возрастанию seq.
- Корректность полей version rows.
- Поведение для prompt без версий.

### ВИ-7. Сравнение версий
Проверки:
- changed/added/deleted сценарии compare_versions_structured.
- Идентичные версии -> пустой diff + warning.
- Ошибка для несуществующей версии.

### ВИ-8. Восстановление версии
Проверки:
- rollback(target_seq) создает новую версию с целевым content.
- rollback(steps_back) создает новую версию.
- Некорректный steps_back -> ValueError.
- Отсутствующие/невалидные параметры rollback.

### ВИ-9. Добавление prompt-тега
Проверки:
- Успешное добавление нового тега.
- Повторное добавление -> warning, без дубликатов.

### ВИ-10. Удаление prompt-тега
Проверки:
- Удаление существующей связи.
- Удаление отсутствующей связи -> warning и отсутствие изменений.

### ВИ-11. Добавление model-тегов
Проверки:
- Успешная привязка валидных model_tags.
- duplicate model_tag -> warning.
- model_tag без тарифа -> warning, тег не добавляется.
- Возврат списка фактически добавленных тегов.

### ВИ-12. Удаление model-тегов
Проверки:
- Удаление существующих model_tags.
- Отсутствующий model_tag -> warning, без ошибки.
- Возврат списка фактически удаленных тегов.

### ВИ-13. Просмотр всех тегов
Проверки:
- Возврат всех тегов с полями name/type/provider.
- Пустой список при отсутствии тегов.
- Порядок сортировки type -> name.

### ВИ-14. Поиск по тегам
Проверки:
- Search по Condition (TagFilter, AND/OR/NOT) через Storage.search_by_tags.
- Фильтрация prompt-группы через with_tag/without_tag.
- Пустой результат без ошибок.

### ВИ-15. Поиск по имени
Проверки:
- get_prompt для существующего имени.
- KeyError для отсутствующего имени.
- Фиксация, что soft-поиск metadata/None отсутствует в текущем API.

### ВИ-16. Получение промпта для использования
Проверки:
- fetch_prompt(name) для актуальной версии.
- fetch_prompt(name, version=seq) для конкретной версии.
- Ошибки: KeyError (name), ValueError (version not found), TypeError (не-int version).
- Реконструкция snapshot + chain delta.

### ВИ-17. Обновление тарифов
Проверки:
- Успешный update_tariffs c upsert.
- Недоступность источника -> ConnectionError.
- Невалидный ответ -> ValueError.
- Ошибка записи в БД -> RuntimeError.

## 8. Минимальный обязательный регрессионный набор
- Инициализация: tests/integration/test_storage_init.py.
- CRUD/versioning: tests/integration/test_prompt_crud.py и tests/integration/test_versions.py.
- Facade API (tags/search/fetch/tariffs/delete): tests/integration/test_storage_facade.py.
- Diff: tests/integration/test_compare_versions.py.
- Costs/model tags: tests/integration/test_costs.py.
- Ключевые контракты: tests/contract/test_spec_gaps.py и tests/contract/test_prompt_info.py.

## 9. Полный прогон тестов
Запуск из корня проекта:

```bash
PYTHONPATH=. pytest tests/unit tests/integration tests/contract -q
```

Для PowerShell:

```powershell
$env:PYTHONPATH='.'; pytest tests/unit tests/integration tests/contract -q
```

## 10. Проверка корректности результатов прогона
Проверяем:
1. Нет неожиданных failed/error и ошибок коллекции.
2. Нет инфраструктурных сбоев окружения.
3. Фактические проблемы сопоставлены с матрицей ВИ -> проверки.
4. Все найденные разрывы добавлены в блок незакрытых шагов.

## 11. Дефекты и отчетность
Для каждого дефекта фиксировать:
- Идентификатор ВИ.
- Шаги воспроизведения.
- Фактический результат.
- Ожидаемый результат.
- Severity/Priority.
- Версию кода/коммита.