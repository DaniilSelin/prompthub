import json
import pytest

from prompthub.facade.storage import Storage


def _msg(*texts, role="user"):
    """Вспомогательная функция: создаёт список сообщений из текстов."""
    return [(role, t) for t in texts]


@pytest.mark.integration
def test_uc02_001_creates_prompt_and_first_version(tmp_path):
    db_path = tmp_path / "uc02_create_prompt.sqlite3"

    storage = Storage(str(db_path))
    try:
        messages_v1 = [("system", "welcome user")]
        prompt = storage.create_prompt("welcome_prompt")
        version_id = prompt.add_version(
            content=messages_v1,
            description="initial",
        )

        assert isinstance(version_id, int)

        versions = prompt.list_versions()
        assert len(versions) == 1
        assert versions[0].seq == 1
        assert versions[0].name == "seq-1"
        assert [tuple(m) for m in json.loads(versions[0].snapshot_content)] == messages_v1
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc02_003_prompt_metadata_created_at_is_stored(tmp_path):
    db_path = tmp_path / "uc02_metadata.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt_name = "metadata_prompt"

        storage.create_prompt(prompt_name)

        row = storage.repo.get_prompt_by_name(prompt_name)
        assert row is not None
        assert row["name"] == prompt_name
        assert row["created_at"] is not None
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc02_004_create_prompt_rolls_back_on_initial_version_failure(tmp_path, monkeypatch):
    db_path = tmp_path / "uc02_atomic_create.sqlite3"

    storage = Storage(str(db_path))
    try:
        def _fail_add_version(*args, **kwargs):
            raise RuntimeError("forced failure")

        monkeypatch.setattr("prompthub.facade.prompt.Prompt.add_version", _fail_add_version)

        with pytest.raises(RuntimeError, match="forced failure"):
            storage.create_prompt(
                "atomic_prompt",
                messages=[("user", "hello")],
                description="initial",
            )

        assert storage.repo.get_prompt_by_name("atomic_prompt") is None
    finally:
        storage._conn.close()




@pytest.mark.integration
def test_uc03_001_adds_new_version_increments_seq_and_sets_parent(tmp_path):
    db_path = tmp_path / "uc03_new_version.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("editable_prompt")
        first_version_id = prompt.add_version(
            content=[("user", "Hello")],
            description="initial",
        )

        second_version_id = prompt.add_version(
            content=[("user", "Hello, world")],
            description="update",
        )

        versions = prompt.list_versions()
        assert len(versions) == 2
        assert versions[0].seq == 1
        assert versions[1].seq == 2

        second_row = storage._conn.execute(
            """
            SELECT parent_version_id
            FROM prompt_versions
            WHERE id = ?
            """,
            (second_version_id,),
        ).fetchone()

        assert second_row is not None
        assert second_row["parent_version_id"] == first_version_id
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc03_003_stores_snapshot_every_snapshot_interval(tmp_path):
    db_path = tmp_path / "uc03_snapshot.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("snapshot_prompt")

        for seq in range(1, 6):
            prompt.add_version(
                content=[("user", f"content v{seq}")],
                description=f"change {seq}",
            )

        rows = storage._conn.execute(
            """
            SELECT seq, snapshot_content
            FROM prompt_versions
            WHERE prompt_id = ?
            ORDER BY seq ASC
            """,
            (prompt.id,),
        ).fetchall()

        assert len(rows) == 5
        assert json.loads(rows[0]["snapshot_content"]) == [["user", "content v1"]]
        assert rows[1]["snapshot_content"] is None
        assert rows[2]["snapshot_content"] is None
        assert rows[3]["snapshot_content"] is None
        assert json.loads(rows[4]["snapshot_content"]) == [["user", "content v5"]]
    finally:
        storage._conn.close()
