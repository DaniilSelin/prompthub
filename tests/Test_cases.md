# Детализированные test cases

## Формат кейса
- ID: уникальный идентификатор теста.
- Тип: unit/integration/contract.
- Приоритет: High/Medium/Low.
- Статус: Implemented / Partial / Planned.
- Предусловия: начальное состояние.
- Шаги: действия для выполнения.
- Ожидаемый результат: проверяемый итог.
- Трассировка: фактический автотест (если есть).

## ВИ-1. Инициализировать хранилище

### TC-UC01-001: Создание новой БД, схемы и PRAGMA
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: путь к новому файлу БД.
- Шаги:
1. Создать Storage с новым db_path.
2. Проверить наличие таблиц и индексов.
3. Проверить PRAGMA journal_mode и foreign_keys на storage._conn.
- Ожидаемый результат: схема создана; WAL и foreign_keys включены.
- Трассировка: tests/integration/test_storage_init.py::test_uc01_001_creates_new_db_schema_and_configures_pragmas

### TC-UC01-002: Повторная инициализация без потери данных
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: существующая БД с prompt и версией.
- Шаги:
1. Инициализировать Storage.
2. Проверить существующий prompt и content.
3. Переинициализировать Storage на том же пути.
4. Повторно проверить prompt и versions.
- Ожидаемый результат: данные сохранены.
- Трассировка: tests/integration/test_storage_init.py::test_uc01_002_reinitialization_preserves_existing_data

### TC-UC01-003: Ошибка открытия БД
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: monkeypatch sqlite3.connect на OperationalError.
- Шаги:
1. Подменить sqlite3.connect.
2. Создать Storage.
- Ожидаемый результат: RuntimeError об ошибке открытия БД.
- Трассировка: tests/integration/test_storage_init.py::test_uc01_003_raises_error_when_db_path_is_unavailable

### TC-UC01-004: Существующий файл не является SQLite БД
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: путь к существующему файлу с не-SQLite содержимым.
- Шаги:
1. Создать файл с невалидным содержимым.
2. Инициализировать Storage по этому пути.
- Ожидаемый результат: RuntimeError о невалидной SQLite БД.
- Трассировка: tests/integration/test_storage_init.py::test_uc01_004_raises_error_for_invalid_existing_sqlite_file

## ВИ-2. Создать промпт

### TC-UC02-001: Создание prompt и первой версии
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: пустое хранилище.
- Шаги:
1. Вызвать create_prompt(name).
2. Вызвать prompt.add_version(content).
3. Проверить list_versions.
- Ожидаемый результат: версия seq=1 создана, snapshot_content заполнен.
- Трассировка: tests/integration/test_prompt_crud.py::test_uc02_001_creates_prompt_and_first_version

### TC-UC02-002: Уникальность имени prompt
- Тип: contract
- Приоритет: High
- Статус: Implemented
- Предусловия: prompt с именем X уже создан.
- Шаги:
1. Повторно вызвать create_prompt(X).
- Ожидаемый результат: KeyError.
- Трассировка: tests/contract/test_spec_gaps.py::test_uc02_002_requires_unique_prompt_name

### TC-UC02-003: Метаданные prompt
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: пустое хранилище.
- Шаги:
1. Создать prompt.
2. Прочитать repo.get_prompt_by_name(name).
- Ожидаемый результат: created_at заполнен.
- Трассировка: tests/integration/test_prompt_crud.py::test_uc02_003_prompt_metadata_created_at_is_stored

### TC-UC02-004: Атомарность create_prompt с messages
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: подменить Prompt.add_version на исключение.
- Шаги:
1. Вызвать create_prompt(name, messages=[...]).
2. Проверить отсутствие prompt в БД.
- Ожидаемый результат: транзакция откатилась.
- Трассировка: tests/integration/test_prompt_crud.py::test_uc02_004_create_prompt_rolls_back_on_initial_version_failure

### TC-UC02-005: Валидация невалидного messages при create_prompt
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: пустое хранилище.
- Шаги:
1. Вызвать create_prompt(name, messages=[]).
2. Вызвать create_prompt с сообщением без role/content.
- Ожидаемый результат: ValueError; prompt не создан.
- Трассировка: tests/integration/test_prompt_crud.py::test_uc02_005_create_prompt_rejects_invalid_messages_and_rolls_back

