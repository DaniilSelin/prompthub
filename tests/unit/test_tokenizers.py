"""
Юнит-тесты для системы подсчёта токенов.
Покрывает: базовый класс ModelTag, конкретные провайдеры, реестр провайдеров.
"""

import sys
import warnings
from unittest.mock import MagicMock

import prompthub.core.tokenizers.registry as reg
from prompthub.core.tokenizers.anthropic_tag import AnthropicModelTag
from prompthub.core.tokenizers.base import ModelTag
from prompthub.core.tokenizers.huggingface_tag import HuggingFaceModelTag
from prompthub.core.tokenizers.openai_tag import OpenAIModelTag

# ---------------------------------------------------------------------------
# Вспомогательные тестовые классы
# ---------------------------------------------------------------------------


class _WordCountTag(ModelTag):
    """Тестовый тег: считает слова, не зависит от внешних библиотек."""

    provider_key = "word-count-test"

    def _count_text(self, text: str) -> int:
        return len(text.split())


class _BrokenTag(ModelTag):
    """Тестовый тег: всегда бросает исключение."""

    provider_key = "broken-test"

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

    def test_provider_key_is_defined_on_subclass(self):
        assert OpenAIModelTag.provider_key == "openai"
        assert AnthropicModelTag.provider_key == "anthropic"
        assert HuggingFaceModelTag.provider_key == "huggingface"


# ---------------------------------------------------------------------------
# OpenAIModelTag
# ---------------------------------------------------------------------------


class TestOpenAIModelTag:

    def _make_mock_openai(self, total_tokens: int) -> tuple[MagicMock, MagicMock]:
        mock_response = MagicMock()
        mock_response.total_tokens = total_tokens

        mock_completions = MagicMock()
        mock_completions.count_tokens.return_value = mock_response

        mock_beta_chat = MagicMock()
        mock_beta_chat.completions = mock_completions

        mock_client = MagicMock()
        mock_client.beta = MagicMock()
        mock_client.beta.chat = mock_beta_chat

        mock_openai_module = MagicMock()
        mock_openai_module.OpenAI.return_value = mock_client
        return mock_openai_module, mock_client

    def test_calls_sdk_count_tokens(self, monkeypatch):
        mock_openai, mock_client = self._make_mock_openai(17)
        monkeypatch.setitem(sys.modules, "openai", mock_openai)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        tag = OpenAIModelTag("gpt-4o")
        result = tag.get_token_count([("user", "hello"), ("assistant", "hi")])

        assert result == 17
        mock_client.beta.chat.completions.count_tokens.assert_called_once_with(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
        )

    def test_client_is_cached_after_first_call(self, monkeypatch):
        mock_openai, mock_client = self._make_mock_openai(5)
        monkeypatch.setitem(sys.modules, "openai", mock_openai)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        tag = OpenAIModelTag("gpt-4o")
        tag.get_token_count([("user", "first")])
        client_ref = tag._client
        tag.get_token_count([("user", "second")])
        assert tag._client is client_ref
        assert mock_openai.OpenAI.call_count == 1

    def test_longer_text_produces_more_tokens(self, monkeypatch):
        call_count = [0]

        def fake_count_tokens(**kwargs):
            call_count[0] += 1
            total_chars = sum(len(m["content"]) for m in kwargs["messages"])
            mock_response = MagicMock()
            mock_response.total_tokens = total_chars
            return mock_response

        mock_openai, mock_client = self._make_mock_openai(0)
        mock_client.beta.chat.completions.count_tokens.side_effect = fake_count_tokens
        monkeypatch.setitem(sys.modules, "openai", mock_openai)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        tag = OpenAIModelTag("gpt-4o")
        short = tag.get_token_count([("user", "Hi")])
        long = tag.get_token_count([("user", "Hi " * 50)])
        assert long > short

    def test_returns_minus_one_and_warns_if_api_key_missing(self, monkeypatch):
        mock_openai, _ = self._make_mock_openai(0)
        monkeypatch.setitem(sys.modules, "openai", mock_openai)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        tag = OpenAIModelTag("gpt-4o")
        tag._client = None

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = tag.get_token_count([("user", "hello")])

        assert result == -1
        assert len(w) == 1
        assert "OPENAI_API_KEY" in str(w[0].message)

    def test_returns_minus_one_and_warns_if_sdk_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "openai", None)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        tag = OpenAIModelTag("gpt-4o")
        tag._client = None

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = tag.get_token_count([("user", "hello")])

        assert result == -1
        assert len(w) == 1


# ---------------------------------------------------------------------------
# AnthropicModelTag
# ---------------------------------------------------------------------------


