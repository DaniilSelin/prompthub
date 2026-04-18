import warnings

import pytest

from prompthub.core.domain.model_tariff import ModelTariff
from prompthub.core.tokenizers.base import ModelTag
from prompthub.infrastructure.tariff_manager import TariffManager
from prompthub.search.filters import TagFilter


class _DummyModelTag(ModelTag):
    provider_key = "dummy-provider"

    def _count_text(self, text: str) -> int:
        return len(text.split())


@pytest.mark.integration
def test_uc04_001_delete_prompt_removes_prompt_versions_and_links(storage):
    prompt = storage.create_prompt("to_delete")
    prompt.add_version([("user", "v1")])
    prompt.add_prompt_tag("topic")

    deleted = storage.delete_prompt("to_delete")

    assert deleted == 1
    assert storage.repo.get_prompt_by_name("to_delete") is None

    versions = storage._conn.execute(
        "SELECT id FROM prompt_versions WHERE prompt_id = ?", (prompt.id,)
    ).fetchall()
    links = storage._conn.execute(
        "SELECT tag_id FROM prompt_tags WHERE prompt_id = ?", (prompt.id,)
    ).fetchall()

    assert versions == []
    assert links == []


@pytest.mark.integration
def test_uc04_002_delete_prompt_missing_raises_key_error(storage):
    with pytest.raises(KeyError, match="не найден"):
        storage.delete_prompt("missing")


@pytest.mark.integration
def test_uc05_005_list_prompts_returns_empty_list_for_empty_storage(storage):
    assert storage.list_prompts() == []


@pytest.mark.integration
def test_uc06_002_list_versions_returns_empty_for_prompt_without_versions(storage):
    prompt = storage.create_prompt("without_versions")
    assert prompt.list_versions() == []


@pytest.mark.integration
def test_uc09_001_add_prompt_tag_creates_link(storage):
    prompt = storage.create_prompt("taggable")
    prompt.add_prompt_tag("marketing")

    tag_names = {row["name"] for row in prompt.list_tags()}
    assert tag_names == {"marketing"}


@pytest.mark.integration
def test_uc09_002_add_prompt_tag_duplicate_warns_and_is_idempotent(storage):
    prompt = storage.create_prompt("taggable_dup")
    prompt.add_prompt_tag("marketing")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        prompt.add_prompt_tag("marketing")

    links = storage._conn.execute(
        "SELECT COUNT(*) FROM prompt_tags WHERE prompt_id = ?",
        (prompt.id,),
    ).fetchone()[0]

    assert links == 1
    assert any(
        "already" in str(x.message).lower() or "уже" in str(x.message).lower()
        for x in w
    )


@pytest.mark.integration
def test_uc10_001_remove_prompt_tag_deletes_existing_link(storage):
    prompt = storage.create_prompt("tag_remove")
    prompt.add_prompt_tag("obsolete")

    prompt.remove_prompt_tag("obsolete")

    tag_names = {row["name"] for row in prompt.list_tags()}
    assert "obsolete" not in tag_names


@pytest.mark.integration
def test_uc10_002_remove_prompt_tag_missing_warns(storage):
    prompt = storage.create_prompt("tag_remove_missing")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        prompt.remove_prompt_tag("missing")

    assert any("не привязан" in str(x.message) for x in w)


@pytest.mark.integration
def test_uc11_002_add_model_tags_duplicate_warns_and_returns_only_new(storage):
    TariffManager(storage._conn).bulk_upsert(
        [
            ModelTariff("model-a", input_price_per_1m=1.0, output_price_per_1m=2.0),
            ModelTariff("model-b", input_price_per_1m=1.0, output_price_per_1m=2.0),
        ]
    )

    storage.create_prompt("models_prompt")
    first_added = storage.add_model_tags("models_prompt", [_DummyModelTag("model-a")])

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        second_added = storage.add_model_tags(
            "models_prompt",
            [_DummyModelTag("model-a"), _DummyModelTag("model-b")],
        )

    prompt = storage.get_prompt("models_prompt")
    model_tags = {row["name"] for row in prompt.list_tags() if row["type"] == "model"}

    assert first_added == ["model-a"]
    assert second_added == ["model-b"]
    assert model_tags == {"model-a", "model-b"}
    assert any("дубликат" in str(x.message).lower() for x in w)


