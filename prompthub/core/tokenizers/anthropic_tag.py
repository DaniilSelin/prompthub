import os
import warnings
from typing import cast

from prompthub.core.tokenizers.base import Messages, ModelTag


class AnthropicModelTag(ModelTag):
    """Подсчёт токенов для моделей Anthropic (Claude) через официальный SDK.

    Требует установленного пакета `anthropic` и переменной окружения
    ANTHROPIC_API_KEY. При отсутствии любого из них get_token_count вернёт -1
    и выдаст предупреждение (стандартное поведение базового класса).

    Использует messages.count_tokens — официальный API Anthropic, который
    учитывает overhead формата (роли, разделители).
    """

    provider_key = "anthropic"

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022"):
        super().__init__(model_name)

    def _count_text(self, text: str) -> int:
        raise NotImplementedError(
            "AnthropicModelTag считает токены на уровне сообщений через SDK, "
            "а не построчно. Используйте get_token_count."
        )

    def get_token_count(self, messages: Messages) -> int:
        """Считает токены через Anthropic SDK (messages.count_tokens).

        При отсутствии ANTHROPIC_API_KEY, пакета `anthropic`, недоступном API
        или другой ошибке выдаёт предупреждение и возвращает -1.
        """
        try:
            import anthropic

            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "ANTHROPIC_API_KEY не найден в переменных окружения. "
                    "Установите переменную окружения ANTHROPIC_API_KEY перед использованием AnthropicModelTag: "
                    "export ANTHROPIC_API_KEY='your-api-key'"
                )

            client = anthropic.Anthropic(api_key=api_key)
            response = client.messages.count_tokens(
                model=self.model_name,
                messages=[
                    {"role": role, "content": content} for role, content in messages
                ],
            )
            return cast(int, response.input_tokens)
        except Exception as e:
            warnings.warn(
                f"[{self.__class__.__name__}:{self.model_name}] "
                f"ошибка подсчёта токенов: {e}"
            )
            return -1