## ВИ-3. Изменить промпт

### TC-UC03-001: Новая версия, seq и parent_version_id
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: prompt с первой версией.
- Шаги:
1. Добавить вторую версию.
2. Проверить seq и parent_version_id.
- Ожидаемый результат: seq увеличен на 1, parent_version_id указывает на предыдущую версию.
- Трассировка: tests/integration/test_prompt_crud.py::test_uc03_001_adds_new_version_increments_seq_and_sets_parent

### TC-UC03-002: Корректный changeset insert/delete/replace
- Тип: unit
- Приоритет: High
- Статус: Implemented
- Предусловия: экземпляр Prompt.
- Шаги:
1. Вызвать _build_changeset для insert/delete/replace.
- Ожидаемый результат: операции и индексы корректны.
- Трассировка: tests/unit/test_filters.py::test_uc03_002_build_changeset_produces_insert_delete_replace_with_indices

### TC-UC03-003: Snapshot на snapshot_interval
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt, snapshot_interval=5.
- Шаги:
1. Добавить 5 версий.
2. Проверить snapshot_content у версий 1 и 5.
- Ожидаемый результат: snapshot у seq=1 и seq=5.
- Трассировка: tests/integration/test_prompt_crud.py::test_uc03_003_stores_snapshot_every_snapshot_interval

### TC-UC03-004: add_version без изменений
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt с текущим content.
- Шаги:
1. Повторно вызвать add_version с тем же content.
2. Сверить count версий до/после.
- Ожидаемый результат: новая версия не создается, возвращается id текущей.
- Трассировка: tests/contract/test_spec_gaps.py::test_uc03_004_update_with_identical_content_does_not_create_new_version

### TC-UC03-005: Конкурентный add_version
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: file-based SQLite, несколько потоков.
- Шаги:
1. Параллельно добавить версии из нескольких Storage.
2. Проверить уникальность seq и непрерывность диапазона.
- Ожидаемый результат: нет коллизий seq.
- Трассировка: tests/integration/test_versions.py::test_uc03_005_concurrent_add_version_keeps_unique_seq

## ВИ-4. Удалить промпт

### TC-UC04-001: Каскадное удаление prompt и связанных сущностей
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: prompt с версиями и тегами.
- Шаги:
1. Удалить prompt.
2. Проверить удаление prompt_versions и prompt_tags.
- Ожидаемый результат: связанные записи удалены каскадно.
- Трассировка: tests/integration/test_storage_facade.py::test_uc04_001_delete_prompt_removes_prompt_versions_and_links; tests/contract/test_deletion_contract.py::test_uc13_004_delete_prompt_cleans_versions_metadata

### TC-UC04-002: Storage.delete_prompt для отсутствующего имени
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt с именем отсутствует.
- Шаги:
1. Вызвать storage.delete_prompt(name).
- Ожидаемый результат: KeyError.
- Трассировка: tests/integration/test_storage_facade.py::test_uc04_002_delete_prompt_missing_raises_key_error

## ВИ-5. Просмотреть список всех промптов

### TC-UC05-001: Базовый список prompt
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: в БД есть prompts.
- Шаги:
1. Вызвать list_prompts.
2. Проверить базовые поля metadata.
- Ожидаемый результат: список prompt возвращен.
- Трассировка: tests/contract/test_prompt_info.py::test_uc05_001_list_all_prompts_with_metadata

### TC-UC05-002: Перемодельный token_count и cost
- Тип: contract
- Приоритет: High
- Статус: Implemented
- Предусловия: есть тарифы и model_tag.
- Шаги:
1. Привязать model_tag.
2. Вызвать list_prompts.
3. Проверить token_count и cost.
- Ожидаемый результат: для модели есть token_count>0 и cost>0.
- Трассировка: tests/contract/test_prompt_info.py::test_uc05_002_list_prompts_includes_per_model_token_count_and_cost

### TC-UC05-003: Отсутствующий тариф
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: model_tag привязан, тариф удален.
- Шаги:
1. Вызвать list_prompts.
- Ожидаемый результат: token_count есть, cost=None, warning.
- Трассировка: tests/integration/test_costs.py::test_missing_tariff_gives_none_cost_but_has_token_count

