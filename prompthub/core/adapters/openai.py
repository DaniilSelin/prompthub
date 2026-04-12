from typing import Any

from prompthub.core.adapters.base import LLMAdapter
from prompthub.core.domain.prompt_messages import PromptMessages


class OpenAIAdapter(LLMAdapter):
    """Адаптер формата OpenAI Chat Completions API."""

    def serialize(self, prompt: PromptMessages) -> list[dict[str, str]]:
        return [{"role": role, "content": content} for role, content in prompt.content]

    def deserialize(
        self,
        payload: Any,
        *,
        name: str = "imported_prompt",
        version: int = 1,
    ) -> PromptMessages:
        if not isinstance(payload, list):
            raise TypeError("OpenAI payload должен быть списком сообщений")

        content: list[tuple[str, str]] = []
        for idx, item in enumerate(payload):
            if not isinstance(item, dict):
                raise TypeError(f"Сообщение #{idx} должно быть словарем")

            role = item.get("role")
            text = item.get("content")
            if not isinstance(role, str) or not isinstance(text, str):
                raise ValueError(f"Некорректное сообщение #{idx}: role/content обязательны")

            content.append((role, text))

        return PromptMessages(name=name, version=version, content=content)
