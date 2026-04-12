import json

import pytest

from prompthub.core.domain.diff import VersionDiff, VersionLineDiff
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
def test_uc07_002_compare_versions_line_diff_shows_changes(tmp_path):
    """TC-UC07-002: line diff между двумя различными версиями содержит изменения."""
    storage = Storage(str(tmp_path / "uc07_line_diff.sqlite3"))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            "line_diff_prompt",
            ["Hello world", "Hello Python world"],
        )

        diff = prompt.compare_versions(1, 2)

        assert isinstance(diff, VersionLineDiff)
        assert diff.name_a == "seq-1"
        assert diff.name_b == "seq-2"
        assert diff.has_changes
        unified = diff.unified()
        assert "Hello world" in unified
        assert "Hello Python world" in unified
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_003_compare_versions_line_diff_identical_has_no_changes(tmp_path):
    """TC-UC07-003: line diff для одной и той же версии пуст."""
    storage = Storage(str(tmp_path / "uc07_line_identical.sqlite3"))
    try:
        prompt = storage.create_prompt("identical_line_prompt")
        prompt.add_version(content=_msg("stable content"))

        diff = prompt.compare_versions(1, 1)

        assert isinstance(diff, VersionLineDiff)
        assert not diff.has_changes
        assert diff.unified() == ""
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_004_compare_versions_chars_shows_changes(tmp_path):
    """TC-UC07-004: char diff между версиями возвращает DiffChunk с изменениями."""
    storage = Storage(str(tmp_path / "uc07_chars_diff.sqlite3"))
    try:
        prompt = _create_prompt_with_versions(
            storage,
            "chars_diff_prompt",
            ["Hello world", "Hello Python world"],
        )

        diff = prompt.compare_versions_chars(1, 2)

        assert isinstance(diff, VersionDiff)
        assert diff.name_a == "seq-1"
        assert diff.name_b == "seq-2"
        assert diff.has_changes
        changes = diff.only_changes()
        assert len(changes) > 0
        inserted = [c.new_text for c in changes if c.tag in ("insert", "replace")]
        assert any("Python" in t for t in inserted)
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_005_compare_versions_chars_identical_has_no_changes(tmp_path):
    """TC-UC07-005: char diff для одной и той же версии не содержит изменённых чанков."""
    storage = Storage(str(tmp_path / "uc07_chars_identical.sqlite3"))
    try:
        prompt = storage.create_prompt("identical_chars_prompt")
        prompt.add_version(content=_msg("stable content"))

        diff = prompt.compare_versions_chars(1, 1)

        assert isinstance(diff, VersionDiff)
        assert not diff.has_changes
        assert diff.only_changes() == []
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_006_compare_versions_raises_for_unknown_version(tmp_path):
    """TC-UC07-006: compare_versions выбрасывает ValueError для несуществующей версии."""
    storage = Storage(str(tmp_path / "uc07_unknown.sqlite3"))
    try:
        prompt = storage.create_prompt("prompt_compare_error")
        prompt.add_version(content=_msg("some content"))

        with pytest.raises(ValueError, match="version not found"):
            prompt.compare_versions(1, 999)

        with pytest.raises(ValueError, match="version not found"):
            prompt.compare_versions_chars(999, 1)
    finally:
        storage._conn.close()


@pytest.mark.integration
def test_uc07_007_compare_versions_chars_chunks_cover_full_content(tmp_path):
    """TC-UC07-007: совокупность чанков char diff покрывает оба контента целиком."""
    storage = Storage(str(tmp_path / "uc07_chunks_cover.sqlite3"))
    try:
        content_a = _msg("Hello world")
        content_b = _msg("Hi Python world!")
        prompt = _create_prompt_with_versions(
            storage, "chunks_cover_prompt", ["Hello world", "Hi Python world!"]
        )

        diff = prompt.compare_versions_chars(1, 2)

        reconstructed_a = "".join(c.old_text for c in diff.chunks)
        reconstructed_b = "".join(c.new_text for c in diff.chunks)
        assert reconstructed_a == json.dumps(content_a, ensure_ascii=False)
        assert reconstructed_b == json.dumps(content_b, ensure_ascii=False)
    finally:
        storage._conn.close()
