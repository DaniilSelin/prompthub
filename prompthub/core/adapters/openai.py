from prompthub.core.adapters.base import LLMAdapter
from prompthub.core.domain.prompt_messages import PromptMessages


class OpenAIAdapter(LLMAdapter):
    """Конвертирует промпт в формат OpenAI Chat Completions API."""

    def convert(self, prompt: PromptMessages) -> list[dict]:
        return [{"role": "user", "content": prompt.content}]
