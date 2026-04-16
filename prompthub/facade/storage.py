from __future__ import annotations

import sqlite3
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from prompthub.core.domain.tag import PromptTag
from prompthub.core.tokenizers.base import ModelTag
from prompthub.facade.prompt import Prompt
from prompthub.facade.prompt_group import PromptGroup
from prompthub.repository import Fields
from prompthub.repository.queries import BaseQuery
from prompthub.repository.query_factory import QueryFactory
from prompthub.repository.repo import PromptRepo
from prompthub.repository.types import (
    CostEntry,
    ExecuteResult,
    ModelTagRow,
    PromptListItem,
    PromptMetadata,
    TagRow,
)
from prompthub.search.filters import Condition

if TYPE_CHECKING:
    from prompthub.core.domain.prompt_messages import PromptMessages  # noqa: F401


class Storage(QueryFactory):
    table: str = Fields._PROMPTS_TABLE

    def __init__(self, path: str):
        self.storage_path: Path = Path(path)
        try:
            self._conn = sqlite3.connect(self.storage_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        except sqlite3.OperationalError as e:
            raise RuntimeError(f"Не удалось открыть базу данных '{path}': {e}") from e
        except sqlite3.DatabaseError as e:
            raise RuntimeError(
                f"Файл '{path}' не является валидной базой SQLite: {e}"
            ) from e

        self.repo = PromptRepo(self._conn)

    def execute(self, query: BaseQuery) -> ExecuteResult:
        return self.repo.execute(query)

    def create_prompt(
        self,
        name: str,
        messages: list[tuple[str, str]] | None = None,
        description: str | None = None,
        tags: list[PromptTag | str] | None = None,
        model_tags: list[ModelTag] | None = None,
    ) -> "Prompt":
        """Создает новый промпт.

        Параметры:
            name        - уникальное имя промпта (ВИ-2).
            messages    - структура сообщений для первой версии. Если передана,
                          первая версия создается автоматически (ВИ-2).
            description - комментарий к первой версии (опционально).
            tags        - список PromptTag для привязки (опционально).
            model_tags  - список ModelTag-объектов для привязки (опционально).

        Поднимает:
            KeyError - если промпт с таким именем уже существует (ВИ-2, альт. 3а).
        """
        if self.repo.get_prompt_by_name(name):
            raise KeyError(f"Промпт '{name}' уже существует")
        try:
            self._conn.execute("BEGIN")

            prompt_id = self.repo.create_prompt(name, commit=False)
            prompt = Prompt(prompt_id, self.repo)

            if messages is not None:
                prompt.add_version(
                    content=messages,
                    description=description,
                    commit=False,
                )

            if tags:
                for tag in tags:
                    prompt.add_prompt_tag(tag, commit=False)

            if model_tags:
                self.add_model_tags(name, model_tags, commit=False)

            self._conn.commit()
            return prompt
        except Exception:
            self._conn.rollback()
            raise

    def fetch_prompt(
        self,
        name: str,
        version: int | None = None,
    ) -> "PromptMessages":
        from prompthub.core.domain.prompt_messages import PromptMessages

        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        prompt = Prompt(row["id"], self.repo)

        if version is not None:
            if not isinstance(version, int):
                raise TypeError("version должен быть целым числом (seq)")
            v = self.repo.get_version_by_seq(row["id"], version)
            if v is None:
                raise ValueError(f"Версия '{version}' не найдена")
            version_seq = v["seq"]
        else:
            latest = self.repo.get_latest_version(row["id"])
            if latest is None:
                raise ValueError(f"Промпт '{name}' не имеет версий")
            version_seq = latest["seq"]

        content = prompt.get_version_content(version_seq)
        return PromptMessages(name=name, version=version_seq, content=content)

    def get_prompt(self, name: str) -> Prompt:
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        return Prompt(row["id"], self.repo)

    def delete_prompt(self, name: str) -> int:
        """Удаляет промпт и всю его историю.

        Поднимает:
            KeyError - если промпт с таким именем не найден (ВИ-4, альт. 2а).
        """
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        return self.repo.delete_prompt(row["id"])

    def make_group_prompt(self) -> PromptGroup:
        return PromptGroup(self.repo)

    def find_prompt(self, name: str) -> PromptMetadata | None:
        row = self.repo.get_prompt_by_name(name)
        if not row:
            return None
        return self.repo.fetch_metadata(row["id"])

    def search_by_tags(self, filters: Condition) -> list[PromptMetadata]:
        rows = self.repo.execute_tag_filter_query(filters)
        return [self.repo.fetch_metadata(r["id"]) for r in rows]

    def list_prompts(self) -> list[PromptListItem]:
        from prompthub.core.tokenizers.registry import count_tokens_per_model

        rows = self.repo.fetch_all_prompts()
        if not rows:
            return []

        result: list[PromptListItem] = []
        for row in rows:
            prompt_id = row["id"]
            metadata = self.repo.fetch_metadata(prompt_id)
            model_tag_rows: list[ModelTagRow] = metadata.get("model_tags") or []
            model_tag_names = [r["name"] for r in model_tag_rows]

            latest = self.repo.get_latest_version(prompt_id)
            if latest is None:
                content: list[tuple[str, str]] = []
            else:
                prompt = Prompt(prompt_id, self.repo)
                content = prompt.get_version_content(latest["seq"])

            if not model_tag_rows:
                entry: PromptListItem = {
                    "name": metadata["name"],
                    "created_at": metadata["created_at"],
                    "updated_at": metadata["updated_at"],
                    "tags": metadata["tags"],
                    "model_tags": None,
                    "costs": None,
                }
                result.append(entry)
                continue

            # Токены считаем токенизатором провайдера, цену берем из тарифов
            tariffs = self.repo.fetch_tariffs(model_tag_names)
            token_counts = count_tokens_per_model(
                content, cast(list[dict[str, Any]], model_tag_rows)
            )

            costs: dict[str, CostEntry] = {}
            for tag_row in model_tag_rows:
                tag_name = tag_row["name"]
                tokens = token_counts.get(tag_name, 0)
                if tag_name not in tariffs:
                    warnings.warn(
                        f"Тариф для модели '{tag_name}' не найден - стоимость не рассчитана"
                    )
                    costs[tag_name] = {"token_count": tokens, "cost": None}
                else:
                    price = tariffs[tag_name]["input_price_per_1m"]
                    costs[tag_name] = {
                        "token_count": tokens,
                        "cost": round(tokens / 1_000_000 * price, 6),
                    }

            entry = {
                "name": metadata["name"],
                "created_at": metadata["created_at"],
                "updated_at": metadata["updated_at"],
                "tags": metadata["tags"],
                "model_tags": metadata["model_tags"],
                "costs": costs,
            }
            result.append(entry)

        return result

    def list_all_tags(self) -> list[TagRow]:
        rows = self.repo.fetch_all_tags()
        return [
            {
                "name": r["name"],
                "type": r["type"],
                "provider": r["provider"],
            }
            for r in rows
        ]

    def update_tariffs(self, url: str | None = None) -> int:
        """Обновляет тарифы для всех моделей из внешнего источника (ВИ-17).

        Запрашивает все цены с OpenRouter и сохраняет их в БД без фильтрации.
        Это позволяет проверять наличие тарифа перед привязкой model_tag (ВИ-11).

        Поднимает:
            ConnectionError - если внешний источник недоступен.
            ValueError      - если полученные данные невалидны.
            RuntimeError    - если ошибка записи в БД.
        """
        from prompthub.infrastructure.pricing_gateway import PricingAPIGateway
        from prompthub.infrastructure.tariff_manager import TariffManager

        gateway = PricingAPIGateway(url=url) if url else PricingAPIGateway()
        all_tariffs = gateway.fetch_pricing_data()  # ConnectionError / ValueError
        return TariffManager(self._conn).bulk_upsert(
            all_tariffs
        )  # RuntimeError при ошибке БД

    def remove_model_tags(
        self, name: str, model_tags: list[ModelTag], commit: bool = True
    ) -> list[str]:
        """Отвязывает ModelTag-объекты от промпта. Возвращает список отвязанных имен."""
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        prompt_id = row["id"]
        current = self.repo.fetch_current_model_tags(prompt_id)

        to_remove = []
        for mt in model_tags:
            tag_name = mt.model_name
            if tag_name not in current:
                warnings.warn(f"Тег '{tag_name}': не привязан к промпту - пропущен")
            else:
                to_remove.append(tag_name)

        if to_remove:
            self.repo.delete_prompt_model_tag_links(prompt_id, to_remove, commit=commit)

        return to_remove

    def add_model_tags(
        self, name: str, model_tags: list[ModelTag], commit: bool = True
    ) -> list[str]:
        """Привязывает ModelTag-объекты к промпту. Возвращает список добавленных имен.

        Пропускает теги с предупреждением если (ВИ-11, альт. 3а):
          - тег уже привязан к промпту (дубликат);
          - для тега нет тарифа в системе.
        """
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        prompt_id = row["id"]
        current = self.repo.fetch_current_model_tags(prompt_id)

        # Загружаем тарифы одним запросом для всех кандидатов
        candidate_names = [mt.model_name for mt in model_tags]
        known_tariffs = self.repo.fetch_tariffs(candidate_names)

        to_add: list[ModelTagRow] = []
        for mt in model_tags:
            tag_name = mt.model_name
            if tag_name in current:
                warnings.warn(f"Тег '{tag_name}': дубликат - уже привязан к промпту")
            elif tag_name not in known_tariffs:
                warnings.warn(
                    f"Тег '{tag_name}': нет тарифа в системе - пропущен. "
                    f"Сначала вызовите update_tariffs()."
                )
            else:
                to_add.append({"name": tag_name, "provider": type(mt).provider_key})

        if to_add:
            self.repo.create_prompt_model_tag_links(prompt_id, to_add, commit=commit)

        return [t["name"] for t in to_add]
