from prompthub.core.tokenizers.base import ModelTag


class AnthropicModelTag(ModelTag):
    """Подсчёт токенов для моделей Anthropic (Claude).

    Anthropic не публикует свой токенизатор. Используем tiktoken с кодировкой
    cl100k_base — это близкое приближение (погрешность ~5-10%).

    Если установлен пакет anthropic и задан API-ключ, можно переопределить
    _count_text для точного подсчёта через anthropic.Anthropic().count_tokens().
    """

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022"):
        super().__init__(model_name)
        self._enc = None

    def _get_enc(self):
        if self._enc is None:
            import tiktoken
            self._enc = tiktoken.get_encoding("cl100k_base")
        return self._enc

    def _count_text(self, text: str) -> int:
        return len(self._get_enc().encode(text))