### TC-UC05-004: Отсутствующий токенизатор
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: модель с неизвестным provider.
- Шаги:
1. Вызвать list_prompts.
- Ожидаемый результат: fallback token_count=0 и warning.
- Трассировка: tests/integration/test_costs.py::test_missing_tokenizer_falls_back_to_word_count

### TC-UC05-005: list_prompts в пустом хранилище
- Тип: integration
- Приоритет: Low
- Статус: Implemented
- Предусловия: в БД нет prompt.
- Шаги:
1. Вызвать list_prompts.
- Ожидаемый результат: возвращается [].
- Трассировка: tests/integration/test_storage_facade.py::test_uc05_005_list_prompts_returns_empty_list_for_empty_storage

## ВИ-6. Просмотреть историю версий

### TC-UC06-001: История версий по seq ASC
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt с двумя версиями.
- Шаги:
1. Вызвать list_versions.
2. Проверить порядок seq.
- Ожидаемый результат: seq возрастает.
- Трассировка: tests/contract/test_prompt_info.py::test_uc06_001_version_history_order_and_fields

### TC-UC06-002: История для prompt без версий
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt создан, версий нет.
- Шаги:
1. Вызвать list_versions.
- Ожидаемый результат: пустой список.
- Трассировка: tests/integration/test_storage_facade.py::test_uc06_002_list_versions_returns_empty_for_prompt_without_versions

### TC-UC06-003: Проверка состава полей истории
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt с несколькими версиями.
- Шаги:
1. Вызвать list_versions.
2. Проверить поля seq/name/message/created_at/is_snapshot.
- Ожидаемый результат: поля соответствуют API PromptVersion.
- Трассировка: tests/contract/test_prompt_info.py::test_uc06_003_list_versions_exposes_expected_fields

## ВИ-7. Сравнить версии промпта

### TC-UC07-001: Сохранение changeset в БД
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt с двумя версиями.
- Шаги:
1. Добавить вторую версию с изменением.
2. Проверить prompt_changes.
- Ожидаемый результат: изменения сохранены.
- Трассировка: tests/contract/test_prompt_info.py::test_uc07_001_changeset_storage_integrity

### TC-UC07-002: compare_versions_structured измененный content
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: prompt с версиями 1 и 2.
- Шаги:
1. Вызвать compare_versions_structured(1,2).
- Ожидаемый результат: has_changes=True, changed заполнен.
- Трассировка: tests/integration/test_compare_versions.py::test_uc07_002_compare_versions_structured_shows_changed_message

### TC-UC07-003: compare_versions_structured идентичные версии
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt с одной версией.
- Шаги:
1. Вызвать compare_versions_structured(1,1).
- Ожидаемый результат: пустой diff.
- Трассировка: tests/integration/test_compare_versions.py::test_uc07_003_compare_versions_structured_identical_has_no_changes; tests/unit/test_filters.py::test_uc07_003_changeset_operations_transform_old_into_new

### TC-UC07-004: Added/deleted сообщения
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: пары версий с добавлением/удалением сообщений.
- Шаги:
1. Сравнить версии.
2. Проверить added/deleted.
- Ожидаемый результат: корректная структурная классификация изменений.
- Трассировка: tests/integration/test_compare_versions.py::test_uc07_004_compare_versions_structured_detects_added_message; tests/integration/test_compare_versions.py::test_uc07_005_compare_versions_structured_detects_deleted_message

### TC-UC07-005: Ошибка для несуществующей версии
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: существует только версия 1.
- Шаги:
1. Вызвать compare_versions_structured с несуществующим seq.
- Ожидаемый результат: ValueError("version not found").
- Трассировка: tests/integration/test_compare_versions.py::test_uc07_006_compare_versions_structured_raises_for_unknown_version

## ВИ-8. Восстановить промпт из предыдущей версии

### TC-UC08-001: rollback по target_seq
- Тип: contract
- Приоритет: High
- Статус: Implemented
- Предусловия: есть seq 1..3.
- Шаги:
1. Вызвать rollback(target_seq=1).
2. Проверить новую версию и сохранение истории.
- Ожидаемый результат: добавлена новая версия с content seq=1.
- Трассировка: tests/contract/test_spec_gaps.py::test_uc08_001_rollback_by_version_name_creates_new_version_without_losing_history

