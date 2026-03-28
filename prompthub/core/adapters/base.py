from abc import ABC, abstractmethod
from prompthub.core.domain.prompt_messages import PromptMessages


class LLMAdapter(ABC):
    @abstractmethod
    def convert(self, prompt: PromptMessages):
        """Конвертирует PromptMessages в нативный формат фреймворка."""
