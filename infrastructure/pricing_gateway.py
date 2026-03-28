import json
import urllib.request
import urllib.error

from core.domain.model_tariff import ModelTariff

# Формат ответа: {"data": [{"id": "model-id", "pricing": {"prompt": "0.0001", "completion": "0.0002"}}, ...]}
DEFAULT_PRICING_URL = "https://openrouter.ai/api/v1/models"


class PricingAPIGateway:
    def __init__(self, url: str = DEFAULT_PRICING_URL, timeout: int = 10):
        self.url = url
        self.timeout = timeout

    def fetch_pricing_data(self) -> list[ModelTariff]:
        try:
            with urllib.request.urlopen(self.url, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except (urllib.error.URLError, OSError) as e:
            raise ConnectionError(f"Внешний источник недоступен: {e}") from e

        try:
            data = json.loads(raw)
            return self._parse(data)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise ValueError(f"Невалидный формат ответа API: {e}") from e

    def _parse(self, data: dict) -> list[ModelTariff]:
        items = data.get("data")
        if not isinstance(items, list):
            raise ValueError("Ожидался список моделей в поле 'data'")

        result = []
        for item in items:
            tag_name = item["id"]
            pricing = item.get("pricing", {})
            result.append(
                ModelTariff(
                    tag_name=tag_name,
                    input_price_per_1k=float(pricing.get("prompt", 0.0)),
                    output_price_per_1k=float(pricing.get("completion", 0.0)),
                )
            )
        return result
