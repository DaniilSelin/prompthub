from __future__ import annotations

from typing import TYPE_CHECKING, Any

from prompthub.core.adapters.langchain import LangChainAdapter
from prompthub.core.domain.prompt_messages import PromptMessages
from prompthub.facade.prompt import Prompt, PromptVersion
from prompthub.repository.types import TagRow

if TYPE_CHECKING:
    from prompthub.core.domain.diff import StructuredDiff, VersionDiff, VersionLineDiff
    from prompthub.core.domain.tag import PromptTag
    from prompthub.core.tokenizers.base import ModelTag


class LangChainPromptAdapter:
    """Proxy-декоратор над Prompt для работы с LangChain.

    Все методы делегируются оборачиваемому Prompt. Методы, возвращающие
    контент версии, автоматически конвертируют его в ChatPromptTemplate.
    Метод add_version принимает как ChatPromptTemplate, так и сырые туплы.

    Пример использования:
        from prompthub.adapters import LangChainPromptAdapter

        prompt = storage.get_prompt("my-prompt")
        lc = LangChainPromptAdapter(prompt)

        template = lc.get_version_content(1)   # -> ChatPromptTemplate
        lc.add_version(template)               # <- ChatPromptTemplate
    """

    def __init__(self, prompt: Prompt) -> None:
        self._prompt = prompt
        self._adapter = LangChainAdapter()

    # ------------------------------------------------------------------
    # Методы с конвертацией контента
    # ------------------------------------------------------------------

    def get_version_content(self, version_seq: int) -> Any:
        """Возвращает контент версии как ChatPromptTemplate."""
        raw = self._prompt.get_version_content(version_seq)
        return self._adapter.serialize(
            PromptMessages(name="", version=version_seq, content=raw)
        )

    def add_version(
        self,
        content: Any,
        description: str | None = None,
        commit: bool = True,
    ) -> int:
        """Добавляет новую версию.

        Принимает ChatPromptTemplate или list[tuple[str, str]].
        ChatPromptTemplate конвертируется обратно в сырой формат.
        """
        if _is_chat_prompt_template(content):
            pm = self._adapter.deserialize(content)
            raw = pm.content
        else:
            raw = content
        return self._prompt.add_version(raw, description, commit=commit)

    # ------------------------------------------------------------------
    # Делегирование — версии
    # ------------------------------------------------------------------

    def list_versions(self) -> list[PromptVersion]:
        return self._prompt.list_versions()

    def rollback(
        self,
        target_seq: int | None = None,
        steps_back: int | None = None,
        description: str | None = None,
    ) -> int:
        return self._prompt.rollback(
            target_seq=target_seq,
            steps_back=steps_back,
            description=description,
        )

    def rollback_hard(
        self,
        target_seq: int | None = None,
        steps_back: int | None = None,
    ) -> PromptVersion:
        return self._prompt.rollback_hard(target_seq=target_seq, steps_back=steps_back)

    # ------------------------------------------------------------------
    # Делегирование — сравнение версий
    # ------------------------------------------------------------------

    def compare_versions(self, seq_a: int, seq_b: int) -> "VersionLineDiff":
        return self._prompt.compare_versions(seq_a, seq_b)

    def compare_versions_chars(self, seq_a: int, seq_b: int) -> "VersionDiff":
        return self._prompt.compare_versions_chars(seq_a, seq_b)

    def compare_versions_structured(self, seq_a: int, seq_b: int) -> "StructuredDiff":
        return self._prompt.compare_versions_structured(seq_a, seq_b)

    # ------------------------------------------------------------------
    # Делегирование — теги
    # ------------------------------------------------------------------

    def list_tags(self) -> list[TagRow]:
        return self._prompt.list_tags()

    def add_prompt_tag(self, tag: "PromptTag | str", commit: bool = True) -> None:
        self._prompt.add_prompt_tag(tag, commit=commit)

    def remove_prompt_tag(self, tag: "PromptTag | str", commit: bool = True) -> None:
        self._prompt.remove_prompt_tag(tag, commit=commit)

    def add_model_tag(self, model_tag: "ModelTag") -> None:
        return self._prompt.add_model_tag(model_tag)

    def remove_model_tag(self, model_tag: "ModelTag") -> None:
        return self._prompt.remove_model_tag(model_tag)

    # ------------------------------------------------------------------
    # Свойства
    # ------------------------------------------------------------------

    @property
    def id(self) -> int:
        return self._prompt.id

    def __repr__(self) -> str:
        return f"<LangChainPromptAdapter prompt_id={self._prompt.id}>"


def _is_chat_prompt_template(obj: Any) -> bool:
    """Проверяет, является ли объект ChatPromptTemplate (без жёсткого импорта)."""
    cls_name = type(obj).__name__
    return cls_name == "ChatPromptTemplate"
