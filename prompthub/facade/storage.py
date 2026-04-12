from prompthub.facade.prompt import Prompt
from prompthub.facade.prompt_group import PromptGroup
from prompthub.repository.repo import PromptRepo
from prompthub.repository import Fields
from prompthub.repository.query_factory import QueryFactory
from prompthub.repository.queries import BaseQuery

from pathlib import Path
import sqlite3
import warnings


class Storage(QueryFactory):
    table: str = Fields._PROMPTS_TABLE

    def __init__(self, path: str):
        self.storage_path: Path = Path(path)
        self._conn = sqlite3.connect(self.storage_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self.repo = PromptRepo(self._conn)

    def execute(self, query: BaseQuery):
        return self.repo.execute(query)

    def create_prompt(self, name: str, model_tags=None) -> Prompt:
        """Создаёт новый промпт. model_tags — список ModelTag-объектов."""
        prompt_id = self.repo.create_prompt(name)
        prompt = Prompt(prompt_id, self.repo)
        if model_tags:
            for mt in model_tags:
                prompt.add_model_tag(mt)
        return prompt

    def fetch_prompt(
        self,
        name: str,
        version: str | None = None,
        adapter_type: str | None = None,
    ):
        from prompthub.core.domain.prompt_messages import PromptMessages
        from prompthub.core.adapters.registry import get_adapter

        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        prompt = Prompt(row["id"], self.repo)

        if version is not None:
            v = self.repo.get_version_by_name(row["id"], version)
            if v is None:
                raise ValueError(f"Версия '{version}' не найдена")
            version_name = v["name"]
        else:
            latest = self.repo.get_latest_version(row["id"])
            if latest is None:
                raise ValueError(f"Промпт '{name}' не имеет версий")
            version_name = latest["name"]

        content = prompt.get_version_content(version_name)
        messages = PromptMessages(name=name, version=version_name, content=content)

        if adapter_type is None:
            return messages

        adapter = get_adapter(adapter_type)
        return adapter.convert(messages)

    def get_prompt(self, name: str) -> Prompt:
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise ValueError("prompt not found")

        return Prompt(row["id"], self.repo)

    def delete_prompt(self, name: str):
        row = self.repo.get_prompt_by_name(name)
        if not row:
            return 0

        return self.repo.delete_prompt(row["id"])

    def make_group_prompt(self) -> PromptGroup:
        return PromptGroup(self.repo)

    def find_prompt(self, name: str) -> dict | None:
        row = self.repo.find_by_name_exact(name)
        if not row:
            return None
        return self.repo.fetch_metadata(row["id"])

    def search_by_tags(self, filters) -> list[dict]:
        rows = self.repo.execute_tag_filter_query(filters)
        return [self.repo.fetch_metadata(r["id"]) for r in rows]

    def list_prompts(self) -> list[dict]:
        from prompthub.core.tokenizers.registry import count_tokens_per_model

        rows = self.repo.fetch_all_prompts()
        if not rows:
            return []

        result = []
        for row in rows:
            prompt_id = row["id"]
            metadata = self.repo.fetch_metadata(prompt_id)
            # model_tags — список {"name": ..., "provider": ...}
            model_tag_rows: list[dict] = metadata.get("model_tags") or []
            model_tag_names = [r["name"] for r in model_tag_rows]

            # Получаем контент последней версии
            latest = self.repo.get_latest_version(prompt_id)
            if latest is None:
                content = []
            else:
                prompt = Prompt(prompt_id, self.repo)
                content = prompt.get_version_content(latest["name"])

            # Токены считаем токенизатором провайдера, цену берём из тарифов
            tariffs = self.repo.fetch_tariffs(model_tag_names) if model_tag_rows else {}
            token_counts = count_tokens_per_model(content, model_tag_rows)

            costs: dict[str, dict] = {}
            for tag_row in model_tag_rows:
                tag_name = tag_row["name"]
                tokens = token_counts.get(tag_name, 0)
                if tag_name not in tariffs:
                    warnings.warn(
                        f"Тариф для модели '{tag_name}' не найден — стоимость не рассчитана"
                    )
                    costs[tag_name] = {"token_count": tokens, "cost": None}
                else:
                    price = tariffs[tag_name]["input_price_per_1m"]
                    costs[tag_name] = {
                        "token_count": tokens,
                        "cost": round(tokens / 1_000_000 * price, 6),
                    }

            entry = {**metadata, "costs": costs}
            result.append(entry)

        return result

    def list_all_tags(self) -> list[dict]:
        rows = self.repo.fetch_all_tags()
        return [
            {
                "name": r[Fields.TAG_NAME],
                "type": r[Fields.TAG_TYPE],
                "provider": r[Fields.TAG_PROVIDER],
            }
            for r in rows
        ]

    def update_tariffs(self, url: str | None = None) -> int:
        """Обновляет тарифы только для моделей, зарегистрированных в тегах.

        Запрашивает все цены из внешнего источника, затем сохраняет только те,
        чьё имя совпадает с тегом типа model в БД. Это предотвращает хранение
        цен для всех 500+ моделей OpenRouter.
        """
        from prompthub.infrastructure.pricing_gateway import PricingAPIGateway
        from prompthub.infrastructure.tariff_manager import TariffManager

        known_tags = self.repo.fetch_all_model_tag_names()
        gateway = PricingAPIGateway(**({"url": url} if url else {}))
        all_tariffs = gateway.fetch_pricing_data()  # ConnectionError / ValueError

        filtered = [t for t in all_tariffs if t.tag_name in known_tags]
        return TariffManager(self._conn).bulk_upsert(filtered)  # RuntimeError при ошибке БД

    def remove_model_tags(self, name: str, model_tags: list) -> list[str]:
        """Отвязывает ModelTag-объекты от промпта. Возвращает список отвязанных имён."""
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        prompt_id = row["id"]
        current = self.repo.fetch_current_model_tags(prompt_id)

        to_remove = []
        for mt in model_tags:
            tag_name = mt.model_name
            if tag_name not in current:
                warnings.warn(f"Тег '{tag_name}': не привязан к промпту — пропущен")
            else:
                to_remove.append(tag_name)

        if to_remove:
            self.repo.delete_prompt_model_tag_links(prompt_id, to_remove)

        return to_remove

    def add_model_tags(self, name: str, model_tags: list) -> list[str]:
        """Привязывает ModelTag-объекты к промпту. Возвращает список добавленных имён."""
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        prompt_id = row["id"]
        current = self.repo.fetch_current_model_tags(prompt_id)

        to_add = []
        for mt in model_tags:
            tag_name = mt.model_name
            if tag_name in current:
                warnings.warn(f"Тег '{tag_name}': дубликат — уже привязан к промпту")
            else:
                to_add.append({"name": tag_name, "provider": type(mt).provider_key})

        if to_add:
            self.repo.create_prompt_model_tag_links(prompt_id, to_add)

        return [t["name"] for t in to_add]
