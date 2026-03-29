import pytest
import sqlite3
from prompthub.facade.storage import Storage

@pytest.fixture
def storage(tmp_path):
    """Фикстура для создания чистого хранилища перед каждым тестом."""
    db_path = tmp_path / "test_info.sqlite3"
    storage_obj = Storage(str(db_path))
    yield storage_obj
    storage_obj._conn.close()

# --- ВИ-5: Список промптов ---

@pytest.mark.integration
def test_uc05_001_list_all_prompts_with_metadata(storage):
    """Позитивный: Получение списка всех промптов с их авторами."""
    storage.create_prompt("prompt_1", author="alice")
    storage.create_prompt("prompt_2", author="bob")
    
    all_prompts = storage._conn.execute("SELECT name, author FROM prompts").fetchall()

    assert len(all_prompts) == 2
    names = {p["name"] for p in all_prompts}
    assert names == {"prompt_1", "prompt_2"}

@pytest.mark.contract
@pytest.mark.skip(reason="Расчет стоимости и токенов еще не реализован")
def test_uc05_002_contract_list_includes_pricing_and_tokens(storage):
    storage.create_prompt("priced_prompt")
    # Ожидаемый будущий API
    data = storage.repo.get_all_prompts_with_pricing() 
    assert "cost" in data[0]
    assert "tokens_count" in data[0]


# --- ВИ-6: История версий ---

@pytest.mark.integration
def test_uc06_001_version_history_order_and_fields(storage):
    """Позитивный: Проверка порядка версий (по seq) и наличия описания."""
    prompt = storage.create_prompt("history_test")
    prompt.add_version("ver 1", name="v1", message="first commit")
    prompt.add_version("ver 2", name="v2", message="second commit")
    
    history = prompt.list_versions()
    
    assert len(history) == 2
    assert history[0].seq == 1
    assert history[1].seq == 2
    assert history[0].message == "first commit"

@pytest.mark.integration
def test_uc06_002_history_after_prompt_deletion(storage):
    """Граничный: Проверка, что версии удаляются вместе с промптом (каскад)."""
    prompt = storage.create_prompt("to_delete")
    prompt.add_version("content", name="v1")
    prompt_id = prompt.id
    
    # Удаляем промпт (предположим, через репозиторий или фасад)
    storage.repo.delete_prompt(prompt_id)
    
    # Проверяем напрямую в БД, что версий не осталось
    versions = storage._conn.execute(
        "SELECT id FROM prompt_versions WHERE prompt_id = ?", (prompt_id,)
    ).fetchall()
    assert len(versions) == 0


# --- ВИ-7: Сравнение версий ---

@pytest.mark.integration
def test_uc07_001_changeset_storage_integrity(storage):
    """Интеграционный: Проверка, что дельты физически записываются в prompt_changes."""
    prompt = storage.create_prompt("diff_test")
    prompt.add_version("Line 1", name="v1")
    prompt.add_version("Line 1\nLine 2", name="v2")
    
    changes = storage._conn.execute(
        """
        SELECT pc.op_type, pc.text
        FROM prompt_changes pc
        JOIN prompt_versions pv ON pc.version_id = pv.id
        WHERE pv.prompt_id = ?
        """,
        (prompt.id,),
    ).fetchall()

    assert len(changes) > 0
    assert any("Line 2" in str(c["text"]) for c in changes)

@pytest.mark.contract
@pytest.mark.skip(reason="Публичный API сравнения (ВИ-7) еще не реализован")
def test_uc07_002_contract_compare_output_structure(storage):
    """Контракт: Метод compare должен возвращать структурированный diff."""
    prompt = storage.create_prompt("api_test")
    prompt.add_version("old", name="v1")
    prompt.add_version("new", name="v2")
    
    
    diff = prompt.compare("v1", "v2")
    assert isinstance(diff, list) 
    assert "type" in diff[0]     