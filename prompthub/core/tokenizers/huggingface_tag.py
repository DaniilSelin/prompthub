from typing import Any

from prompthub.core.tokenizers.base import ModelTag


class HuggingFaceModelTag(ModelTag):
    """Подсчет токенов через transformers.AutoTokenizer (HuggingFace).

    Принимает любое имя модели из HuggingFace Hub:
        HuggingFaceModelTag("meta-llama/Llama-3-8B")
        HuggingFaceModelTag("mistralai/Mistral-7B-v0.1")

    Токенизатор кешируется - загружается один раз при первом вызове.
    """

    provider_key = "huggingface"

    def __init__(self, model_name: str):
        super().__init__(model_name)
        self._tokenizer: Any | None = None

    def _get_tokenizer(self):
        if self._tokenizer is None:
            from transformers import AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        return self._tokenizer

    def _count_text(self, text: str) -> int:
        tokenizer = self._get_tokenizer()
        return len(tokenizer.encode(text))