class TestAnthropicModelTag:

    def _make_mock_anthropic(self, token_count: int) -> tuple[MagicMock, MagicMock]:
        mock_response = MagicMock()
        mock_response.input_tokens = token_count

        mock_messages = MagicMock()
        mock_messages.count_tokens.return_value = mock_response

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        mock_anthropic = MagicMock()
        mock_anthropic.Anthropic.return_value = mock_client
        return mock_anthropic, mock_client

    def test_calls_sdk_count_tokens(self, monkeypatch):
        mock_anthropic, mock_client = self._make_mock_anthropic(42)
        monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        tag = AnthropicModelTag("claude-3-5-sonnet-20241022")
        result = tag.get_token_count([("user", "hello"), ("assistant", "hi")])

        assert result == 42
        mock_client.messages.count_tokens.assert_called_once_with(
            model="claude-3-5-sonnet-20241022",
            messages=[
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi"},
            ],
        )

    def test_returns_minus_one_and_warns_if_api_key_missing(self, monkeypatch):
        mock_anthropic, _ = self._make_mock_anthropic(0)
        monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic)
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = AnthropicModelTag().get_token_count([("user", "hello")])

        assert result == -1
        assert len(w) == 1
        assert "ANTHROPIC_API_KEY" in str(w[0].message)

    def test_returns_minus_one_and_warns_if_sdk_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "anthropic", None)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = AnthropicModelTag().get_token_count([("user", "hello")])

        assert result == -1
        assert len(w) == 1

    def test_longer_text_produces_more_tokens(self, monkeypatch):
        """SDK должен возвращать больше токенов для более длинного текста."""
        call_count = [0]

        def fake_count_tokens(**kwargs):
            call_count[0] += 1
            total_chars = sum(len(m["content"]) for m in kwargs["messages"])
            mock_response = MagicMock()
            mock_response.input_tokens = total_chars
            return mock_response

        mock_anthropic, mock_client = self._make_mock_anthropic(0)
        mock_client.messages.count_tokens.side_effect = fake_count_tokens
        monkeypatch.setitem(sys.modules, "anthropic", mock_anthropic)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        tag = AnthropicModelTag()
        short = tag.get_token_count([("user", "Hi")])
        long = tag.get_token_count([("user", "Hi " * 50)])
        assert long > short


# ---------------------------------------------------------------------------
# HuggingFaceModelTag
# ---------------------------------------------------------------------------


class TestHuggingFaceModelTag:

    def _make_mock_transformers(self, token_ids: list[int]) -> MagicMock:
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
# Registry: _PROVIDER_REGISTRY, resolve_tokenizer, count_tokens_per_model
# ---------------------------------------------------------------------------


class TestRegistry:

    def test_provider_registry_contains_known_providers(self):
        assert "openai" in reg._PROVIDER_REGISTRY
        assert "anthropic" in reg._PROVIDER_REGISTRY
        assert "huggingface" in reg._PROVIDER_REGISTRY

    def test_resolve_tokenizer_returns_correct_instance(self):
        result = reg.resolve_tokenizer("gpt-4o", "openai")
        assert isinstance(result, OpenAIModelTag)
        assert result.model_name == "gpt-4o"

    def test_resolve_tokenizer_returns_none_for_unknown_provider(self):
        result = reg.resolve_tokenizer("some-model", "unknown-provider")
        assert result is None

    def test_count_tokens_per_model_uses_provider_from_row(self, monkeypatch):
        class Fixed10(ModelTag):
            provider_key = "fixed-10"

            def _count_text(self, text: str) -> int:
                return 10

        class Fixed20(ModelTag):
            provider_key = "fixed-20"

            def _count_text(self, text: str) -> int:
                return 20

        monkeypatch.setitem(reg._PROVIDER_REGISTRY, "fixed-10", Fixed10)
        monkeypatch.setitem(reg._PROVIDER_REGISTRY, "fixed-20", Fixed20)

        rows = [
            {"name": "model-a", "provider": "fixed-10"},
            {"name": "model-b", "provider": "fixed-20"},
        ]
        result = reg.count_tokens_per_model([("user", "anything")], rows)
        assert result == {"model-a": 10, "model-b": 20}

    def test_falls_back_to_word_count_for_unknown_provider(self):
        rows = [{"name": "unknown-model", "provider": "unknown-provider"}]
        messages = [("user", "hello world")]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = reg.count_tokens_per_model(messages, rows)

        assert result["unknown-model"] == 2
        assert any("unknown-provider" in str(x.message) for x in w)

    def test_minus_one_from_tokenizer_falls_back_to_word_count(self, monkeypatch):
        monkeypatch.setitem(reg._PROVIDER_REGISTRY, "broken-test", _BrokenTag)
        rows = [{"name": "broken", "provider": "broken-test"}]
        messages = [("user", "one two three")]

        with warnings.catch_warnings(record=True):
            warnings.simplefilter("always")
            result = reg.count_tokens_per_model(messages, rows)

        assert result["broken"] == 3

    def test_each_model_gets_independent_count(self, monkeypatch):
        class LenTag(ModelTag):
            provider_key = "len-test"

            def _count_text(self, text: str) -> int:
                return len(text)

        class WordTag(ModelTag):
            provider_key = "word-test"

            def _count_text(self, text: str) -> int:
                return len(text.split())

        monkeypatch.setitem(reg._PROVIDER_REGISTRY, "len-test", LenTag)
        monkeypatch.setitem(reg._PROVIDER_REGISTRY, "word-test", WordTag)

        rows = [
            {"name": "len-model", "provider": "len-test"},
            {"name": "word-model", "provider": "word-test"},
        ]
        messages = [("user", "hi there")]
        result = reg.count_tokens_per_model(messages, rows)

        assert result["len-model"] == 8  # len("hi there")
        assert result["word-model"] == 2  # 2 слова

    def test_empty_rows_returns_empty_dict(self):
        result = reg.count_tokens_per_model([("user", "hello")], [])
        assert result == {}
