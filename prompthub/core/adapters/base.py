from abc import ABC, abstractmethod
from typing import Any

from prompthub.core.domain.prompt_messages import PromptMessages


class LLMAdapter(ABC):
    @abstractmethod
    def serialize(self, prompt: PromptMessages) -> Any:
        """Преобразует PromptMessages во внешний формат фреймворка."""

    @abstractmethod
    def deserialize(
        self,
        payload: Any,
        *,
        name: str = "imported_prompt",
        version: int = 1,
    ) -> PromptMessages:
        """Преобразует внешний формат фреймворка обратно в PromptMessages."""

    def convert(self, prompt: PromptMessages) -> Any:
        """Совместимость со старым API: convert == serialize."""
        return self.serialize(prompt)
