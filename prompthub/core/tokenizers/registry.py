import warnings
from prompthub.core.tokenizers.base import ModelTag, Messages
from prompthub.core.tokenizers.openai_tag import OpenAIModelTag
from prompthub.core.tokenizers.anthropic_tag import AnthropicModelTag
from prompthub.core.tokenizers.huggingface_tag import HuggingFaceModelTag

# Неизменяемый реестр провайдеров: provider_key → класс токенизатора.
# Для добавления нового провайдера достаточно добавить строку здесь —
# схема БД при этом не меняется (provider хранится как TEXT).
_PROVIDER_REGISTRY: dict[str, type[ModelTag]] = {
    "openai": OpenAIModelTag,
    "anthropic": AnthropicModelTag,
    "huggingface": HuggingFaceModelTag,
}


def resolve_tokenizer(model_name: str, provider_key: str) -> ModelTag | None:
    """Создаёт экземпляр токенизатора по имени модели и ключу провайдера.

    Возвращает None, если провайдер не зарегистрирован.
    """
    cls = _PROVIDER_REGISTRY.get(provider_key)
    if cls is None:
        return None
    return cls(model_name)


def _word_count(messages: Messages) -> int:
    return sum(len(content.split()) for _, content in messages)


def count_tokens_per_model(
    messages: Messages,
    model_tag_rows: list[dict],
) -> dict[str, int]:
    """Считает токены для каждой модели её собственным токенизатором.

    Аргумент model_tag_rows — список словарей с ключами 'name' и 'provider',
    полученных из БД. Пример: [{"name": "gpt-4o", "provider": "openai"}, ...]

    Если провайдер не зарегистрирован или токенизатор вернул ошибку (-1),
    подставляется приближение по словам с предупреждением.

    Возвращает словарь {model_name: token_count}.
    """
    word_count: int | None = None
    result: dict[str, int] = {}

    for row in model_tag_rows:
        model_name = row["name"]
        provider_key = row.get("provider") or ""

        tokenizer = resolve_tokenizer(model_name, provider_key)

        if tokenizer is None:
            if word_count is None:
                word_count = _word_count(messages)
            warnings.warn(
                f"Нет зарегистрированного токенизатора для провайдера '{provider_key}' "
                f"(модель '{model_name}'). Используется приближение по словам."
            )
            result[model_name] = word_count
            continue

        count = tokenizer.get_token_count(messages)
        if count < 0:
            if word_count is None:
                word_count = _word_count(messages)
            result[model_name] = word_count
        else:
            result[model_name] = count

    return result
