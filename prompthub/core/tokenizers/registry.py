import warnings
from prompthub.core.tokenizers.base import ModelTag, Messages

_registry: dict[str, ModelTag] = {}


def register(tag_name: str, model_tag: ModelTag) -> None:
    """Регистрирует экземпляр ModelTag под именем тега из БД.

    Пример:
        register("gpt-4o", OpenAIModelTag("gpt-4o"))
        register("llama-3-8b", HuggingFaceModelTag("meta-llama/Llama-3-8B"))
    """
    _registry[tag_name] = model_tag


def get(tag_name: str) -> ModelTag | None:
    """Возвращает зарегистрированный ModelTag или None."""
    return _registry.get(tag_name)


def count_tokens(messages: Messages, model_tags: list[str]) -> int:
    """Считает токены, используя первый доступный зарегистрированный тег.

    Перебирает model_tags по порядку. Если для тега есть зарегистрированный
    ModelTag — использует его. Если ни один не зарегистрирован — возвращает
    приближение через подсчёт слов. Если ModelTag вернул -1 (ошибка) —
    переходит к следующему тегу.
    """
    for tag in model_tags:
        mt = _registry.get(tag)
        if mt is None:
            continue
        result = mt.get_token_count(messages)
        if result >= 0:
            return result

    if model_tags:
        warnings.warn(
            f"Нет зарегистрированного токенизатора для тегов {model_tags}. "
            f"Используется приближение по словам."
        )
    return sum(len(content.split()) for _, content in messages)
