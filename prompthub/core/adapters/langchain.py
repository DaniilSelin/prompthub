from typing import Any

from prompthub.core.adapters.base import LLMAdapter
from prompthub.core.domain.prompt_messages import PromptMessages


class LangChainAdapter(LLMAdapter):
    """Адаптер формата LangChain messages."""

    @staticmethod
    def _import_langchain_messages():
        try:
            from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
        except ImportError as exc:
            raise ImportError(
                "Для adapter_type='langchain' установите пакет 'langchain-core'."
            ) from exc
        return AIMessage, HumanMessage, SystemMessage

    def serialize(self, prompt: PromptMessages) -> list[Any]:
        AIMessage, HumanMessage, SystemMessage = self._import_langchain_messages()

        role_map = {
            "system": SystemMessage,
            "user": HumanMessage,
            "assistant": AIMessage,
        }

        result: list[Any] = []
        for role, content in prompt.content:
            cls = role_map.get(role)
            if cls is None:
                raise ValueError(f"Неподдерживаемая роль для LangChain: {role}")
            result.append(cls(content=content))

        return result

    def deserialize(
        self,
        payload: Any,
        *,
        name: str = "imported_prompt",
        version: int = 1,
    ) -> PromptMessages:
        if not isinstance(payload, list):
            raise TypeError("LangChain payload должен быть списком сообщений")

        content: list[tuple[str, str]] = []
        for idx, item in enumerate(payload):
            role: str | None = None
            text: str | None = None

            if isinstance(item, dict):
                role = item.get("role")
                text = item.get("content")
            else:
                message_type = getattr(item, "type", None)
                if message_type == "system":
                    role = "system"
                elif message_type == "human":
                    role = "user"
                elif message_type == "ai":
                    role = "assistant"

                text = getattr(item, "content", None)

            if not isinstance(role, str) or not isinstance(text, str):
                raise ValueError(f"Некорректное LangChain-сообщение #{idx}")

            content.append((role, text))

        return PromptMessages(name=name, version=version, content=content)
