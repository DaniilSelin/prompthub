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


@pytest.mark.contract
def test_uc02_002_requires_unique_prompt_name(tmp_path):
    db_path = tmp_path / "uc02_unique_name.sqlite3"

    storage = Storage(str(db_path))
    try:
        storage.create_prompt("duplicate_name")

        with pytest.raises(KeyError):
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
            description="initial",
        )

        before_count = storage._conn.execute(
            "SELECT COUNT(*) FROM prompt_versions WHERE prompt_id = ?",
            (prompt.id,),
        ).fetchone()[0]

        returned_id = prompt.add_version(
            content=[("user", "stable content")],
            description="should be ignored",
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

        prompt.rollback(target_seq=1)

        after = prompt.list_versions()
        assert len(after) == len(before) + 1
        assert after[-1].seq == previous_latest_seq + 1
        assert after[-1].name == "seq-4"

        assert prompt.get_version_content(after[-1].seq) == prompt.get_version_content(
            1
        )
        assert [row.seq for row in after[:-1]] == [1, 2, 3]
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

        prompt.rollback(steps_back=2)

        after = prompt.list_versions()
        assert len(after) == len(before) + 1
        assert after[-1].seq == previous_latest_seq + 1
        assert after[-1].name == "seq-5"

        assert prompt.get_version_content(after[-1].seq) == prompt.get_version_content(
            2
        )
        assert [row.seq for row in after[:-1]] == [1, 2, 3, 4]
    finally:
        storage._conn.close()


@pytest.mark.contract
def test_uc16_004_fetch_prompt_returns_prompt_messages(tmp_path):
    """fetch_prompt возвращает PromptMessages без адаптера."""
    from prompthub.core.domain.prompt_messages import PromptMessages

    db_path = tmp_path / "uc16_raw.sqlite3"
    storage = Storage(str(db_path))
    try:
        prompt = storage.create_prompt("prompt_raw")
        prompt.add_version(
            content=[("user", "Hello"), ("assistant", "Hi!")],
            description="initial",
        )

        result = storage.fetch_prompt("prompt_raw")

        assert isinstance(result, PromptMessages)
        assert result.content == [("user", "Hello"), ("assistant", "Hi!")]
    finally:
        storage._conn.close()


@pytest.mark.contract
def test_uc16_005_langchain_prompt_adapter_wraps_prompt(tmp_path):
    """LangChainPromptAdapter проксирует Prompt и конвертирует контент в ChatPromptTemplate."""
    from prompthub.adapters import LangChainPromptAdapter

    db_path = tmp_path / "uc16_langchain_proxy.sqlite3"
    storage = Storage(str(db_path))
    try:
        p = storage.create_prompt("prompt_lc")
        p.add_version(
            content=[("system", "You are helpful"), ("user", "Hello")],
            description="initial",
        )

        lc = LangChainPromptAdapter(storage.get_prompt("prompt_lc"))

        try:
            result = lc.get_version_content(1)
        except ImportError:
            pytest.skip("langchain-core не установлен")
        else:
            # Результат должен быть ChatPromptTemplate
            assert type(result).__name__ == "ChatPromptTemplate"
    finally:
        storage._conn.close()


@pytest.mark.contract
def test_uc16_006_langchain_adapter_delegates_add_version(tmp_path):
    """LangChainPromptAdapter.add_version принимает raw-туплы и делегирует Prompt."""
    from prompthub.adapters import LangChainPromptAdapter

    db_path = tmp_path / "uc16_langchain_add.sqlite3"
    storage = Storage(str(db_path))
    try:
        p = storage.create_prompt("prompt_lc_add")
        p.add_version(content=[("user", "v1")])

        lc = LangChainPromptAdapter(storage.get_prompt("prompt_lc_add"))
        lc.add_version([("user", "v2"), ("assistant", "ok")])

        versions = lc.list_versions()
        assert len(versions) == 2
    finally:
        storage._conn.close()
