import pytest

from prompthub.facade.storage import Storage


@pytest.mark.integration
def test_uc02_001_creates_prompt_and_first_version(tmp_path):
    db_path = tmp_path / "uc02_create_prompt.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("welcome_prompt", author="qa")
        version_id = prompt.add_version(
            content="System: welcome user",
            name="v1",
            author="qa",
            message="initial",
        )

        assert isinstance(version_id, int)

        versions = prompt.list_versions()
        assert len(versions) == 1
        assert versions[0].seq == 1
        assert versions[0].name == "v1"
        assert versions[0].snapshot_content == "System: welcome user"
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc02_003_prompt_metadata_author_and_created_at_are_stored(tmp_path):
    db_path = tmp_path / "uc02_metadata.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt_name = "metadata_prompt"
        prompt_author = "qa-author"

        storage.create_prompt(prompt_name, author=prompt_author)

        row = storage.repo.get_prompt_by_name(prompt_name)
        assert row is not None
        assert row["name"] == prompt_name
        assert row["author"] == prompt_author
        assert row["created_at"] is not None
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc02_004_current_implementation_allows_duplicate_prompt_names(tmp_path):
    db_path = tmp_path / "uc02_duplicate_allowed.sqlite3"

    storage = Storage(str(db_path))
    try:
        duplicate_name = "same_name"

        storage.create_prompt(duplicate_name, author="qa")
        storage.create_prompt(duplicate_name, author="qa")

        count = storage._conn.execute(
            "SELECT COUNT(*) FROM prompts WHERE name = ?",
            (duplicate_name,),
        ).fetchone()[0]

        assert count == 2
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc03_001_adds_new_version_increments_seq_and_sets_parent(tmp_path):
    db_path = tmp_path / "uc03_new_version.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("editable_prompt", author="qa")
        first_version_id = prompt.add_version(
            content="Hello",
            name="v1",
            author="qa",
            message="initial",
        )

        second_version_id = prompt.add_version(
            content="Hello, world",
            name="v2",
            author="qa",
            message="update",
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
        prompt = storage.create_prompt("snapshot_prompt", author="qa")

        for seq in range(1, 6):
            prompt.add_version(
                content=f"content v{seq}",
                name=f"v{seq}",
                author="qa",
                message=f"change {seq}",
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
        assert rows[0]["snapshot_content"] == "content v1"
        assert rows[1]["snapshot_content"] is None
        assert rows[2]["snapshot_content"] is None
        assert rows[3]["snapshot_content"] is None
        assert rows[4]["snapshot_content"] == "content v5"
    finally:
        storage._conn.close()
