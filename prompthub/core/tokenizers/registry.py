import warnings
from prompthub.core.tokenizers.base import ModelTag, Messages

_registry: dict[str, ModelTag] = {}

_WORD_COUNT_FALLBACK = "word_count"


def register(tag_name: str, model_tag: ModelTag) -> None:
    """Регистрирует экземпляр ModelTag под именем тега из БД.

    Пример:
        register("openai/gpt-4o", OpenAIModelTag("gpt-4o"))
        register("meta-llama/llama-3.1-8b-instruct", HuggingFaceModelTag("meta-llama/Llama-3.1-8B"))
    """
    _registry[tag_name] = model_tag


def get(tag_name: str) -> ModelTag | None:
    """Возвращает зарегистрированный ModelTag или None."""
    return _registry.get(tag_name)


def _word_count(messages: Messages) -> int:
    return sum(len(content.split()) for _, content in messages)


def count_tokens_per_model(messages: Messages, model_tags: list[str]) -> dict[str, int]:
    """Считает токены для каждой модели её собственным токенизатором.

    Возвращает словарь {tag_name: token_count}.
    Если для тега нет зарегистрированного токенизатора или он вернул ошибку (-1),
    подставляется приближение по словам с предупреждением.
    """
    word_count = None  # вычисляем лениво, только если нужен fallback
    result: dict[str, int] = {}

    for tag in model_tags:
        mt = _registry.get(tag)
        if mt is None:
            if word_count is None:
                word_count = _word_count(messages)
            warnings.warn(
                f"Нет зарегистрированного токенизатора для '{tag}'. "
                f"Используется приближение по словам."
            )
            result[tag] = word_count
            continue

        count = mt.get_token_count(messages)
        if count < 0:
            if word_count is None:
                word_count = _word_count(messages)
            result[tag] = word_count
        else:
            result[tag] = count

    return result


# Оставляем для обратной совместимости: возвращает токены первого рабочего тега.
def count_tokens(messages: Messages, model_tags: list[str]) -> int:
    if not model_tags:
        return _word_count(messages)
    per_model = count_tokens_per_model(messages, model_tags)
    return next(iter(per_model.values())) if per_model else _word_count(messages)
