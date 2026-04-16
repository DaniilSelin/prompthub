from abc import ABC, abstractmethod
from typing import Any

from prompthub.core.domain.prompt_messages import PromptMessages


class LLMAdapter(ABC):
    @abstractmethod
    def serialize(self, prompt: PromptMessages) -> Any: ...

    @abstractmethod
    def deserialize(
        self,
        payload: Any,
        *,
        name: str = "imported_prompt",
        version: int = 1,
    ) -> PromptMessages: ...
