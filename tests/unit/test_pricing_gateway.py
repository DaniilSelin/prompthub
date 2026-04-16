"""
Юнит-тесты для PricingAPIGateway - парсинг цен OpenRouter.
Покрывает: конвертацию per-token -> per-1M, извлечение провайдера, обработку ошибок.
"""

import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from prompthub.infrastructure.pricing_gateway import PricingAPIGateway


@pytest.fixture
def gateway():
    return PricingAPIGateway()


# ---------------------------------------------------------------------------
# _parse: конвертация цен
# ---------------------------------------------------------------------------


class TestParse:

    def _data(self, *models):
        return {"data": list(models)}

    def _model(self, id_, prompt, completion):
        return {
            "id": id_,
            "pricing": {"prompt": str(prompt), "completion": str(completion)},
        }

    def test_converts_per_token_to_per_1m_input(self, gateway):
        data = self._data(self._model("openai/gpt-4o", "0.0000025", "0.00001"))
        result = gateway._parse(data)
        assert result[0].input_price_per_1m == pytest.approx(2.5)

    def test_converts_per_token_to_per_1m_output(self, gateway):
        data = self._data(self._model("openai/gpt-4o", "0.0000025", "0.00001"))
        result = gateway._parse(data)
        assert result[0].output_price_per_1m == pytest.approx(10.0)

    def test_sets_tag_name_from_model_id(self, gateway):
        data = self._data(self._model("openai/gpt-4o-mini", "0.00000015", "0.0000006"))
        result = gateway._parse(data)
        assert result[0].tag_name == "openai/gpt-4o-mini"

    def test_normalizes_tag_name_to_lowercase(self, gateway):
        data = self._data(self._model("OpenAI/GPT-4O", "0.0000025", "0.00001"))
        result = gateway._parse(data)
        assert result[0].tag_name == "openai/gpt-4o"

    def test_normalizes_tag_name_strips_whitespace(self, gateway):
        data = self._data(self._model("  openai/gpt-4o  ", "0.0000025", "0.00001"))
        result = gateway._parse(data)
        assert result[0].tag_name == "openai/gpt-4o"

    def test_parses_multiple_models(self, gateway):
        data = self._data(
            self._model("openai/gpt-4o", "0.0000025", "0.00001"),
            self._model("openai/gpt-4o-mini", "0.00000015", "0.0000006"),
        )
        result = gateway._parse(data)
        assert len(result) == 2

    def test_handles_zero_pricing(self, gateway):
        data = self._data(
            {"id": "some/free-model", "pricing": {"prompt": "0", "completion": "0"}}
        )
        result = gateway._parse(data)
        assert len(result) == 1
        assert result[0].input_price_per_1m == 0.0

    def test_handles_missing_pricing_field(self, gateway):
        data = self._data({"id": "some/model"})
        result = gateway._parse(data)
        assert len(result) == 1
        assert result[0].input_price_per_1m == 0.0
        assert result[0].output_price_per_1m == 0.0

    def test_skips_model_with_non_numeric_pricing(self, gateway):
        data = self._data(
            {"id": "bad/model", "pricing": {"prompt": "free", "completion": "free"}},
            self._model("good/model", "0.000001", "0.000002"),
        )
        result = gateway._parse(data)
        assert len(result) == 1
        assert result[0].tag_name == "good/model"

    def test_raises_value_error_if_data_field_missing(self, gateway):
        with pytest.raises(ValueError, match="список моделей"):
            gateway._parse({"models": []})

    def test_raises_value_error_if_data_is_not_list(self, gateway):
        with pytest.raises(ValueError, match="список моделей"):
            gateway._parse({"data": "not-a-list"})


# ---------------------------------------------------------------------------
# fetch_pricing_data: сетевой слой
# ---------------------------------------------------------------------------


class TestFetchPricingData:

    def test_raises_connection_error_on_network_failure(self, gateway):
        with patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")
        ):
            with pytest.raises(ConnectionError, match="недоступен"):
                gateway.fetch_pricing_data()

    def test_raises_value_error_on_invalid_json(self, gateway):
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = b"not json {"

        with patch("urllib.request.urlopen", return_value=mock_response):
            with pytest.raises(ValueError, match="Невалидный формат"):
                gateway.fetch_pricing_data()

    def test_parses_real_response_format(self, gateway):
        payload = json.dumps(
            {
                "data": [
                    {
                        "id": "openai/gpt-4o",
                        "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
                    },
                    {
                        "id": "anthropic/claude-3-5-sonnet",
                        "pricing": {"prompt": "0.000003", "completion": "0.000015"},
                    },
                ]
            }
        ).encode()

        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.read.return_value = payload

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = gateway.fetch_pricing_data()

        assert len(result) == 2
        gpt = next(t for t in result if t.tag_name == "openai/gpt-4o")
        assert gpt.input_price_per_1m == pytest.approx(2.5)
