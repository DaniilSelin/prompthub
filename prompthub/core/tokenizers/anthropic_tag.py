from prompthub.core.tokenizers.base import ModelTag, Messages


class AnthropicModelTag(ModelTag):
    """Подсчёт токенов для моделей Anthropic (Claude) через официальный SDK.

    Требует установленного пакета `anthropic` и переменной окружения
    ANTHROPIC_API_KEY. При отсутствии любого из них get_token_count вернёт -1
    и выдаст предупреждение (стандартное поведение базового класса).

    Использует messages.count_tokens — официальный API Anthropic, который
    учитывает overhead формата (роли, разделители).
    """

    provider_key = "anthropic"

    def __init__(self, model_name: str = "claude-3-5-sonnet-20241022"):
        super().__init__(model_name)

    def _count_text(self, text: str) -> int:
        raise NotImplementedError(
            "AnthropicModelTag считает токены на уровне сообщений через SDK, "
            "а не построчно. Используйте get_token_count."
        )

    def get_token_count(self, messages: Messages) -> int:
        """Считает токены через Anthropic SDK (messages.count_tokens).

        При отсутствии пакета `anthropic`, недоступном API или другой ошибке
        выдаёт предупреждение и возвращает -1 (стандартное поведение библиотеки).
        """
        import warnings
        try:
            import anthropic
            client = anthropic.Anthropic()
            response = client.messages.count_tokens(
                model=self.model_name,
                messages=[
                    {"role": role, "content": content}
                    for role, content in messages
                ],
            )
            return response.input_tokens
        except Exception as e:
            warnings.warn(
                f"[{self.__class__.__name__}:{self.model_name}] "
                f"ошибка подсчёта токенов: {e}"
            )
            return -1
