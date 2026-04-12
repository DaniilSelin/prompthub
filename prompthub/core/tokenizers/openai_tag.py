from prompthub.core.tokenizers.base import ModelTag, Messages


class OpenAIModelTag(ModelTag):
    provider_key = "openai"
    """Подсчёт токенов через tiktoken (библиотека OpenAI).

    Поддерживает любую модель OpenAI: gpt-4o, gpt-4, gpt-3.5-turbo и др.
    Кешируем энкодер — загрузка происходит один раз при первом вызове.

    Примечание: считаем только токены в тексте сообщений. Для точного
    подсчёта запроса к Chat Completions API нужно добавить ~4 токена
    на каждое сообщение (overhead роли и разделителей). Это легко
    сделать, переопределив get_token_count.
    """

    def __init__(self, model_name: str = "gpt-4o"):
        super().__init__(model_name)
        self._enc = None

    def _get_enc(self):
        if self._enc is None:
            import tiktoken
            self._enc = tiktoken.encoding_for_model(self.model_name)
        return self._enc

    def _count_text(self, text: str) -> int:
        import tiktoken
        try:
            return len(self._get_enc().encode(text))
        except KeyError:
            # модель не знакома tiktoken — берём cl100k_base как запасной вариант
            import warnings
            warnings.warn(
                f"tiktoken не знает модель '{self.model_name}', "
                f"используется кодировка cl100k_base"
            )
            self._enc = tiktoken.get_encoding("cl100k_base")
            return len(self._enc.encode(text))
