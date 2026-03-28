import sqlite3

import pytest

from prompthub.facade.storage import Storage


def _create_prompt_with_versions(
    storage: Storage, prompt_name: str, contents: list[str]
):
    prompt = storage.create_prompt(prompt_name, author="qa")

    for seq, content in enumerate(contents, start=1):
        prompt.add_version(
            content=content,
            name=f"v{seq}",
            author="qa",
            message=f"version {seq}",
        )

    return prompt


@pytest.mark.contract
@pytest.mark.xfail(
    strict=True,
    reason="Requirement expects unique prompt names, current schema allows duplicates",
)
def test_uc02_002_requires_unique_prompt_name_contract(tmp_path):
    db_path = tmp_path / "uc02_unique_name_contract.sqlite3"

    storage = Storage(str(db_path))
    try:
        storage.create_prompt("duplicate_name", author="qa")

        with pytest.raises((sqlite3.IntegrityError, ValueError)):
            storage.create_prompt("duplicate_name", author="qa")
    finally:
        storage._conn.close()


@pytest.mark.contract
@pytest.mark.xfail(
    strict=True,
    reason="Contract expects idempotent update without creating version; current implementation raises ValueError",
)
def test_uc03_004_contract_update_with_identical_content_does_not_create_new_version(
    tmp_path,
):
    db_path = tmp_path / "uc03_no_changes_contract.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("no_change_prompt", author="qa")
        prompt.add_version(
            content="stable content",
            name="v1",
            author="qa",
            message="initial",
        )

        before_count = storage._conn.execute(
            "SELECT COUNT(*) FROM prompt_versions WHERE prompt_id = ?",
            (prompt.id,),
        ).fetchone()[0]

        prompt.add_version(
            content="stable content",
            name="v2",
            author="qa",
            message="should be ignored",
        )

        after_count = storage._conn.execute(
            "SELECT COUNT(*) FROM prompt_versions WHERE prompt_id = ?",
            (prompt.id,),
        ).fetchone()[0]

        assert after_count == before_count
    finally:
        storage._conn.close()


@pytest.mark.contract
@pytest.mark.xfail(strict=True, reason="known rollback runtime defect")
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
        previous_latest_seq = before[-1]["seq"]

        prompt.rollback(
            name="v1",
            name_rollback_version="rollback_to_v1",
            author="qa",
        )

        after = prompt.list_versions()
        assert len(after) == len(before) + 1
        assert after[-1]["seq"] == previous_latest_seq + 1
        assert after[-1]["name"] == "rollback_to_v1"

        assert prompt.get_version_content(
            "rollback_to_v1"
        ) == prompt.get_version_content("v1")
        assert [row["name"] for row in after[:-1]] == ["v1", "v2", "v3"]
    finally:
        storage._conn.close()


@pytest.mark.contract
@pytest.mark.xfail(strict=True, reason="known rollback runtime defect")
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
        previous_latest_seq = before[-1]["seq"]

        prompt.rollback(
            steps_back=2,
            name_rollback_version="rollback_steps_2",
            author="qa",
        )

        after = prompt.list_versions()
        assert len(after) == len(before) + 1
        assert after[-1]["seq"] == previous_latest_seq + 1
        assert after[-1]["name"] == "rollback_steps_2"

        assert prompt.get_version_content(
            "rollback_steps_2"
        ) == prompt.get_version_content("v2")
        assert [row["name"] for row in after[:-1]] == ["v1", "v2", "v3", "v4"]
    finally:
        storage._conn.close()


@pytest.mark.contract
@pytest.mark.skip(
    reason="Required API get_prompt(name, version=None, adapter_type=None) is not implemented yet"
)
def test_uc16_004_adapter_type_contract_for_future_api(tmp_path):
    db_path = tmp_path / "uc16_adapter_contract.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("prompt_adapter_contract", author="qa")
        prompt.add_version(
            content="base",
            name="v1",
            author="qa",
            message="initial",
        )

        # Contract placeholder until adapter API is implemented.
        assert prompt is not None
    finally:
        storage._conn.close()
