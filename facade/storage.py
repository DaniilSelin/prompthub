from facade.prompt import Prompt
from facade.prompt_group import PromptGroup
from repository.repo import PromptRepo
from repository import Fields
from repository.query_factory import QueryFactory
from repository.queries import BaseQuery 

from pathlib import Path
import sqlite3
import warnings

class Storage(QueryFactory):
    table: str = Fields._PROMPTS_TABLE

    def __init__(self, path: str):
        self.storage_path: Path = Path(path)
        self._conn = sqlite3.connect(self.storage_path)
        self._conn.row_factory = sqlite3.Row

        self.repo = PromptRepo(self._conn)

    def execute(self, query: BaseQuery):
        return self.repo.execute(query)

    def create_prompt(
        self,
        name: str,
        author: str | None = None,
    ) -> Prompt:
        prompt_id = self.repo.create_prompt(name, author)
        return Prompt(prompt_id, self.repo)

    def fetch_prompt(
        self,
        name: str,
        version: str | None = None,
        adapter_type: str | None = None,
    ):
        from core.domain.prompt_messages import PromptMessages
        from core.adapters.registry import get_adapter

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

    def list_all_tags(self) -> list[dict]:
        rows = self.repo.fetch_all_tags()
        return [{"name": r["name"], "type": r["type"]} for r in rows]

    def update_tariffs(self, url: str | None = None) -> int:
        from infrastructure.pricing_gateway import PricingAPIGateway
        from infrastructure.tariff_manager import TariffManager

        gateway = PricingAPIGateway(**({"url": url} if url else {}))
        tariffs = gateway.fetch_pricing_data()   # ConnectionError / ValueError

        manager = TariffManager(self._conn)
        return manager.bulk_upsert(tariffs)      # RuntimeError при ошибке БД

    def register_tariff(self, tag_name: str):
        self.repo.register_tariff(tag_name)

    def remove_model_tags(self, name: str, model_tags: list[str]) -> list[str]:
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        prompt_id = row["id"]
        current = self.repo.fetch_current_model_tags(prompt_id)

        to_remove = []
        for tag in model_tags:
            if tag not in current:
                warnings.warn(f"Тег '{tag}': не привязан к промпту — пропущен")
            else:
                to_remove.append(tag)

        if to_remove:
            self.repo.delete_prompt_model_tag_links(prompt_id, to_remove)

        return to_remove

    def add_model_tags(self, name: str, model_tags: list[str]) -> list[str]:
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

        prompt_id = row["id"]
        current = self.repo.fetch_current_model_tags(prompt_id)
        available = self.repo.fetch_available_tariffs()

        to_add = []
        for tag in model_tags:
            if tag in current:
                warnings.warn(f"Тег '{tag}': дубликат — уже привязан к промпту")
            elif tag not in available:
                warnings.warn(f"Тег '{tag}': нет тарифа — пропущен")
            else:
                to_add.append(tag)

        if to_add:
            self.repo.create_prompt_model_tag_links(prompt_id, to_add)

        return to_add