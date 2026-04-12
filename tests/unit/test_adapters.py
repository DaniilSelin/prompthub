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
    def serialize(self, prompt: PromptMessages):
        return {"name": prompt.name, "version": prompt.version, "content": prompt.content}

    def deserialize(self, payload, *, name: str = "imported_prompt", version: int = 1):
        return PromptMessages(name=name, version=version, content=payload["content"])


def test_openai_adapter_supports_serialize_and_deserialize():
    adapter = get_adapter("openai")
    prompt = PromptMessages(name="p", version=2, content=[("user", "hello")])

    serialized = adapter.serialize(prompt)
    assert serialized == [{"role": "user", "content": "hello"}]

    restored = adapter.deserialize(serialized, name="restored", version=7)
    assert restored.name == "restored"
    assert restored.version == 7
    assert restored.content == [("user", "hello")]


def test_custom_adapter_can_be_registered_and_removed():
    key = "dummy-adapter"
    register_adapter(key, _DummyAdapter)
    try:
        assert key in list_adapter_types()
        adapter = get_adapter(key)
        payload = adapter.serialize(PromptMessages(name="x", version=1, content=[("user", "u")]))
        assert payload["name"] == "x"
    finally:
        unregister_adapter(key)

    with pytest.raises(ValueError, match=key):
        get_adapter(key)


def test_unknown_adapter_raises_value_error():
    with pytest.raises(ValueError, match="not-registered"):
        get_adapter("not-registered")