### TC-UC08-002: rollback по steps_back
- Тип: contract
- Приоритет: High
- Статус: Implemented
- Предусловия: есть seq 1..4.
- Шаги:
1. Вызвать rollback(steps_back=2).
- Ожидаемый результат: добавлена новая версия с target content.
- Трассировка: tests/contract/test_spec_gaps.py::test_uc08_002_rollback_by_steps_creates_new_version_without_losing_history

### TC-UC08-003: Некорректный steps_back
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: есть 2 версии.
- Шаги:
1. Вызвать rollback(steps_back=999) и rollback(steps_back=-1).
- Ожидаемый результат: ValueError.
- Трассировка: tests/integration/test_versions.py::test_uc08_003_rollback_with_invalid_steps_back_raises_value_error

### TC-UC08-004: Несуществующий target_seq
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: есть версии 1..N.
- Шаги:
1. Вызвать rollback(target_seq=999).
- Ожидаемый результат: ValueError.
- Трассировка: tests/integration/test_versions.py::test_uc08_004_rollback_with_unknown_target_seq_raises_value_error

### TC-UC08-005: rollback без параметров
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: есть версии.
- Шаги:
1. Вызвать rollback() без target_seq/steps_back.
- Ожидаемый результат: ValueError.
- Трассировка: tests/integration/test_versions.py::test_uc08_005_rollback_without_params_raises_value_error

### TC-UC08-006: rollback при отсутствии версий
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt создан, но версий нет.
- Шаги:
1. Вызвать rollback(target_seq=1).
- Ожидаемый результат: ValueError.
- Трассировка: tests/integration/test_versions.py::test_uc08_006_rollback_without_versions_raises_value_error

## ВИ-9. Добавить тег к промпту

### TC-UC09-001: Добавление нового prompt-тега
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt без тега.
- Шаги:
1. Вызвать prompt.add_prompt_tag("tag").
2. Проверить связь в prompt_tags.
- Ожидаемый результат: связь создана.
- Трассировка: tests/integration/test_storage_facade.py::test_uc09_001_add_prompt_tag_creates_link

### TC-UC09-002: Повторное добавление prompt-тега
- Тип: integration
- Приоритет: Low
- Статус: Implemented
- Предусловия: тег уже привязан.
- Шаги:
1. Повторно вызвать add_prompt_tag.
- Ожидаемый результат: warning, без дубликата.
- Трассировка: tests/integration/test_storage_facade.py::test_uc09_002_add_prompt_tag_duplicate_warns_and_is_idempotent

## ВИ-10. Удалить тег с промпта

### TC-UC10-001: Удаление существующего prompt-тега
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: связь prompt-tag существует.
- Шаги:
1. Вызвать prompt.remove_prompt_tag("tag").
2. Проверить отсутствие связи.
- Ожидаемый результат: связь удалена.
- Трассировка: tests/integration/test_storage_facade.py::test_uc10_001_remove_prompt_tag_deletes_existing_link

### TC-UC10-002: Удаление отсутствующего prompt-тега
- Тип: integration
- Приоритет: Low
- Статус: Implemented
- Предусловия: связь отсутствует.
- Шаги:
1. Вызвать remove_prompt_tag.
- Ожидаемый результат: warning, без исключения.
- Трассировка: tests/integration/test_storage_facade.py::test_uc10_002_remove_prompt_tag_missing_warns

## ВИ-11. Добавить model_tag

### TC-UC11-001: Добавление model_tag с тарифом
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: есть тариф модели.
- Шаги:
1. Вызвать storage.add_model_tags(name,[model]).
2. Проверить связь и возврат добавленного тега.
- Ожидаемый результат: тег добавлен.
- Трассировка: tests/integration/test_storage_facade.py::test_uc11_002_add_model_tags_duplicate_warns_and_returns_only_new

### TC-UC11-002: Duplicate model_tag
- Тип: integration
- Приоритет: Low
- Статус: Implemented
- Предусловия: model_tag уже привязан.
- Шаги:
1. Повторно вызвать add_model_tags.
- Ожидаемый результат: warning, без дубликата.
- Трассировка: tests/integration/test_storage_facade.py::test_uc11_002_add_model_tags_duplicate_warns_and_returns_only_new

