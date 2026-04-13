import json
import urllib.error
import urllib.request
from typing import Any

from prompthub.core.domain.model_tariff import ModelTariff

# OpenRouter отдаёт цены за токен (например 0.0000025 для GPT-4o input).
# Умножаем на 1_000_000 чтобы получить цену за 1M токенов ($2.50).
# Формат ответа:
# {
#   "data": [
#     {
#       "id": "openai/gpt-4o",
#       "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
#       ...
#     },
#     ...
#   ]
# }
DEFAULT_PRICING_URL = "https://openrouter.ai/api/v1/models"
_PER_TOKEN_TO_PER_1M = 1_000_000


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

    def _parse(self, data: dict[str, Any]) -> list[ModelTariff]:
        items = data.get("data")
        if not isinstance(items, list):
            raise ValueError("Ожидался список моделей в поле 'data'")

        result = []
        for item in items:
            model_id = item.get("id", "")
            pricing = item.get("pricing") or {}

            # OpenRouter: значения — строки с ценой за токен в USD.
            # Пропускаем модели с нулевой или отсутствующей ценой (бесплатные / без данных).
            try:
                input_per_token = float(pricing.get("prompt") or 0)
                output_per_token = float(pricing.get("completion") or 0)
            except (ValueError, TypeError):
                continue

            result.append(
                ModelTariff(
                    tag_name=model_id,
                    input_price_per_1m=round(input_per_token * _PER_TOKEN_TO_PER_1M, 6),
                    output_price_per_1m=round(
                        output_per_token * _PER_TOKEN_TO_PER_1M, 6
                    ),
                )
            )

        return result
