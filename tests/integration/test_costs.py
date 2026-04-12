"""
Интеграционные тесты для подсчёта стоимости промптов.
Покрывает: per-model token_count, per-model cost, отсутствие тарифа, отсутствие токенизатора.
"""

import warnings

import pytest

import prompthub.core.tokenizers.registry as reg
from prompthub.core.domain.model_tariff import ModelTariff
from prompthub.core.tokenizers.base import ModelTag
from prompthub.facade.storage import Storage
from prompthub.infrastructure.tariff_manager import TariffManager

# ---------------------------------------------------------------------------
# Вспомогательные классы и фикстуры
# ---------------------------------------------------------------------------


class _Fixed100Tag(ModelTag):
    """Токенизатор, всегда возвращающий 100 токенов."""

    provider_key = "fixed-100"

    def _count_text(self, text: str) -> int:
        return 100


class _Fixed200Tag(ModelTag):
    """Токенизатор, всегда возвращающий 200 токенов."""

    provider_key = "fixed-200"

    def _count_text(self, text: str) -> int:
        return 200


class _Fixed1000Tag(ModelTag):
    """Токенизатор, всегда возвращающий 1000 токенов."""

    provider_key = "fixed-1000"

    def _count_text(self, text: str) -> int:
        return 1000


class _Fixed500Tag(ModelTag):
    """Токенизатор, всегда возвращающий 500 токенов."""

    provider_key = "fixed-500"

    def _count_text(self, text: str) -> int:
        return 500


class _Fixed42Tag(ModelTag):
    provider_key = "fixed-42"

    def _count_text(self, text: str) -> int:
        return 42


class _Fixed999Tag(ModelTag):
    provider_key = "fixed-999"

    def _count_text(self, text: str) -> int:
        return 999


class _Fixed10Tag(ModelTag):
    provider_key = "fixed-10"

    def _count_text(self, text: str) -> int:
        return 10


@pytest.fixture(autouse=True)
def inject_test_providers(monkeypatch):
    """Добавляем тестовые провайдеры в реестр, не трогая production-провайдеры."""
    for key, cls in [
        ("fixed-100", _Fixed100Tag),
        ("fixed-200", _Fixed200Tag),
        ("fixed-1000", _Fixed1000Tag),
        ("fixed-500", _Fixed500Tag),
        ("fixed-42", _Fixed42Tag),
        ("fixed-999", _Fixed999Tag),
        ("fixed-10", _Fixed10Tag),
    ]:
        monkeypatch.setitem(reg._PROVIDER_REGISTRY, key, cls)


@pytest.fixture
def storage(tmp_path):
    s = Storage(str(tmp_path / "costs.sqlite3"))
    yield s
    s._conn.close()


def _upsert(storage: Storage, *tariffs: ModelTariff) -> None:
    TariffManager(storage._conn).bulk_upsert(list(tariffs))


# ---------------------------------------------------------------------------
# TC-COST-01: каждая модель считает токены своим токенизатором
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_each_model_uses_own_tokenizer(storage):
    _upsert(
        storage,
        ModelTariff(
            "model-a", "fixed-100", input_price_per_1m=1.0, output_price_per_1m=2.0
        ),
        ModelTariff(
            "model-b", "fixed-200", input_price_per_1m=1.0, output_price_per_1m=2.0
        ),
    )

    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello")])
    storage.add_model_tags("p", [_Fixed100Tag("model-a"), _Fixed200Tag("model-b")])

    data = storage.list_prompts()
    costs = data[0]["costs"]

    assert costs["model-a"]["token_count"] == 100
    assert costs["model-b"]["token_count"] == 200


# ---------------------------------------------------------------------------
# TC-COST-02: цена вычисляется из токенов конкретной модели
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_cost_computed_from_own_token_count(storage):
    _upsert(
        storage,
        ModelTariff(
            "cheap-model", "fixed-1000", input_price_per_1m=1.0, output_price_per_1m=2.0
        ),
        ModelTariff(
            "expensive-model",
            "fixed-500",
            input_price_per_1m=10.0,
            output_price_per_1m=20.0,
        ),
    )

    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello")])
    storage.add_model_tags(
        "p", [_Fixed1000Tag("cheap-model"), _Fixed500Tag("expensive-model")]
    )

    data = storage.list_prompts()
    costs = data[0]["costs"]

    # cheap-model:     1000 / 1_000_000 * 1.0  = 0.001
    # expensive-model: 500  / 1_000_000 * 10.0 = 0.005
    assert costs["cheap-model"]["cost"] == pytest.approx(0.001)
    assert costs["expensive-model"]["cost"] == pytest.approx(0.005)


