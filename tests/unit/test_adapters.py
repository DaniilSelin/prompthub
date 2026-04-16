import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from prompthub.core.adapters.base import LLMAdapter
from prompthub.core.adapters.registry import (
    get_adapter,
    list_adapter_types,
    register_adapter,
    unregister_adapter,
)
from prompthub.core.domain.prompt_messages import PromptMessages


class _DummyAdapter(LLMAdapter):
    def serialize(self, prompt: PromptMessages) -> dict[str, Any]:
        return {
            "name": prompt.name,
            "version": prompt.version,
            "content": prompt.content,
        }

    def deserialize(
        self,
        payload: dict[str, Any],
        *,
        name: str = "imported_prompt",
        version: int = 1,
    ) -> PromptMessages:
        return PromptMessages(name=name, version=version, content=payload["content"])


# ---------------------------------------------------------------------------
# LangChain adapter
# ---------------------------------------------------------------------------


def _make_mock_langchain():
    """Создает мок ChatPromptTemplate для тестов без установленного langchain-core."""
    mock_template = MagicMock()
    mock_template.__class__.__name__ = "ChatPromptTemplate"

    # format_messages() возвращает список мок-сообщений
    msg_system = MagicMock()
    msg_system.type = "system"
    msg_system.content = "You are helpful"

    msg_user = MagicMock()
    msg_user.type = "human"
    msg_user.content = "Hello"

    mock_template.format_messages.return_value = [msg_system, msg_user]
    return mock_template


def test_langchain_adapter_serialize_returns_chat_prompt_template(monkeypatch):
    """serialize() должен возвращать ChatPromptTemplate через from_messages с туплами."""
    mock_template = MagicMock()
    mock_template.__class__.__name__ = "ChatPromptTemplate"

    mock_ChatPromptTemplate = MagicMock()
    mock_ChatPromptTemplate.from_messages.return_value = mock_template

    mock_langchain_core_prompts = MagicMock()
    mock_langchain_core_prompts.ChatPromptTemplate = mock_ChatPromptTemplate

    mock_langchain_core = MagicMock()
    mock_langchain_core.prompts = mock_langchain_core_prompts

    monkeypatch.setitem(sys.modules, "langchain_core", mock_langchain_core)
    monkeypatch.setitem(
        sys.modules, "langchain_core.prompts", mock_langchain_core_prompts
    )

    from prompthub.core.adapters.langchain import LangChainAdapter

    adapter = LangChainAdapter()
    prompt = PromptMessages(
        name="p",
        version=1,
        content=[("system", "You are helpful"), ("user", "Hello")],
    )
    result = adapter.serialize(prompt)

    # from_messages вызван с туплами (role, content) - без конкретных классов сообщений
    mock_ChatPromptTemplate.from_messages.assert_called_once_with(
        [("system", "You are helpful"), ("user", "Hello")]
    )
    assert result is mock_template


def test_langchain_adapter_deserialize_from_chat_prompt_template(monkeypatch):
    """deserialize() из ChatPromptTemplate через format_messages() - duck-typing."""
    mock_template = _make_mock_langchain()

    mock_langchain_core_prompts = MagicMock()
    mock_langchain_core = MagicMock()
    mock_langchain_core.prompts = mock_langchain_core_prompts

    monkeypatch.setitem(sys.modules, "langchain_core", mock_langchain_core)
    monkeypatch.setitem(
        sys.modules, "langchain_core.prompts", mock_langchain_core_prompts
    )

    from prompthub.core.adapters.langchain import LangChainAdapter

    adapter = LangChainAdapter()
    # mock_template имеет .format_messages() - работает как ChatPromptTemplate
    result = adapter.deserialize(mock_template, name="test", version=2)

    assert result.name == "test"
    assert result.version == 2
    assert result.content == [("system", "You are helpful"), ("user", "Hello")]


def test_langchain_adapter_deserialize_from_tuples(monkeypatch):
    """deserialize() принимает список кортежей напрямую."""
    mock_langchain_core_prompts = MagicMock()
    mock_langchain_core = MagicMock()
    mock_langchain_core.prompts = mock_langchain_core_prompts

    monkeypatch.setitem(sys.modules, "langchain_core", mock_langchain_core)
    monkeypatch.setitem(
        sys.modules, "langchain_core.prompts", mock_langchain_core_prompts
    )

    from prompthub.core.adapters.langchain import LangChainAdapter

    adapter = LangChainAdapter()
    result = adapter.deserialize(
        [("system", "Be concise"), ("user", "Hi")],
        name="x",
        version=3,
    )

    assert result.content == [("system", "Be concise"), ("user", "Hi")]


def test_langchain_adapter_not_in_registry_by_default():
    """Адаптер 'openai' больше не должен быть зарегистрирован."""
    with pytest.raises(ValueError, match="openai"):
        get_adapter("openai")


# ---------------------------------------------------------------------------
# Реестр адаптеров
# ---------------------------------------------------------------------------


def test_custom_adapter_can_be_registered_and_removed():
    key = "dummy-adapter"
    register_adapter(key, _DummyAdapter)
    try:
        assert key in list_adapter_types()
        adapter = get_adapter(key)
        payload = adapter.serialize(
            PromptMessages(name="x", version=1, content=[("user", "u")])
        )
        assert payload["name"] == "x"
    finally:
        unregister_adapter(key)

    with pytest.raises(ValueError, match=key):
        get_adapter(key)


def test_unknown_adapter_raises_value_error():
    with pytest.raises(ValueError, match="not-registered"):
        get_adapter("not-registered")


def test_langchain_is_in_registry():
    assert "langchain" in list_adapter_types()
