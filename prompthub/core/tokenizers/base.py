import warnings
from abc import ABC, abstractmethod
from typing import ClassVar

Messages = list[tuple[str, str]]


class ModelTag(ABC):
    """Базовый класс для модели с подсчётом токенов.

    Контент промпта — list[tuple[role, content]]. Базовая реализация
    суммирует токены по всем полям content. Провайдер может переопределить
    get_token_count, если нужно учитывать overhead формата (роли, разделители).

    Каждый подкласс обязан определить класс-атрибут provider_key — строку,
    по которой система определяет нужный токенизатор при чтении тега из БД.
    """

    provider_key: ClassVar[str]  # определяется в подклассе, например "openai"

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    def _count_text(self, text: str) -> int:
        """Подсчёт токенов в одной строке. Реализуется провайдером."""
        ...

    def get_token_count(self, messages: Messages) -> int:
        """Суммирует токены по полям content всех сообщений.

        При любой ошибке (библиотека не установлена, модель не найдена,
        сетевой сбой) выдаёт Warning и возвращает -1.
        """
        try:
            return sum(self._count_text(content) for _, content in messages)
        except Exception as e:
            warnings.warn(
                f"[{self.__class__.__name__}:{self.model_name}] "
                f"ошибка подсчёта токенов: {e}"
            )
            return -1
