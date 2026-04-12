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
        self._conn = sqlite3.connect(self.storage_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self.repo = PromptRepo(self._conn)

    def execute(self, query: BaseQuery):
        return self.repo.execute(query)

    def create_prompt(
        self,
        name: str,
        messages: list[tuple[str, str]] | None = None,
        description: str | None = None,
        tags: list | None = None,
        model_tags: list | None = None,
    ) -> "Prompt":
        """Создаёт новый промпт.

        Параметры:
            name        — уникальное имя промпта (ВИ-2).
            messages    — структура сообщений для первой версии. Если передана,
                          первая версия создаётся автоматически (ВИ-2).
            description — комментарий к первой версии (опционально).
            tags        — список PromptTag для привязки (опционально).
            model_tags  — список ModelTag-объектов для привязки (опционально).

        Поднимает:
            KeyError — если промпт с таким именем уже существует (ВИ-2, альт. 3а).
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
        adapter_type: str | None = None,
    ):
        from prompthub.core.domain.prompt_messages import PromptMessages
        from prompthub.core.adapters.registry import get_adapter

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
        messages = PromptMessages(name=name, version=version_seq, content=content)

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
        """Удаляет промпт и всю его историю.

        Поднимает:
            KeyError — если промпт с таким именем не найден (ВИ-4, альт. 2а).
        """
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise KeyError(f"Промпт '{name}' не найден")

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
                content = prompt.get_version_content(latest["seq"])

            if not model_tag_rows:
                entry = {
                    **metadata,
                    "model_tags": None,
                    "costs": None,
                }
                result.append(entry)
                continue

            # Токены считаем токенизатором провайдера, цену берём из тарифов
            tariffs = self.repo.fetch_tariffs(model_tag_names)
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
        """Обновляет тарифы для всех моделей из внешнего источника (ВИ-17).

        Запрашивает все цены с OpenRouter и сохраняет их в БД без фильтрации.
        Это позволяет проверять наличие тарифа перед привязкой model_tag (ВИ-11).

        Поднимает:
            ConnectionError — если внешний источник недоступен.
            ValueError      — если полученные данные невалидны.
            RuntimeError    — если ошибка записи в БД.
        """
        from prompthub.infrastructure.pricing_gateway import PricingAPIGateway
        from prompthub.infrastructure.tariff_manager import TariffManager

        gateway = PricingAPIGateway(**({"url": url} if url else {}))
        all_tariffs = gateway.fetch_pricing_data()  # ConnectionError / ValueError
        return TariffManager(self._conn).bulk_upsert(all_tariffs)  # RuntimeError при ошибке БД

    def remove_model_tags(self, name: str, model_tags: list, commit: bool = True) -> list[str]:
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
            self.repo.delete_prompt_model_tag_links(prompt_id, to_remove, commit=commit)

        return to_remove

    def add_model_tags(self, name: str, model_tags: list, commit: bool = True) -> list[str]:
        """Привязывает ModelTag-объекты к промпту. Возвращает список добавленных имён.

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

        to_add = []
        for mt in model_tags:
            tag_name = mt.model_name
            if tag_name in current:
                warnings.warn(f"Тег '{tag_name}': дубликат — уже привязан к промпту")
            elif tag_name not in known_tariffs:
                warnings.warn(
                    f"Тег '{tag_name}': нет тарифа в системе — пропущен. "
                    f"Сначала вызовите update_tariffs()."
                )
            else:
                to_add.append({"name": tag_name, "provider": type(mt).provider_key})

        if to_add:
            self.repo.create_prompt_model_tag_links(prompt_id, to_add, commit=commit)

        return [t["name"] for t in to_add]
