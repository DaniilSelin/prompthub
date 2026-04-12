import pytest

from prompthub.core.domain.tag import PromptTag


# --- ВИ-11: Удаление версии ---


@pytest.mark.contract
def test_uc11_002_delete_last_remaining_version_raises_error(storage):
    """Удаление единственной версии промпта должно блокироваться."""
    prompt = storage.create_prompt("last_version_test")
    version_id = prompt.add_version([("user", "only one version")])

    with pytest.raises(ValueError, match="Нельзя удалить единственную версию"):
        storage.repo.delete_version(version_id)

    versions = storage._conn.execute(
        "SELECT id FROM prompt_versions WHERE prompt_id = ?", (prompt.id,)
    ).fetchall()
    assert len(versions) == 1


# --- ВИ-13: Удаление промпта (Связи и консистентность) ---


@pytest.mark.contract
def test_uc13_003_global_tags_persistence_contract(storage):
    tag_name = "shared-tag"
    p1 = storage.create_prompt("prompt_1")
    p2 = storage.create_prompt("prompt_2")

    p1.add_prompt_tag(PromptTag(tag_name))
    p2.add_prompt_tag(PromptTag(tag_name))

    storage.repo.delete_prompt(p1.id)

    conn = storage._conn
    res_links = conn.execute(
        "SELECT * FROM prompt_tags WHERE prompt_id=?", (p1.id,)
    ).fetchall()
    assert len(res_links) == 0

    res_tag = conn.execute("SELECT * FROM tags WHERE name=?", (tag_name,)).fetchone()
    assert res_tag is not None
    assert res_tag["name"] == tag_name


@pytest.mark.contract
def test_uc13_004_delete_prompt_cleans_versions_metadata(storage):
    prompt = storage.create_prompt("clean_test")
    prompt.add_version([("user", "v1 content")])
    prompt.add_version([("user", "v2 content")])
    p_id = prompt.id

    storage.repo.delete_prompt(p_id)

    versions = storage._conn.execute(
        "SELECT id FROM prompt_versions WHERE prompt_id=?", (p_id,)
    ).fetchall()
    assert len(versions) == 0
