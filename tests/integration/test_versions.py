import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from prompthub.facade.prompt import Prompt
from prompthub.facade.storage import Storage


def _msg(text: str) -> list[tuple[str, str]]:
    return [("user", text)]


def _create_prompt_with_versions(
    storage: Storage, prompt_name: str, contents: list[str]
) -> Prompt:
    prompt = storage.create_prompt(prompt_name)

    for seq, content in enumerate(contents, start=1):
        prompt.add_version(
            content=_msg(content),
            description=f"version {seq}",
        )

    return prompt


@pytest.mark.integration
def test_uc08_003_rollback_with_invalid_steps_back_raises_value_error(tmp_path):
    db_path = tmp_path / "uc08_invalid_steps.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="invalid_steps_prompt",
            contents=["first", "second"],
        )

        with pytest.raises(ValueError, match="Некорректное количество шагов"):
            prompt.rollback(steps_back=999)

        with pytest.raises(ValueError, match="Некорректное количество шагов"):
            prompt.rollback(steps_back=-1)

        versions_after = prompt.list_versions()
        assert len(versions_after) == 2
        assert [row.seq for row in versions_after] == [1, 2]
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc16_001_returns_latest_version_content(tmp_path):
    db_path = tmp_path / "uc16_latest.sqlite3"

    storage = Storage(str(db_path))
    try:
        expected_contents = ["alpha", "alpha beta", "alpha beta gamma"]
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="prompt_latest",
            contents=expected_contents,
        )

        latest_version_seq = prompt.list_versions()[-1].seq
        latest_content = prompt.get_version_content(latest_version_seq)

        assert latest_version_seq == 3
        assert latest_content == _msg(expected_contents[-1])
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc16_002_reconstructs_content_from_snapshot_and_delta_chain(tmp_path):
    db_path = tmp_path / "uc16_assemble.sqlite3"

    storage = Storage(str(db_path))
    try:
        contents = [
            "A",
            "AB",
            "AB!",
            "A B!",
            "A B!?",
            "A B!?+",
            "A B!?+ END",
        ]
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="prompt_assemble",
            contents=contents,
        )

        v6_content = prompt.get_version_content(6)
        v7_content = prompt.get_version_content(7)

        assert v6_content == _msg(contents[5])
        assert v7_content == _msg(contents[6])

        snapshot_row = storage._conn.execute(
            """
            SELECT seq, snapshot_content
            FROM prompt_versions
            WHERE prompt_id = ? AND snapshot_content IS NOT NULL
            ORDER BY seq ASC
            """,
            (prompt.id,),
        ).fetchall()

        assert [row["seq"] for row in snapshot_row] == [1, 5]
        assert json.loads(snapshot_row[-1]["snapshot_content"]) == [
            list(m) for m in _msg(contents[4])
        ]
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc16_007_reconstructs_version_with_multi_operation_changeset(tmp_path):
    db_path = tmp_path / "uc16_multi_ops.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("prompt_multi_ops")
        prompt.add_version(content=_msg("abc123"))
        prompt.add_version(content=_msg("x_bc!23z"))

        changes_count = storage._conn.execute(
            """
            SELECT COUNT(*)
            FROM prompt_changes pc
            JOIN prompt_versions pv ON pv.id = pc.version_id
            WHERE pv.prompt_id = ? AND pv.seq = ?
            """,
            (prompt.id, 2),
        ).fetchone()[0]

        assert changes_count >= 2
        assert prompt.get_version_content(2) == _msg("x_bc!23z")
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc08_004_rollback_hard_by_name_removes_later_versions(tmp_path):
    """TC-UC08-004: rollback_hard по имени удаляет версии после целевой."""
    db_path = tmp_path / "uc08_hard_by_name.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="hard_rollback_prompt",
            contents=["v1 content", "v2 content", "v3 content", "v4 content"],
        )

        assert len(prompt.list_versions()) == 4

        prompt.rollback_hard(target_seq=2)

        versions = prompt.list_versions()
        assert len(versions) == 2
        assert [v.seq for v in versions] == [1, 2]
        assert prompt.get_version_content(2) == _msg("v2 content")
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc08_005_rollback_hard_by_steps_removes_later_versions(tmp_path):
    """TC-UC08-005: rollback_hard по steps_back удаляет нужные версии."""
    db_path = tmp_path / "uc08_hard_by_steps.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="hard_rollback_steps_prompt",
            contents=["first", "second", "third"],
        )

        prompt.rollback_hard(steps_back=1)

        versions = prompt.list_versions()
        assert len(versions) == 2
        assert versions[-1].seq == 2
        assert prompt.get_version_content(2) == _msg("second")
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc08_006_rollback_hard_raises_for_unknown_name(tmp_path):
    """TC-UC08-006: rollback_hard выбрасывает ValueError для несуществующего имени версии."""
    db_path = tmp_path / "uc08_hard_unknown.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="hard_rollback_error_prompt",
            contents=["only"],
        )

        with pytest.raises(ValueError):
            prompt.rollback_hard(target_seq=999)
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc16_003_raises_error_for_unknown_version_name(tmp_path):
    db_path = tmp_path / "uc16_unknown_version.sqlite3"

    storage = Storage(str(db_path))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            prompt_name="prompt_unknown",
            contents=["first", "second"],
        )

        with pytest.raises(ValueError, match="version not found"):
            prompt.get_version_content(999)
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc03_005_concurrent_add_version_keeps_unique_seq(tmp_path):
    db_path = tmp_path / "uc03_concurrent.sqlite3"

    bootstrap = Storage(str(db_path))
    try:
        prompt = bootstrap.create_prompt("concurrent_prompt")
        prompt.add_version(content=_msg("base"))
    finally:
        bootstrap._conn.close()

    def _worker(i: int) -> None:
        s = Storage(str(db_path))
        try:
            p = s.get_prompt("concurrent_prompt")
            p.add_version(content=_msg(f"content-{i}"))
        finally:
            s._conn.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_worker, i) for i in range(2, 10)]
        for f in futures:
            f.result()

    check = Storage(str(db_path))
    try:
        prompt = check.get_prompt("concurrent_prompt")
        seqs = [v.seq for v in prompt.list_versions()]

        assert len(seqs) == len(set(seqs))
        assert sorted(seqs) == list(range(1, len(seqs) + 1))
    finally:
        check._conn.close()