@pytest.mark.integration
def test_uc11_003_add_model_tags_without_tariff_warns_and_skips(storage):
    storage.create_prompt("models_without_tariff")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        added = storage.add_model_tags(
            "models_without_tariff", [_DummyModelTag("unknown-model")]
        )

    assert added == []
    assert any("нет тарифа" in str(x.message).lower() for x in w)


@pytest.mark.integration
def test_uc12_001_remove_model_tags_removes_existing_links(storage):
    TariffManager(storage._conn).bulk_upsert(
        [
            ModelTariff("model-x", input_price_per_1m=1.0, output_price_per_1m=2.0),
            ModelTariff("model-y", input_price_per_1m=1.0, output_price_per_1m=2.0),
        ]
    )

    storage.create_prompt("models_remove")
    storage.add_model_tags(
        "models_remove", [_DummyModelTag("model-x"), _DummyModelTag("model-y")]
    )

    removed = storage.remove_model_tags("models_remove", [_DummyModelTag("model-x")])

    model_rows = [
        row
        for row in storage.get_prompt("models_remove").list_tags()
        if row["type"] == "model"
    ]
    names = {row["name"] for row in model_rows}

    assert removed == ["model-x"]
    assert names == {"model-y"}


@pytest.mark.integration
def test_uc12_002_remove_model_tags_missing_warns_and_returns_empty(storage):
    storage.create_prompt("models_remove_missing")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        removed = storage.remove_model_tags(
            "models_remove_missing", [_DummyModelTag("model-z")]
        )

    assert removed == []
    assert any("не привязан" in str(x.message).lower() for x in w)


@pytest.mark.integration
def test_uc13_001_list_all_tags_returns_sorted_rows(storage):
    TariffManager(storage._conn).bulk_upsert(
        [
            ModelTariff("model-b", input_price_per_1m=1.0, output_price_per_1m=2.0),
            ModelTariff("model-a", input_price_per_1m=1.0, output_price_per_1m=2.0),
        ]
    )

    prompt = storage.create_prompt("all_tags")
    prompt.add_prompt_tag("zeta")
    prompt.add_prompt_tag("alpha")
    storage.add_model_tags(
        "all_tags", [_DummyModelTag("model-b"), _DummyModelTag("model-a")]
    )

    tags = storage.list_all_tags()

    assert [(t["type"], t["name"]) for t in tags] == [
        ("model", "model-a"),
        ("model", "model-b"),
        ("prompt", "alpha"),
        ("prompt", "zeta"),
    ]


@pytest.mark.integration
def test_uc13_002_list_all_tags_empty_returns_empty_list(storage):
    assert storage.list_all_tags() == []


@pytest.mark.integration
def test_uc14_001_search_by_tags_with_tagfilter(storage):
    p1 = storage.create_prompt("search_finance")
    p1.add_prompt_tag("finance")

    p2 = storage.create_prompt("search_legal")
    p2.add_prompt_tag("legal")

    result = storage.search_by_tags(TagFilter("finance"))

    assert {row["name"] for row in result} == {"search_finance"}


@pytest.mark.integration
def test_uc14_002_search_by_tags_supports_boolean_composition(storage):
    p1 = storage.create_prompt("bool_finance")
    p1.add_prompt_tag("finance")

    p2 = storage.create_prompt("bool_legal_deprecated")
    p2.add_prompt_tag("legal")
    p2.add_prompt_tag("deprecated")

    p3 = storage.create_prompt("bool_legal")
    p3.add_prompt_tag("legal")

    condition = (TagFilter("finance") | TagFilter("legal")) & ~TagFilter("deprecated")
    result = storage.search_by_tags(condition)

    assert {row["name"] for row in result} == {"bool_finance", "bool_legal"}


@pytest.mark.integration
def test_uc14_003_prompt_group_with_tag_and_without_tag(storage):
    p1 = storage.create_prompt("group_a")
    p1.add_version([("user", "A")])
    p1.add_prompt_tag("group")

    p2 = storage.create_prompt("group_b")
    p2.add_version([("user", "B")])

    with_group = storage.make_group_prompt().with_tag("group")
    without_group = storage.make_group_prompt().without_tag("group")

    with_rows = with_group.list_versions()
    without_rows = without_group.list_versions()

    assert {row["prompt_id"] for row in with_rows} == {p1.id}
    assert {row["prompt_id"] for row in without_rows} == {p2.id}


