"""
Интеграционные тесты для подсчёта стоимости промптов.
Покрывает: per-model token_count, per-model cost, отсутствие тарифа, отсутствие токенизатора.
"""
import warnings
import pytest

from prompthub.facade.storage import Storage
from prompthub.core.tokenizers.base import ModelTag
from prompthub.core.domain.model_tariff import ModelTariff
from prompthub.infrastructure.tariff_manager import TariffManager
import prompthub.core.tokenizers.registry as reg


# ---------------------------------------------------------------------------
# Вспомогательные классы и фикстуры
# ---------------------------------------------------------------------------

class _FixedTag(ModelTag):
    """Токенизатор с фиксированным числом токенов — предсказуемый для тестов."""
    def __init__(self, token_count: int, name: str = "fixed"):
        super().__init__(name)
        self._n = token_count

    def _count_text(self, text: str) -> int:
        return self._n


@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    monkeypatch.setattr(reg, "_registry", {})


@pytest.fixture
def storage(tmp_path):
    s = Storage(str(tmp_path / "costs.sqlite3"))
    yield s
    s._conn.close()


def _upsert(storage, *tariffs: ModelTariff):
    TariffManager(storage._conn).bulk_upsert(list(tariffs))


# ---------------------------------------------------------------------------
# TC-COST-01: каждая модель считает токены своим токенизатором
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_each_model_uses_own_tokenizer(storage):
    reg.register("model-a", _FixedTag(100, "model-a"))
    reg.register("model-b", _FixedTag(200, "model-b"))

    _upsert(
        storage,
        ModelTariff("model-a", "provider-a", input_price_per_1m=1.0, output_price_per_1m=2.0),
        ModelTariff("model-b", "provider-b", input_price_per_1m=1.0, output_price_per_1m=2.0),
    )

    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello")], name="v1")
    storage.add_model_tags("p", ["model-a", "model-b"])

    data = storage.list_prompts()
    costs = data[0]["costs"]

    assert costs["model-a"]["token_count"] == 100
    assert costs["model-b"]["token_count"] == 200


# ---------------------------------------------------------------------------
# TC-COST-02: цена вычисляется из токенов конкретной модели
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_cost_computed_from_own_token_count(storage):
    reg.register("cheap-model", _FixedTag(1000, "cheap"))
    reg.register("expensive-model", _FixedTag(500, "expensive"))

    _upsert(
        storage,
        ModelTariff("cheap-model",     "p", input_price_per_1m=1.0,  output_price_per_1m=2.0),
        ModelTariff("expensive-model",  "p", input_price_per_1m=10.0, output_price_per_1m=20.0),
    )

    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello")], name="v1")
    storage.add_model_tags("p", ["cheap-model", "expensive-model"])

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
    reg.register("no-tariff-model", _FixedTag(42, "no-tariff"))

    # Сначала регистрируем тариф и привязываем тег нормальным путём
    _upsert(
        storage,
        ModelTariff("no-tariff-model", "p", input_price_per_1m=1.0, output_price_per_1m=2.0),
    )
    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello")], name="v1")
    storage.add_model_tags("p", ["no-tariff-model"])

    # Удаляем тариф — имитируем ситуацию устаревших данных
    storage._conn.execute("DELETE FROM model_tariffs WHERE tag_name = 'no-tariff-model'")
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
        ModelTariff("unknown-model", "p", input_price_per_1m=2.0, output_price_per_1m=4.0),
    )

    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello world"), ("system", "be helpful")], name="v1")
    storage.add_model_tags("p", ["unknown-model"])

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        data = storage.list_prompts()

    model_info = data[0]["costs"]["unknown-model"]
    # "hello world" (2) + "be helpful" (2) = 4 слова
    assert model_info["token_count"] == 4
    assert model_info["cost"] is not None
    assert any("unknown-model" in str(x.message) for x in w)


# ---------------------------------------------------------------------------
# TC-COST-05: промпт без model_tags → пустой costs
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_prompt_without_model_tags_has_empty_costs(storage):
    prompt = storage.create_prompt("p")
    prompt.add_version([("user", "hello")], name="v1")

    data = storage.list_prompts()
    assert data[0]["costs"] == {}


# ---------------------------------------------------------------------------
# TC-COST-06: промпт без версий → нулевые токены и нулевая стоимость
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_prompt_without_versions_has_zero_cost(storage):
    reg.register("some-model", _FixedTag(999, "some"))
    _upsert(
        storage,
        ModelTariff("some-model", "p", input_price_per_1m=5.0, output_price_per_1m=10.0),
    )

    storage.create_prompt("p")
    storage.add_model_tags("p", ["some-model"])

    data = storage.list_prompts()
    model_info = data[0]["costs"]["some-model"]
    assert model_info["token_count"] == 0
    assert model_info["cost"] == 0.0


# ---------------------------------------------------------------------------
# TC-COST-07: несколько промптов — каждый считается независимо
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_multiple_prompts_counted_independently(storage):
    reg.register("model-x", _FixedTag(10, "x"))
    _upsert(
        storage,
        ModelTariff("model-x", "p", input_price_per_1m=1.0, output_price_per_1m=2.0),
    )

    for i in range(3):
        p = storage.create_prompt(f"prompt-{i}")
        p.add_version([("user", f"content {i}")], name="v1")
        storage.add_model_tags(f"prompt-{i}", ["model-x"])

    data = storage.list_prompts()
    assert len(data) == 3
    for entry in data:
        assert entry["costs"]["model-x"]["token_count"] == 10
