"""
Юнит-тесты для системы подсчёта токенов (ВИ: подсчёт стоимости промпта).
Покрывает: базовый класс ModelTag, конкретные провайдеры, реестр.
"""
import sys
import warnings
import pytest
from unittest.mock import MagicMock

from prompthub.core.tokenizers.base import ModelTag
from prompthub.core.tokenizers.openai_tag import OpenAIModelTag
from prompthub.core.tokenizers.anthropic_tag import AnthropicModelTag
from prompthub.core.tokenizers.huggingface_tag import HuggingFaceModelTag
import prompthub.core.tokenizers.registry as reg


# ---------------------------------------------------------------------------
# Вспомогательные фикстуры
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def isolated_registry(monkeypatch):
    """Каждый тест работает с чистым реестром — не влияет на глобальное состояние."""
    monkeypatch.setattr(reg, "_registry", {})


class _WordCountTag(ModelTag):
    """Тестовый тег: считает слова, не зависит от внешних библиотек."""
    def _count_text(self, text: str) -> int:
        return len(text.split())


class _BrokenTag(ModelTag):
    """Тестовый тег: всегда бросает исключение."""
    def _count_text(self, text: str) -> int:
        raise RuntimeError("tokenizer unavailable")


# ---------------------------------------------------------------------------
# ModelTag: базовое поведение
# ---------------------------------------------------------------------------

class TestModelTagBase:

    def test_sums_only_content_fields_ignores_role(self):
        tag = _WordCountTag("dummy")
        messages = [("system", "you are helpful"), ("user", "hello world")]
        # "you are helpful" = 3, "hello world" = 2 → 5
        assert tag.get_token_count(messages) == 5

    def test_returns_minus_one_and_warns_on_exception(self):
        tag = _BrokenTag("broken")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = tag.get_token_count([("user", "hello")])

        assert result == -1
        assert len(w) == 1
        assert issubclass(w[0].category, UserWarning)

    def test_warning_contains_class_and_model_name(self):
        tag = _BrokenTag("my-model")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            tag.get_token_count([("user", "x")])
        assert "_BrokenTag" in str(w[0].message)
        assert "my-model" in str(w[0].message)

    def test_empty_messages_returns_zero(self):
        tag = _WordCountTag("dummy")
        assert tag.get_token_count([]) == 0


# ---------------------------------------------------------------------------
# OpenAIModelTag
# ---------------------------------------------------------------------------

class TestOpenAIModelTag:

    def test_returns_positive_int_for_known_model(self):
        tag = OpenAIModelTag("gpt-4o")
        result = tag.get_token_count([("user", "Hello, world!")])
        assert isinstance(result, int)
        assert result > 0

    def test_encoder_is_cached_after_first_call(self):
        tag = OpenAIModelTag("gpt-4o")
        tag.get_token_count([("user", "first")])
        enc_ref = tag._enc
        tag.get_token_count([("user", "second")])
        assert tag._enc is enc_ref

    def test_longer_text_produces_more_tokens(self):
        tag = OpenAIModelTag("gpt-4o")
        short = tag.get_token_count([("user", "Hi")])
        long = tag.get_token_count([("user", "Hi " * 50)])
        assert long > short

    def test_returns_minus_one_and_warns_if_tiktoken_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "tiktoken", None)
        tag = OpenAIModelTag("gpt-4o")
        tag._enc = None  # сбрасываем кеш

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = tag.get_token_count([("user", "hello")])

        assert result == -1
        assert len(w) == 1


# ---------------------------------------------------------------------------
# AnthropicModelTag
# ---------------------------------------------------------------------------

class TestAnthropicModelTag:

    def test_returns_positive_int(self):
        tag = AnthropicModelTag()
        result = tag.get_token_count([("user", "Hello Claude!")])
        assert isinstance(result, int)
        assert result > 0

    def test_encoding_is_cached(self):
        tag = AnthropicModelTag()
        tag.get_token_count([("user", "x")])
        enc_ref = tag._enc
        tag.get_token_count([("user", "y")])
        assert tag._enc is enc_ref

    def test_returns_minus_one_if_tiktoken_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "tiktoken", None)
        tag = AnthropicModelTag()
        tag._enc = None

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = tag.get_token_count([("user", "hello")])

        assert result == -1


# ---------------------------------------------------------------------------
# HuggingFaceModelTag
# ---------------------------------------------------------------------------

class TestHuggingFaceModelTag:

    def _make_mock_transformers(self, token_ids: list[int]):
        mock_tokenizer = MagicMock()
        mock_tokenizer.encode.return_value = token_ids
        mock_transformers = MagicMock()
        mock_transformers.AutoTokenizer.from_pretrained.return_value = mock_tokenizer
        return mock_transformers

    def test_delegates_to_autotokenizer(self, monkeypatch):
        mock_transformers = self._make_mock_transformers([1, 2, 3, 4, 5])
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        tag = HuggingFaceModelTag("meta-llama/Llama-3-8B")
        result = tag.get_token_count([("user", "hello world")])

        assert result == 5
        mock_transformers.AutoTokenizer.from_pretrained.assert_called_once_with(
            "meta-llama/Llama-3-8B"
        )

    def test_tokenizer_is_cached(self, monkeypatch):
        mock_transformers = self._make_mock_transformers([1, 2])
        monkeypatch.setitem(sys.modules, "transformers", mock_transformers)

        tag = HuggingFaceModelTag("some/model")
        tag.get_token_count([("user", "a")])
        tag.get_token_count([("user", "b")])

        assert mock_transformers.AutoTokenizer.from_pretrained.call_count == 1

    def test_returns_minus_one_if_transformers_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "transformers", None)
        tag = HuggingFaceModelTag("some/model")
        tag._tokenizer = None

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = tag.get_token_count([("user", "hello")])

        assert result == -1
        assert len(w) == 1


# ---------------------------------------------------------------------------
# Registry: count_tokens_per_model
# ---------------------------------------------------------------------------

class TestRegistry:

    def test_uses_registered_tokenizer_per_model(self):
        class Fixed(ModelTag):
            def __init__(self, n): super().__init__("x"); self.n = n
            def _count_text(self, text): return self.n

        reg.register("model-a", Fixed(10))
        reg.register("model-b", Fixed(20))

        messages = [("user", "anything")]
        result = reg.count_tokens_per_model(messages, ["model-a", "model-b"])

        assert result == {"model-a": 10, "model-b": 20}

    def test_falls_back_to_word_count_for_unregistered_tag(self):
        messages = [("user", "hello world")]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = reg.count_tokens_per_model(messages, ["unknown-model"])

        assert result["unknown-model"] == 2
        assert any("unknown-model" in str(x.message) for x in w)

    def test_minus_one_from_tokenizer_also_falls_back_to_word_count(self):
        reg.register("broken", _BrokenTag("broken"))
        messages = [("user", "one two three")]

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = reg.count_tokens_per_model(messages, ["broken"])

        assert result["broken"] == 3

    def test_each_model_gets_independent_count(self):
        class LenTag(ModelTag):
            def _count_text(self, text): return len(text)

        class WordTag(ModelTag):
            def _count_text(self, text): return len(text.split())

        reg.register("len-model", LenTag("len"))
        reg.register("word-model", WordTag("word"))

        messages = [("user", "hi there")]
        result = reg.count_tokens_per_model(messages, ["len-model", "word-model"])

        assert result["len-model"] == 8   # len("hi there")
        assert result["word-model"] == 2  # 2 слова

    def test_empty_tags_returns_empty_dict(self):
        result = reg.count_tokens_per_model([("user", "hello")], [])
        assert result == {}