@pytest.mark.integration
def test_uc15_002_get_prompt_missing_raises_key_error(storage):
    with pytest.raises(KeyError, match="не найден"):
        storage.get_prompt("unknown")


@pytest.mark.integration
def test_uc16_004_fetch_prompt_returns_requested_version(storage):
    prompt = storage.create_prompt("fetch_specific")
    prompt.add_version([("user", "v1")])
    prompt.add_version([("user", "v2")])

    result = storage.fetch_prompt("fetch_specific", version=1)

    assert result.version == 1
    assert result.content == [("user", "v1")]


@pytest.mark.integration
def test_uc16_005_fetch_prompt_non_int_version_raises_type_error(storage):
    prompt = storage.create_prompt("fetch_type")
    prompt.add_version([("user", "v1")])

    with pytest.raises(TypeError, match="целым числом"):
        storage.fetch_prompt("fetch_type", version="1")


@pytest.mark.integration
def test_uc16_006_fetch_prompt_missing_prompt_raises_key_error(storage):
    with pytest.raises(KeyError, match="не найден"):
        storage.fetch_prompt("missing_prompt")


@pytest.mark.integration
def test_uc16_008_fetch_prompt_without_versions_raises_value_error(storage):
    storage.create_prompt("no_versions")

    with pytest.raises(ValueError, match="не имеет версий"):
        storage.fetch_prompt("no_versions")


@pytest.mark.integration
def test_uc17_001_update_tariffs_successfully_upserts(monkeypatch, storage):
    from prompthub.infrastructure.pricing_gateway import PricingAPIGateway

    def _fake_fetch(self):
        return [
            ModelTariff(
                "provider/model-1",
                input_price_per_1m=1.25,
                output_price_per_1m=2.5,
            )
        ]

    monkeypatch.setattr(PricingAPIGateway, "fetch_pricing_data", _fake_fetch)

    updated = storage.update_tariffs(url="https://example.invalid/models")

    row = storage._conn.execute(
        "SELECT tag_name, input_price_per_1m, output_price_per_1m FROM model_tariffs WHERE tag_name = ?",
        ("provider/model-1",),
    ).fetchone()

    assert updated == 1
    assert row is not None
    assert row["input_price_per_1m"] == pytest.approx(1.25)
    assert row["output_price_per_1m"] == pytest.approx(2.5)


@pytest.mark.integration
def test_uc17_002_update_tariffs_propagates_connection_error(monkeypatch, storage):
    from prompthub.infrastructure.pricing_gateway import PricingAPIGateway

    def _fake_fetch(self):
        raise ConnectionError("network down")

    monkeypatch.setattr(PricingAPIGateway, "fetch_pricing_data", _fake_fetch)

    with pytest.raises(ConnectionError, match="network down"):
        storage.update_tariffs()


@pytest.mark.integration
def test_uc17_003_update_tariffs_propagates_value_error(monkeypatch, storage):
    from prompthub.infrastructure.pricing_gateway import PricingAPIGateway

    def _fake_fetch(self):
        raise ValueError("bad payload")

    monkeypatch.setattr(PricingAPIGateway, "fetch_pricing_data", _fake_fetch)

    with pytest.raises(ValueError, match="bad payload"):
        storage.update_tariffs()


@pytest.mark.integration
def test_uc17_004_update_tariffs_propagates_runtime_error(monkeypatch, storage):
    from prompthub.infrastructure.pricing_gateway import PricingAPIGateway
    from prompthub.infrastructure.tariff_manager import TariffManager

    def _fake_fetch(self):
        return [
            ModelTariff(
                "provider/model-2",
                input_price_per_1m=1.0,
                output_price_per_1m=2.0,
            )
        ]

    def _fake_bulk_upsert(self, tariffs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(PricingAPIGateway, "fetch_pricing_data", _fake_fetch)
    monkeypatch.setattr(TariffManager, "bulk_upsert", _fake_bulk_upsert)

    with pytest.raises(RuntimeError, match="write failed"):
        storage.update_tariffs()