### TC-UC11-003: model_tag без тарифа
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: тариф отсутствует.
- Шаги:
1. Вызвать add_model_tags с неизвестной моделью.
- Ожидаемый результат: warning, тег пропущен, список добавленных пуст.
- Трассировка: tests/integration/test_storage_facade.py::test_uc11_003_add_model_tags_without_tariff_warns_and_skips

## ВИ-12. Удалить model_tag

### TC-UC12-001: Удаление существующего model_tag
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: model_tag привязан.
- Шаги:
1. Вызвать storage.remove_model_tags(name,[model]).
- Ожидаемый результат: тег удален, возвращен в списке удаленных.
- Трассировка: tests/integration/test_storage_facade.py::test_uc12_001_remove_model_tags_removes_existing_links

### TC-UC12-002: Удаление отсутствующего model_tag
- Тип: integration
- Приоритет: Low
- Статус: Implemented
- Предусловия: model_tag не привязан.
- Шаги:
1. Вызвать remove_model_tags.
- Ожидаемый результат: warning, список удаленных пуст.
- Трассировка: tests/integration/test_storage_facade.py::test_uc12_002_remove_model_tags_missing_warns_and_returns_empty

## ВИ-13. Просмотреть все теги

### TC-UC13-001: list_all_tags для заполненного справочника
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: есть prompt/model теги.
- Шаги:
1. Вызвать storage.list_all_tags().
- Ожидаемый результат: возвращены name/type/provider, сортировка type->name.
- Трассировка: tests/integration/test_storage_facade.py::test_uc13_001_list_all_tags_returns_sorted_rows

### TC-UC13-002: list_all_tags для пустого справочника
- Тип: integration
- Приоритет: Low
- Статус: Implemented
- Предусловия: тегов нет.
- Шаги:
1. Вызвать list_all_tags.
- Ожидаемый результат: пустой список.
- Трассировка: tests/integration/test_storage_facade.py::test_uc13_002_list_all_tags_empty_returns_empty_list

## ВИ-14. Найти и вернуть промпты по тегу

### TC-UC14-001: Поиск через Storage.search_by_tags(TagFilter)
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: несколько prompt с разными тегами.
- Шаги:
1. Сформировать Condition.
2. Вызвать storage.search_by_tags(condition).
- Ожидаемый результат: возвращены только matching prompts.
- Трассировка: tests/integration/test_storage_facade.py::test_uc14_001_search_by_tags_with_tagfilter

### TC-UC14-002: Поиск с NOT/AND/OR комбинациями
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: данные для булевой фильтрации.
- Шаги:
1. Сформировать комбинированный Filter.
2. Вызвать search_by_tags.
- Ожидаемый результат: корректная выборка по булевому выражению.
- Трассировка: tests/integration/test_storage_facade.py::test_uc14_002_search_by_tags_supports_boolean_composition

### TC-UC14-003: PromptGroup with_tag/without_tag
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt-группа с тегами.
- Шаги:
1. Вызвать make_group_prompt().with_tag(...)/without_tag(...).
2. Выполнить search_versions.
- Ожидаемый результат: корректная фильтрация версий.
- Трассировка: tests/integration/test_storage_facade.py::test_uc14_003_prompt_group_with_tag_and_without_tag

## ВИ-15. Найти промпт по названию

### TC-UC15-001: get_prompt для существующего имени
- Тип: integration
- Приоритет: Medium
- Статус: Partial
- Предусловия: prompt существует.
- Шаги:
1. Вызвать storage.get_prompt(name).
- Ожидаемый результат: возвращен Prompt.
- Трассировка: косвенно в tests/integration/test_storage_init.py и других integration тестах

### TC-UC15-002: get_prompt для отсутствующего имени
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt отсутствует.
- Шаги:
1. Вызвать get_prompt(name).
- Ожидаемый результат: KeyError.
- Трассировка: tests/integration/test_storage_facade.py::test_uc15_002_get_prompt_missing_raises_key_error

### TC-UC15-003: Soft-поиск metadata/None
- Тип: contract
- Приоритет: Low
- Статус: Planned
- Предусловия: требуется поддержка soft-режима из требований.
- Шаги:
1. Вызвать soft-поиск по имени.
- Ожидаемый результат: metadata или None.
- Трассировка: отсутствует (метод не реализован в текущем API)

