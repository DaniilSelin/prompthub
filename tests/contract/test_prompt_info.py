import pytest

import prompthub.core.tokenizers.registry as reg
from prompthub.core.domain.diff import StructuredDiff
from prompthub.core.domain.model_tariff import ModelTariff
from prompthub.core.tokenizers.base import ModelTag
from prompthub.core.tokenizers.openai_tag import OpenAIModelTag
from prompthub.infrastructure.tariff_manager import TariffManager


@pytest.mark.integration
def test_uc05_001_list_all_prompts_with_metadata(storage):
    storage.create_prompt("prompt_1")
    storage.create_prompt("prompt_2")

    all_prompts = storage._conn.execute("SELECT name FROM prompts").fetchall()

    assert len(all_prompts) == 2
    names = {p["name"] for p in all_prompts}
    assert names == {"prompt_1", "prompt_2"}


@pytest.mark.contract
def test_uc05_002_list_prompts_includes_per_model_token_count_and_cost(
    storage, monkeypatch
):
    class _FixedTokenOpenAITag(ModelTag):
        provider_key = "openai"

        def _count_text(self, text: str) -> int:
            return 8

    monkeypatch.setitem(reg._PROVIDER_REGISTRY, "openai", _FixedTokenOpenAITag)

    TariffManager(storage._conn).bulk_upsert(
        [
            ModelTariff(
                tag_name="gpt-4o",
                input_price_per_1m=2.5,
                output_price_per_1m=10.0,
            )
        ]
    )

    prompt = storage.create_prompt("priced_prompt")
    prompt.add_version([("user", "hello world")])
    storage.add_model_tags("priced_prompt", [OpenAIModelTag("gpt-4o")])

    data = storage.list_prompts()

    assert len(data) == 1
    costs = data[0]["costs"]
    assert "gpt-4o" in costs
    model_info = costs["gpt-4o"]
    assert "token_count" in model_info
    assert model_info["token_count"] > 0
    assert model_info["cost"] is not None
    assert model_info["cost"] > 0


@pytest.mark.integration
def test_uc06_001_version_history_order_and_fields(storage):
    prompt = storage.create_prompt("history_test")
    prompt.add_version([("user", "ver 1")], description="first commit")
    prompt.add_version([("user", "ver 2")], description="second commit")

    history = prompt.list_versions()

    assert len(history) == 2
    assert history[0].seq == 1
    assert history[1].seq == 2
    assert history[0].message == "first commit"


@pytest.mark.integration
def test_uc06_002_history_after_prompt_deletion(storage):
    prompt = storage.create_prompt("to_delete")
    prompt.add_version([("user", "content")])
    prompt_id = prompt.id

    storage.repo.delete_prompt(prompt_id)

    versions = storage._conn.execute(
        "SELECT id FROM prompt_versions WHERE prompt_id = ?", (prompt_id,)
    ).fetchall()
    assert len(versions) == 0


@pytest.mark.integration
def test_uc07_001_changeset_storage_integrity(storage):
    prompt = storage.create_prompt("diff_test")
    prompt.add_version([("user", "Line 1")])
    prompt.add_version([("user", "Line 1\nLine 2")])

    changes = storage._conn.execute(
        """
        SELECT pc.op_type, pc.text
        FROM prompt_changes pc
        JOIN prompt_versions pv ON pc.version_id = pv.id
        WHERE pv.prompt_id = ?
        """,
        (prompt.id,),
    ).fetchall()

    assert len(changes) > 0
    assert any("Line 2" in str(c["text"]) for c in changes)


@pytest.mark.contract
def test_uc07_002_compare_versions_returns_structured_diff(storage):
    prompt = storage.create_prompt("structured_contract")
    prompt.add_version([("user", "hello")])
    prompt.add_version([("user", "hello world")])

    diff = prompt.compare_versions_structured(1, 2)

    assert isinstance(diff, StructuredDiff)
    assert diff.name_a == "seq-1"
    assert diff.name_b == "seq-2"
    assert diff.has_changes
    assert diff.changed


@pytest.mark.contract
def test_uc06_003_list_versions_exposes_expected_fields(storage):
    prompt = storage.create_prompt("history_fields")
    prompt.add_version([("user", "v1")], description="first")

    history = prompt.list_versions()

    assert len(history) == 1
    version = history[0]
    assert version.seq == 1
    assert version.name == "seq-1"
    assert version.message == "first"
    assert version.created_at is not None
    assert version.is_snapshot is True
