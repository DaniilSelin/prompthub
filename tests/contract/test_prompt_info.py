import pytest
from prompthub.facade.storage import Storage
from prompthub.core.domain.diff import VersionDiff

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
def test_uc05_002_list_prompts_includes_token_count(storage):
    """list_prompts возвращает token_count для каждого промпта."""
    prompt = storage.create_prompt("priced_prompt", author="qa")
    prompt.add_version([("user", "hello world")], name="v1")

    data = storage.list_prompts()

    assert len(data) == 1
    assert "token_count" in data[0]
    assert data[0]["token_count"] == 2


# --- ВИ-6: История версий ---

@pytest.mark.integration
def test_uc06_001_version_history_order_and_fields(storage):
    """Позитивный: Проверка порядка версий (по seq) и наличия описания."""
    prompt = storage.create_prompt("history_test")
    prompt.add_version([("user", "ver 1")], name="v1", message="first commit")
    prompt.add_version([("user", "ver 2")], name="v2", message="second commit")

    history = prompt.list_versions()

    assert len(history) == 2
    assert history[0].seq == 1
    assert history[1].seq == 2
    assert history[0].message == "first commit"

@pytest.mark.integration
def test_uc06_002_history_after_prompt_deletion(storage):
    """Граничный: Проверка, что версии удаляются вместе с промптом (каскад)."""
    prompt = storage.create_prompt("to_delete")
    prompt.add_version([("user", "content")], name="v1")
    prompt_id = prompt.id

    storage.repo.delete_prompt(prompt_id)

    versions = storage._conn.execute(
        "SELECT id FROM prompt_versions WHERE prompt_id = ?", (prompt_id,)
    ).fetchall()
    assert len(versions) == 0


# --- ВИ-7: Сравнение версий ---

@pytest.mark.integration
def test_uc07_001_changeset_storage_integrity(storage):
    """Интеграционный: Проверка, что дельты физически записываются в prompt_changes."""
    prompt = storage.create_prompt("diff_test")
    prompt.add_version([("user", "Line 1")], name="v1")
    prompt.add_version([("user", "Line 1\nLine 2")], name="v2")

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
def test_uc07_002_compare_versions_returns_structured_diff(storage):
    """compare_versions_chars возвращает VersionDiff с изменёнными чанками."""
    prompt = storage.create_prompt("api_test")
    prompt.add_version([("user", "old content")], name="v1")
    prompt.add_version([("user", "new content")], name="v2")

    diff = prompt.compare_versions_chars("v1", "v2")

    assert isinstance(diff, VersionDiff)
    assert diff.has_changes
    changes = diff.only_changes()
    assert len(changes) > 0
    assert any(c.tag in ("insert", "replace", "delete") for c in changes)
