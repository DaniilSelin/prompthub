from prompthub.core.adapters.base import LLMAdapter
from prompthub.core.adapters.openai import OpenAIAdapter

_REGISTRY: dict[str, type[LLMAdapter]] = {
    "openai": OpenAIAdapter,
}


def get_adapter(adapter_type: str) -> LLMAdapter:
    cls = _REGISTRY.get(adapter_type)
    if cls is None:
        raise ValueError(
            f"Адаптер '{adapter_type}' не поддерживается. "
            f"Доступные: {list(_REGISTRY.keys())}"
        )
    return cls()
