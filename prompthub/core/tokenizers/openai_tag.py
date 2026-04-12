import os
import warnings
from typing import Any

from prompthub.core.tokenizers.base import Messages, ModelTag


class OpenAIModelTag(ModelTag):
    """Подсчёт токенов для моделей OpenAI через официальный SDK-клиент.

    Использует client.beta.chat.completions.count_tokens() — канонический
    способ, рекомендованный OpenAI, учитывающий overhead формата сообщений.

    Требует установленного пакета `openai` и переменной окружения OPENAI_API_KEY.
    При отсутствии любого из них get_token_count вернёт -1 и выдаст предупреждение.
    """

    provider_key = "openai"

    def __init__(self, model_name: str = "gpt-4o"):
        super().__init__(model_name)
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ImportError(
                    "Для OpenAIModelTag установите пакет 'openai': pip install openai"
                ) from exc

            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise EnvironmentError(
                    "OPENAI_API_KEY не найден в переменных окружения. "
                    "Установите переменную окружения OPENAI_API_KEY перед использованием OpenAIModelTag: "
                    "export OPENAI_API_KEY='your-api-key'"
                )

            self._client = OpenAI(api_key=api_key)
        return self._client

    def _count_text(self, text: str) -> int:
        raise NotImplementedError(
            "OpenAIModelTag считает токены на уровне сообщений через SDK-клиент, "
            "а не построчно. Используйте get_token_count."
        )

    def get_token_count(self, messages: Messages) -> int:
        """Считает токены через OpenAI SDK (beta.chat.completions.count_tokens).

        При отсутствии пакета `openai`, OPENAI_API_KEY или другой ошибке
        выдаёт предупреждение и возвращает -1.
        """
        try:
            client = self._get_client()
            response = client.beta.chat.completions.count_tokens(
                model=self.model_name,
                messages=[
                    {"role": role, "content": content} for role, content in messages
                ],
            )
            return int(response.total_tokens)
        except Exception as e:
            warnings.warn(
                f"[{self.__class__.__name__}:{self.model_name}] "
                f"ошибка подсчёта токенов: {e}"
            )
            return -1
