import pytest
import sqlite3
from prompthub.facade.storage import Storage

@pytest.fixture
def storage(tmp_path):
    db_path = tmp_path / "deletion_contract.sqlite3"
    storage_obj = Storage(str(db_path))
    yield storage_obj
    storage_obj._conn.close()

# --- ВИ-11: Удаление версии (Сложные случаи) ---

@pytest.mark.contract
@pytest.mark.xfail(strict=True, reason="Удаление единственной версии промпта должно блокироваться или удалять промпт")
def test_uc11_002_delete_last_remaining_version_contract(storage):
    prompt = storage.create_prompt("last_version_test")
    prompt.add_version("only one version", name="v1")
    
    storage.repo.delete_version(prompt.id, "v1")
    
    assert storage.repo.get_prompt_by_name("last_version_test") is None

@pytest.mark.contract
@pytest.mark.skip(reason="История удалений (Audit Log) еще не реализована")
def test_uc11_003_contract_deletion_audit_log(storage):
    prompt = storage.create_prompt("audit_test")
    prompt.add_version("content", name="v1")
    
    storage.repo.delete_version(prompt.id, "v1", user_id="admin_01")
    
    logs = storage.get_audit_logs(prompt_id=prompt.id)
    assert logs[0]["action"] == "DELETE_VERSION"
    assert logs[0]["user_id"] == "admin_01"


# --- ВИ-12: Защита от удаления (Заморозка / Роли) ---

@pytest.mark.contract
@pytest.mark.skip(reason="Ролевая модель (permissions) еще не реализована")
def test_uc12_002_non_author_cannot_delete_contract(storage):
    prompt = storage.create_prompt("private_prompt", author="user_A")
    
    with pytest.raises(PermissionError, match="Insufficient permissions"):
        storage.repo.delete_prompt(prompt.id, requestor_id="user_B")


# --- ВИ-13: Удаление промпта (Связи и консистентность) ---

@pytest.mark.contract
def test_uc13_003_global_tags_persistence_contract(storage):
    tag_name = "shared-tag"
    p1 = storage.create_prompt("prompt_1")
    p2 = storage.create_prompt("prompt_2")
    
    p1.add_tag(tag_name, "prompt")
    p2.add_tag(tag_name, "prompt")
    
    storage.repo.delete_prompt(p1.id)
    
    conn = storage._conn
    res_links = conn.execute("SELECT * FROM prompt_tags WHERE prompt_id=?", (p1.id,)).fetchall()
    assert len(res_links) == 0
    
    res_tag = conn.execute("SELECT * FROM tags WHERE name=?", (tag_name,)).fetchone()
    assert res_tag is not None
    assert res_tag["name"] == tag_name

@pytest.mark.contract
def test_uc13_004_delete_prompt_cleans_versions_metadata(storage):
    prompt = storage.create_prompt("clean_test")
    prompt.add_version("v1", name="v1")
    prompt.add_version("v2", name="v2")
    p_id = prompt.id
    
    storage.repo.delete_prompt(p_id)
    
    versions = storage._conn.execute("SELECT id FROM prompt_versions WHERE prompt_id=?", (p_id,)).fetchall()
    assert len(versions) == 0