## ВИ-16. Получить промпт для использования

### TC-UC16-001: fetch_prompt без версии
- Тип: contract
- Приоритет: High
- Статус: Implemented
- Предусловия: prompt с версией.
- Шаги:
1. Вызвать storage.fetch_prompt(name).
- Ожидаемый результат: PromptMessages для актуальной версии.
- Трассировка: tests/contract/test_spec_gaps.py::test_uc16_004_fetch_prompt_returns_prompt_messages

### TC-UC16-002: Реконструкция snapshot + chain delta
- Тип: integration
- Приоритет: High
- Статус: Implemented
- Предусловия: history >= 7 версий.
- Шаги:
1. Запросить промежуточные и последние версии.
2. Сверить content с эталоном.
- Ожидаемый результат: корректная реконструкция.
- Трассировка: tests/integration/test_versions.py::test_uc16_002_reconstructs_content_from_snapshot_and_delta_chain; tests/integration/test_versions.py::test_uc16_007_reconstructs_version_with_multi_operation_changeset

### TC-UC16-003: Ошибка для несуществующей версии
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: версия отсутствует.
- Шаги:
1. Вызвать get_version_content(unknown_seq).
- Ожидаемый результат: ValueError("version not found").
- Трассировка: tests/integration/test_versions.py::test_uc16_003_raises_error_for_unknown_version_name

### TC-UC16-004: fetch_prompt(name, version=seq)
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: есть несколько версий.
- Шаги:
1. Вызвать fetch_prompt(name, version=2).
- Ожидаемый результат: возвращен PromptMessages для seq=2.
- Трассировка: tests/integration/test_storage_facade.py::test_uc16_004_fetch_prompt_returns_requested_version

### TC-UC16-005: fetch_prompt с не-int version
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt существует.
- Шаги:
1. Вызвать fetch_prompt(name, version="2").
- Ожидаемый результат: TypeError.
- Трассировка: tests/integration/test_storage_facade.py::test_uc16_005_fetch_prompt_non_int_version_raises_type_error

### TC-UC16-006: fetch_prompt для отсутствующего prompt
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt отсутствует.
- Шаги:
1. Вызвать fetch_prompt(unknown_name).
- Ожидаемый результат: KeyError.
- Трассировка: tests/integration/test_storage_facade.py::test_uc16_006_fetch_prompt_missing_prompt_raises_key_error

### TC-UC16-008: fetch_prompt для prompt без версий
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: prompt создан, версий нет.
- Шаги:
1. Вызвать fetch_prompt(name).
- Ожидаемый результат: ValueError.
- Трассировка: tests/integration/test_storage_facade.py::test_uc16_008_fetch_prompt_without_versions_raises_value_error

## ВИ-17. Обновить тарифы моделей

### TC-UC17-001: update_tariffs успешный upsert
- Тип: integration
- Приоритет: Medium
- Статус: Implemented
- Предусловия: mock внешнего источника с валидными тарифами.
- Шаги:
1. Вызвать storage.update_tariffs(url).
2. Проверить количество upsert и данные в model_tariffs.
- Ожидаемый результат: тарифы обновлены/добавлены.
- Трассировка: tests/integration/test_storage_facade.py::test_uc17_001_update_tariffs_successfully_upserts

### TC-UC17-002: Недоступный источник
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: gateway получает URLError.
- Шаги:
1. Вызвать update_tariffs.
- Ожидаемый результат: ConnectionError.
- Трассировка: tests/integration/test_storage_facade.py::test_uc17_002_update_tariffs_propagates_connection_error

### TC-UC17-003: Невалидный формат ответа
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: источник возвращает невалидный JSON/структуру.
- Шаги:
1. Вызвать update_tariffs.
- Ожидаемый результат: ValueError.
- Трассировка: tests/integration/test_storage_facade.py::test_uc17_003_update_tariffs_propagates_value_error

### TC-UC17-004: Ошибка записи в БД
- Тип: contract
- Приоритет: Medium
- Статус: Implemented
- Предусловия: сбой во время bulk_upsert.
- Шаги:
1. Смоделировать sqlite error при update_tariffs.
- Ожидаемый результат: RuntimeError.
- Трассировка: tests/integration/test_storage_facade.py::test_uc17_004_update_tariffs_propagates_runtime_error