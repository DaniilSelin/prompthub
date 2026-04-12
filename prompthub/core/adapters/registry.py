from collections.abc import Callable
from typing import TypeAlias

from prompthub.core.adapters.base import LLMAdapter

AdapterFactory: TypeAlias = Callable[[], LLMAdapter]


def _load_langchain() -> LLMAdapter:
    from prompthub.core.adapters.langchain import LangChainAdapter

    return LangChainAdapter()


_REGISTRY: dict[str, AdapterFactory] = {
    "langchain": _load_langchain,
}


def _normalize_adapter_type(adapter_type: str) -> str:
    if not isinstance(adapter_type, str) or not adapter_type.strip():
        raise ValueError("adapter_type должен быть непустой строкой")
    return adapter_type.strip().lower()


def register_adapter(
    adapter_type: str, adapter_factory: AdapterFactory | type[LLMAdapter]
) -> None:
    key = _normalize_adapter_type(adapter_type)

    if isinstance(adapter_factory, type):
        if not issubclass(adapter_factory, LLMAdapter):
            raise TypeError("adapter_factory должен наследовать LLMAdapter")
        _REGISTRY[key] = adapter_factory
        return

    if not callable(adapter_factory):
        raise TypeError("adapter_factory должен быть вызываемым")

    _REGISTRY[key] = adapter_factory


def unregister_adapter(adapter_type: str) -> None:
    key = _normalize_adapter_type(adapter_type)
    if key not in _REGISTRY:
        raise ValueError(f"Адаптер '{adapter_type}' не зарегистрирован")
    del _REGISTRY[key]


def list_adapter_types() -> list[str]:
    return sorted(_REGISTRY.keys())


def get_adapter(adapter_type: str) -> LLMAdapter:
    key = _normalize_adapter_type(adapter_type)
    factory = _REGISTRY.get(key)
    if factory is None:
        raise ValueError(
            f"Адаптер '{adapter_type}' не поддерживается. "
            f"Доступные: {list(_REGISTRY.keys())}"
        )

    try:
        adapter = factory()
    except ImportError as exc:
        raise ValueError(
            f"Адаптер '{adapter_type}' не поддерживается или модуль не установлен: {exc}"
        ) from exc

    if not isinstance(adapter, LLMAdapter):
        raise TypeError(f"Фабрика адаптера '{adapter_type}' вернула некорректный тип")

    return adapter
