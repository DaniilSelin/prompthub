import pytest

from prompthub.core.domain.diff import StructuredDiff
from prompthub.facade.prompt import Prompt
from prompthub.facade.storage import Storage


def _msg(text: str) -> list[tuple[str, str]]:
    return [("user", text)]


def _create_prompt_with_versions(
    storage: Storage, prompt_name: str, contents: list[str]
) -> Prompt:
    prompt = storage.create_prompt(prompt_name)
    for seq, content in enumerate(contents, start=1):
        prompt.add_version(content=_msg(content), description=f"version {seq}")
    return prompt


@pytest.mark.integration
def test_uc07_002_compare_versions_structured_shows_changed_message(tmp_path):
    """TC-UC07-002: структурный diff между версиями с измененным контентом."""
    storage = Storage(str(tmp_path / "uc07_structured.sqlite3"))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            "structured_diff_prompt",
            ["Hello world", "Hello Python world"],
        )

        diff = prompt.compare_versions_structured(1, 2)

        assert isinstance(diff, StructuredDiff)
        assert diff.name_a == "seq-1"
        assert diff.name_b == "seq-2"
        assert diff.has_changes
        assert len(diff.changed) == 1
        assert diff.changed[0].role == "user"
        assert "Hello world" in diff.changed[0].old_content
        assert "Hello Python world" in diff.changed[0].new_content
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_003_compare_versions_structured_identical_has_no_changes(tmp_path):
    """TC-UC07-003: структурный diff для одной и той же версии пуст."""
    storage = Storage(str(tmp_path / "uc07_structured_identical.sqlite3"))
    try:
        prompt = storage.create_prompt("identical_structured_prompt")
        prompt.add_version(content=_msg("stable content"))

        import warnings

        with warnings.catch_warnings(record=True):
            diff = prompt.compare_versions_structured(1, 1)

        assert isinstance(diff, StructuredDiff)
        assert not diff.has_changes
        assert diff.added == []
        assert diff.deleted == []
        assert diff.changed == []
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_004_compare_versions_structured_detects_added_message(tmp_path):
    """TC-UC07-004: структурный diff обнаруживает добавленное сообщение."""
    storage = Storage(str(tmp_path / "uc07_added_msg.sqlite3"))
    try:
        prompt = storage.create_prompt("added_msg_prompt")
        prompt.add_version(content=[("system", "You are helpful")])
        prompt.add_version(content=[("system", "You are helpful"), ("user", "Hello")])

        diff = prompt.compare_versions_structured(1, 2)

        assert diff.has_changes
        assert len(diff.added) == 1
        assert diff.added[0] == ("user", "Hello")
        assert diff.deleted == []
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_005_compare_versions_structured_detects_deleted_message(tmp_path):
    """TC-UC07-005: структурный diff обнаруживает удаленное сообщение."""
    storage = Storage(str(tmp_path / "uc07_deleted_msg.sqlite3"))
    try:
        prompt = storage.create_prompt("deleted_msg_prompt")
        prompt.add_version(content=[("system", "You are helpful"), ("user", "Hello")])
        prompt.add_version(content=[("system", "You are helpful")])

        diff = prompt.compare_versions_structured(1, 2)

        assert diff.has_changes
        assert len(diff.deleted) == 1
        assert diff.deleted[0] == ("user", "Hello")
        assert diff.added == []
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_006_compare_versions_structured_raises_for_unknown_version(tmp_path):
    """TC-UC07-006: compare_versions_structured выбрасывает ValueError для несуществующей версии."""
    storage = Storage(str(tmp_path / "uc07_unknown.sqlite3"))
    try:
        prompt = storage.create_prompt("prompt_compare_error")
        prompt.add_version(content=_msg("some content"))

        with pytest.raises(ValueError, match="version not found"):
            prompt.compare_versions_structured(1, 999)

        with pytest.raises(ValueError, match="version not found"):
            prompt.compare_versions_structured(999, 1)
    finally:
        storage._conn.close()