# ---------------------------------------------------------------------------
# TC-COST-03: отсутствие тарифа → cost=None, token_count есть
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_missing_tariff_gives_none_cost_but_has_token_count(storage):
    """Тариф удалён после привязки тега — cost=None, token_count сохраняется."""
    _upsert(
        storage,
        ModelTariff(
            "no-tariff-model",
            "fixed-42",
            input_price_per_1m=1.0,
            output_price_per_1m=2.0,
        ),
    )
    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello")])
    storage.add_model_tags("p", [_Fixed42Tag("no-tariff-model")])

    # Удаляем тариф — имитируем ситуацию устаревших данных
    storage._conn.execute(
        "DELETE FROM model_tariffs WHERE tag_name = 'no-tariff-model'"
    )
    storage._conn.commit()

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        data = storage.list_prompts()

    model_info = data[0]["costs"]["no-tariff-model"]
    assert model_info["token_count"] == 42
    assert model_info["cost"] is None
    assert any("no-tariff-model" in str(x.message) for x in w)


# ---------------------------------------------------------------------------
# TC-COST-04: отсутствие токенизатора → word-count fallback + предупреждение
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_missing_tokenizer_falls_back_to_word_count(storage):
    _upsert(
        storage,
        ModelTariff(
            "unknown-model",
            "unknown-provider",
            input_price_per_1m=2.0,
            output_price_per_1m=4.0,
        ),
    )

    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello world"), ("system", "be helpful")])

    # Создаём ModelTag с неизвестным провайдером для теста
    class _UnknownProviderTag(ModelTag):
        provider_key = "unknown-provider"

        def _count_text(self, text: str) -> int:
            return 0  # не будет вызван

    storage.add_model_tags("p", [_UnknownProviderTag("unknown-model")])

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        data = storage.list_prompts()

    model_info = data[0]["costs"]["unknown-model"]
    # "hello world" (2) + "be helpful" (2) = 4 слова
    assert model_info["token_count"] == 4
    assert model_info["cost"] is not None
    assert any("unknown-model" in str(x.message) for x in w)


# ---------------------------------------------------------------------------
# TC-COST-05: промпт без model_tags → costs = None
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_prompt_without_model_tags_has_none_costs(storage):
    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello")])

    data = storage.list_prompts()
    assert data[0]["costs"] is None


# ---------------------------------------------------------------------------
# TC-COST-06: промпт без версий → нулевые токены и нулевая стоимость
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_prompt_without_versions_has_zero_cost(storage):
    _upsert(
        storage,
        ModelTariff(
            "some-model", "fixed-999", input_price_per_1m=5.0, output_price_per_1m=10.0
        ),
    )

    storage.create_prompt("p")
    storage.add_model_tags("p", [_Fixed999Tag("some-model")])

    data = storage.list_prompts()
    model_info = data[0]["costs"]["some-model"]
    assert model_info["token_count"] == 0
    assert model_info["cost"] == 0.0


# ---------------------------------------------------------------------------
# TC-COST-07: несколько промптов — каждый считается независимо
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_multiple_prompts_counted_independently(storage):
    _upsert(
        storage,
        ModelTariff(
            "model-x", "fixed-10", input_price_per_1m=1.0, output_price_per_1m=2.0
        ),
    )

    for i in range(3):
        p = storage.create_prompt(f"prompt-{i}")
        p.add_version([("user", f"content {i}")])
        storage.add_model_tags(f"prompt-{i}", [_Fixed10Tag("model-x")])

    data = storage.list_prompts()
    assert len(data) == 3
    for entry in data:
        assert entry["costs"]["model-x"]["token_count"] == 10
