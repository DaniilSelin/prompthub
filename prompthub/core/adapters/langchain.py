from typing import Any

from prompthub.core.adapters.base import LLMAdapter
from prompthub.core.domain.prompt_messages import PromptMessages


class LangChainAdapter(LLMAdapter):
    """Адаптер для LangChain - конвертирует PromptMessages в ChatPromptTemplate.

    Использует ChatPromptTemplate.from_messages() с кортежами (role, content),
    без явного импорта конкретных классов AIMessage/HumanMessage/SystemMessage.
    """

    @staticmethod
    def _import_chat_prompt_template() -> Any:
        try:
            from langchain_core.prompts import ChatPromptTemplate
        except ImportError as exc:
            raise ImportError(
                "Для LangChainAdapter установите пакет 'langchain-core': "
                "pip install langchain-core"
            ) from exc
        return ChatPromptTemplate

    def serialize(self, prompt: PromptMessages) -> Any:
        ChatPromptTemplate = self._import_chat_prompt_template()
        return ChatPromptTemplate.from_messages(prompt.content)

    def deserialize(
        self,
        payload: Any,
        *,
        name: str = "imported_prompt",
        version: int = 1,
    ) -> PromptMessages:
        self._import_chat_prompt_template()  # проверяем наличие langchain-core

        content: list[tuple[str, str]] = []

        is_template = (
            not isinstance(payload, list)
            and hasattr(payload, "format_messages")
            and callable(payload.format_messages)
        )

        if is_template:
            messages = payload.format_messages()
            _type_to_role = {
                "system": "system",
                "human": "user",
                "ai": "assistant",
            }
            for idx, msg in enumerate(messages):
                msg_type = getattr(msg, "type", None)
                role = _type_to_role.get(msg_type, msg_type)
                text = getattr(msg, "content", None)
                if not isinstance(role, str) or not isinstance(text, str):
                    raise ValueError(
                        f"Некорректное сообщение ChatPromptTemplate #{idx}"
                    )
                content.append((role, text))

        elif isinstance(payload, list):
            for idx, item in enumerate(payload):
                if isinstance(item, tuple) and len(item) == 2:
                    role, text = item
                elif isinstance(item, dict):
                    role = item.get("role")
                    text = item.get("content")
                else:
                    msg_type = getattr(item, "type", None)
                    _type_to_role = {
                        "system": "system",
                        "human": "user",
                        "ai": "assistant",
                    }
                    role = _type_to_role.get(msg_type, msg_type)
                    text = getattr(item, "content", None)

                if not isinstance(role, str) or not isinstance(text, str):
                    raise ValueError(f"Некорректное LangChain-сообщение #{idx}")
                content.append((role, text))

        else:
            raise TypeError(
                "LangChain payload должен быть ChatPromptTemplate или списком сообщений"
            )

        return PromptMessages(name=name, version=version, content=content)
