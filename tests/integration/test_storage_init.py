import sqlite3

import pytest

from facade.storage import Storage


@pytest.mark.integration
def test_uc01_001_creates_new_db_schema_and_configures_pragmas(tmp_path):
    db_path = tmp_path / "storage_init.sqlite3"
    assert not db_path.exists()

    storage = Storage(str(db_path))
    try:
        assert db_path.exists()

        conn = storage._conn
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {
            "prompts",
            "prompt_versions",
            "prompt_changes",
            "tags",
            "prompt_tags",
        }.issubset(tables)

        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert {
            "idx_prompt_tags_prompt",
            "idx_prompt_tags_tag",
            "idx_pv_prompt_seq",
            "idx_pv_prompt_name",
            "idx_pv_snapshot",
        }.issubset(indexes)

        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        foreign_keys = conn.execute("PRAGMA foreign_keys").fetchone()[0]

        assert str(journal_mode).lower() == "wal"
        assert foreign_keys == 1
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc01_002_reinitialization_preserves_existing_data(tmp_path):
    db_path = tmp_path / "storage_reinit.sqlite3"
    prompt_name = "prompt_reinit"
    version_name = "v1"
    content = "Hello, world!"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt(prompt_name, author="qa")
        prompt.add_version(
            content=content,
            name=version_name,
            author="qa",
            message="initial version",
        )

        existing_prompt = storage.get_prompt(prompt_name)
        assert existing_prompt.get_version_content(version_name) == content
    finally:
        storage._conn.close()

    reinitialized_storage = Storage(str(db_path))
    try:
        restored_prompt = reinitialized_storage.get_prompt(prompt_name)
        assert restored_prompt.get_version_content(version_name) == content

        versions = restored_prompt.list_versions()
        assert len(versions) == 1
        assert versions[0]["seq"] == 1
    finally:
        reinitialized_storage._conn.close()


@pytest.mark.integration
def test_uc01_003_raises_error_when_db_path_is_unavailable(monkeypatch, tmp_path):
    db_path = tmp_path / "unavailable" / "storage.sqlite3"

    def failing_connect(*args, **kwargs):
        raise sqlite3.OperationalError("unable to open database file")

    monkeypatch.setattr("facade.storage.sqlite3.connect", failing_connect)

    with pytest.raises(sqlite3.OperationalError, match="unable to open database file"):
        Storage(str(db_path))
