import sqlite3

import pytest

from prompthub.facade.storage import Storage


def _msg(text: str) -> list[tuple]:
    return [("user", text)]


def _create_prompt_with_versions(
    storage: Storage, prompt_name: str, contents: list[str]
):
    prompt = storage.create_prompt(prompt_name)

    for seq, content in enumerate(contents, start=1):
        prompt.add_version(
            content=_msg(content),
            name=f"v{seq}",
            message=f"version {seq}",
        )

    return prompt


@pytest.mark.contract
def test_uc02_002_requires_unique_prompt_name(tmp_path):
    db_path = tmp_path / "uc02_unique_name.sqlite3"

    storage = Storage(str(db_path))
    try:
        storage.create_prompt("duplicate_name")

        with pytest.raises((sqlite3.IntegrityError, ValueError)):
            storage.create_prompt("duplicate_name")
    finally:
        storage._conn.close()


@pytest.mark.contract
def test_uc03_004_update_with_identical_content_does_not_create_new_version(tmp_path):
    db_path = tmp_path / "uc03_no_changes.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("no_change_prompt")
        v1_id = prompt.add_version(
            content=[("user", "stable content")],
            name="v1",
            message="initial",
        )

        before_count = storage._conn.execute(
            "SELECT COUNT(*) FROM prompt_versions WHERE prompt_id = ?",
            (prompt.id,),
        ).fetchone()[0]

        returned_id = prompt.add_version(
            content=[("user", "stable content")],
            name="v2",
            message="should be ignored",
        )

        after_count = storage._conn.execute(
            "SELECT COUNT(*) FROM prompt_versions WHERE prompt_id = ?",
            (prompt.id,),
        ).fetchone()[0]

        assert after_count == before_count
        assert returned_id == v1_id
    finally:
        storage._conn.close()


@pytest.mark.contract
def test_uc08_001_rollback_by_version_name_creates_new_version_without_losing_history(
    tmp_path,
):
    db_path = tmp_path / "uc08_rollback_by_name.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="rollback_by_name_prompt",
            contents=["alpha", "beta", "gamma"],
        )

        before = prompt.list_versions()
        previous_latest_seq = before[-1].seq

        prompt.rollback(
            name="v1",
            name_rollback_version="rollback_to_v1",
        )

        after = prompt.list_versions()
        assert len(after) == len(before) + 1
        assert after[-1].seq == previous_latest_seq + 1
        assert after[-1].name == "rollback_to_v1"

        assert prompt.get_version_content(
            "rollback_to_v1"
        ) == prompt.get_version_content("v1")
        assert [row.name for row in after[:-1]] == ["v1", "v2", "v3"]
    finally:
        storage._conn.close()


@pytest.mark.contract
def test_uc08_002_rollback_by_steps_creates_new_version_without_losing_history(
    tmp_path,
):
    db_path = tmp_path / "uc08_rollback_by_steps.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="rollback_by_steps_prompt",
            contents=["one", "two", "three", "four"],
        )

        before = prompt.list_versions()
        previous_latest_seq = before[-1].seq

        prompt.rollback(
            steps_back=2,
            name_rollback_version="rollback_steps_2",
        )

        after = prompt.list_versions()
        assert len(after) == len(before) + 1
        assert after[-1].seq == previous_latest_seq + 1
        assert after[-1].name == "rollback_steps_2"

        assert prompt.get_version_content(
            "rollback_steps_2"
        ) == prompt.get_version_content("v2")
        assert [row.name for row in after[:-1]] == ["v1", "v2", "v3", "v4"]
    finally:
        storage._conn.close()


@pytest.mark.contract
def test_uc16_004_fetch_prompt_with_adapter_type(tmp_path):
    db_path = tmp_path / "uc16_adapter.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("prompt_adapter")
        prompt.add_version(
            content=[("user", "Hello"), ("assistant", "Hi!")],
            name="v1",
            message="initial",
        )

        result = storage.fetch_prompt("prompt_adapter", adapter_type="openai")

        assert isinstance(result, list)
        assert result[0] == {"role": "user", "content": "Hello"}
        assert result[1] == {"role": "assistant", "content": "Hi!"}
    finally:
        storage._conn.close()
