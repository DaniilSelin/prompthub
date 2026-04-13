import warnings
from collections.abc import Callable
from typing import Any

from prompthub.core.tokenizers.base import Messages, ModelTag


def _load_openai_tag() -> type[ModelTag]:
    from prompthub.core.tokenizers.openai_tag import OpenAIModelTag

    return OpenAIModelTag


def _load_anthropic_tag() -> type[ModelTag]:
    from prompthub.core.tokenizers.anthropic_tag import AnthropicModelTag

    return AnthropicModelTag


def _load_huggingface_tag() -> type[ModelTag]:
    from prompthub.core.tokenizers.huggingface_tag import HuggingFaceModelTag

    return HuggingFaceModelTag


# Неизменяемый реестр провайдеров: provider_key → класс токенизатора.
# Для добавления нового провайдера достаточно добавить строку здесь —
# схема БД при этом не меняется (provider хранится как TEXT).
_PROVIDER_REGISTRY: dict[str, type[ModelTag] | Callable[[], type[ModelTag]]] = {
    "openai": _load_openai_tag,
    "anthropic": _load_anthropic_tag,
    "huggingface": _load_huggingface_tag,
}


def resolve_tokenizer(model_name: str, provider_key: str) -> ModelTag | None:
    """Создаёт экземпляр токенизатора по имени модели и ключу провайдера.

    Возвращает None, если провайдер не зарегистрирован.
    """
    provider = _PROVIDER_REGISTRY.get(provider_key)
    if provider is None:
        return None

    cls = (
        provider()
        if callable(provider) and not isinstance(provider, type)
        else provider
    )
    if not isinstance(cls, type) or not issubclass(cls, ModelTag):
        raise TypeError(f"Провайдер '{provider_key}' должен возвращать класс ModelTag")

    return cls(model_name)


def count_tokens_per_model(
    messages: Messages,
    model_tag_rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Считает токены для каждой модели её собственным токенизатором.

    Аргумент model_tag_rows — список словарей с ключами 'name' и 'provider',
    полученных из БД. Пример: [{"name": "gpt-4o", "provider": "openai"}, ...]

    Если провайдер не зарегистрирован или токенизатор вернул ошибку (-1),
    подставляется приближение по словам с предупреждением.

    Возвращает словарь {model_name: token_count}.
    """
    result: dict[str, int] = {}

    for row in model_tag_rows:
        model_name = row["name"]
        provider_key = row.get("provider") or ""

        tokenizer = resolve_tokenizer(model_name, provider_key)

        if tokenizer is None:
            warnings.warn(
                f"Нет зарегистрированного токенизатора для провайдера '{provider_key}' "
                f"(модель '{model_name}')."
            )
            result[model_name] = 0
            continue

        count = tokenizer.get_token_count(messages)
        if count < 0:
            result[model_name] = 0
        else:
            result[model_name] = count

    return result
