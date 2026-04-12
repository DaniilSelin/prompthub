from prompthub.repository import Fields
from prompthub.repository import SNAPSHOT_INTERVAL
from prompthub.repository.queries import BaseQuery
from prompthub.repository.query_factory import QueryFactory
from prompthub.core.domain.operations import (
    InsertOperation,
    DeleteOperation,
    ReplaceOperation,
)
from prompthub.core.domain.diff import DiffChunk, VersionDiff, VersionLineDiff, StructuredDiff, ChangedMessage

import difflib
import json

Messages = list[tuple[str, str]]


class PromptVersion:
    def __init__(
        self,
        id: int,
        prompt_id: int,
        name: str,
        seq: int,
        parent_id: int | None,
        snapshot_content: str | None,
        message: str | None,
        created_at: str,
    ):
        self.id = id
        self.prompt_id = prompt_id
        self.name = name
        self.seq = seq
        self.parent_id = parent_id
        self.snapshot_content = snapshot_content
        self.message = message
        self.created_at = created_at

    @property
    def is_snapshot(self) -> bool:
        return self.snapshot_content is not None

    def __repr__(self):
        return f"<PromptVersion {self.name} seq={self.seq} snapshot={self.is_snapshot}>"


class Prompt(QueryFactory):
    table: str = Fields._PROMPT_VERSIONS_TABLE

    def __init__(
        self,
        id: int,
        repo,
        tags: list | None = None,
    ):
        self.id = id
        self.repo = repo
        self.tags = tags or []
        self.snapshot_interval = SNAPSHOT_INTERVAL

    def execute(self, query: BaseQuery):
        return self.repo.execute(query)

    @staticmethod
    def _validate_messages(messages: Messages):
        if not isinstance(messages, list) or not messages:
            raise ValueError("content должен быть непустым списком сообщений")
        for msg in messages:
            if (
                not isinstance(msg, (tuple, list))
                or len(msg) != 2
                or not isinstance(msg[0], str)
                or not isinstance(msg[1], str)
            ):
                raise ValueError(
                    "Каждое сообщение должно быть кортежем (role, content)"
                )

    @staticmethod
    def _serialize(messages: Messages) -> str:
        return json.dumps([list(m) for m in messages], ensure_ascii=False)

    @staticmethod
    def _deserialize(text: str) -> Messages:
        return [tuple(item) for item in json.loads(text)]

    def add_version(
        self,
        content: Messages,
        name: str,
        message: str | None = None,
    ):
        self._validate_messages(content)
        serialized = self._serialize(content)

        latest = self.repo.get_latest_version(self.id)

        if latest is None:
            return self.repo.insert_version(
                prompt_id=self.id,
                name=name,
                seq=1,
                parent_id=None,
                snapshot_content=serialized,
                message=message,
                changes=[],
            )

        prev_raw = self._assemble(latest["seq"])

        if prev_raw == serialized:
            return latest["id"]

        changes = self._build_changeset(prev_raw, serialized)
        new_seq = latest["seq"] + 1

        snapshot = serialized if new_seq % self.snapshot_interval == 0 else None

        return self.repo.insert_version(
            prompt_id=self.id,
            name=name,
            seq=new_seq,
            parent_id=latest["id"],
            snapshot_content=snapshot,
            message=message,
            changes=changes,
        )

    def rollback_hard(self, name: str | None = None, steps_back: int | None = None):
        versions = self.list_versions()
        if not versions:
            raise ValueError("Нет версий для отката")

        if name:
            target = next((v for v in versions if v.name == name), None)
            if not target:
                raise ValueError(f"Версия {name} не найдена")
        elif steps_back is not None:
            if steps_back < 0 or steps_back >= len(versions):
                raise ValueError(f"Некорректное количество шагов: {steps_back}")
            target = versions[-(steps_back + 1)]
        else:
            raise ValueError("Нужно указать name или steps_back")

        for v in reversed(versions):
            if v.seq > target.seq:
                self.repo.delete_version(v.id)

        return target

    def rollback(
        self,
        name: str | None = None,
        steps_back: int | None = None,
        name_rollback_version: str = "rollback_version",
    ):
        import warnings as _warnings
        versions = self.list_versions()
        if not versions:
            raise ValueError("Нет версий для отката")

        if name:
            target = next((v for v in versions if v.name == name), None)
            if not target:
                raise ValueError(f"Версия {name} не найдена")
            rollback_version_content = self.get_version_content(target.name)
        elif steps_back is not None:
            if steps_back < 0 or steps_back >= len(versions):
                raise ValueError(f"Некорректное количество шагов: {steps_back}")
            target = versions[-(steps_back + 1)]
            rollback_version_content = self.get_version_content(target.name)
        else:
            raise ValueError("Нужно указать name или steps_back")

        latest_id = self.repo.get_latest_version(self.id)["id"]
        result_id = self.add_version(
            content=rollback_version_content,
            name=name_rollback_version,
            message="rollback to " + target.name,
        )

        # ВИ-8, альт. 7а: если содержимое целевой версии идентично актуальной
        if result_id == latest_id:
            _warnings.warn(
                f"Already at target state: откат на '{target.name}' не нужен — "
                f"содержимое идентично актуальной версии.",
                stacklevel=2,
            )

        return result_id

    def _get_raw_content(self, name: str) -> str:
        v = self.repo.get_version_by_name(self.id, name)
        if not v:
            raise ValueError("version not found")
        return self._assemble(v["seq"])

    def get_version_content(self, name: str) -> Messages:
        return self._deserialize(self._get_raw_content(name))

    def list_versions(self) -> list["PromptVersion"]:
        rows = self.repo.list_versions(self.id)
        return [
            PromptVersion(
                id=r["id"],
                prompt_id=r["prompt_id"],
                name=r["name"],
                seq=r["seq"],
                parent_id=r["parent_version_id"],
                snapshot_content=r["snapshot_content"],
                message=r["message"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def list_tags(self) -> list[dict]:
        from prompthub.repository import Fields
        rows = self.repo.list_tags(self.id)
        return [
            {
                "name": r[Fields.TAG_NAME],
                "type": r[Fields.TAG_TYPE],
                "provider": r[Fields.TAG_PROVIDER],
            }
            for r in rows
        ]

    def add_model_tag(self, model_tag) -> None:
        """Привязывает ModelTag к промпту. Провайдер определяется из класса объекта."""
        from prompthub.repository import TAG_MODEL_TYPE
        provider_key = type(model_tag).provider_key
        self.repo.add_tag(self.id, model_tag.model_name, TAG_MODEL_TYPE, provider_key)

    def remove_model_tag(self, model_tag) -> None:
        """Отвязывает ModelTag от промпта."""
        from prompthub.repository import TAG_MODEL_TYPE
        self.repo.remove_tag(self.id, model_tag.model_name, TAG_MODEL_TYPE)

    def add_prompt_tag(self, tag) -> None:
        """Привязывает PromptTag (категорийный тег) к промпту.

        Если тег уже привязан — выдаёт предупреждение и пропускает (ВИ-9, альт. 4а).
        """
        import warnings
        from prompthub.repository import TAG_PROMPT_TYPE
        value = tag.value if hasattr(tag, "value") else str(tag)
        current = self.repo.fetch_current_prompt_tags(self.id)
        if value in current:
            warnings.warn(
                f"Тег '{value}': уже привязан к промпту — пропущен",
                stacklevel=2,
            )
            return
        self.repo.add_tag(self.id, value, TAG_PROMPT_TYPE)

    def remove_prompt_tag(self, tag) -> None:
        """Отвязывает PromptTag от промпта."""
        from prompthub.repository import TAG_PROMPT_TYPE
        value = tag.value if hasattr(tag, "value") else str(tag)
        self.repo.remove_tag(self.id, value, TAG_PROMPT_TYPE)

    def _assemble(self, target_seq: int) -> str:
        snapshot = self.repo.get_nearest_snapshot(self.id, target_seq)

        if snapshot:
            content = snapshot["snapshot_content"]
            start_seq = snapshot["seq"] + 1
        else:
            content = ""
            start_seq = 1

        versions = self.repo.get_versions_range(self.id, start_seq, target_seq)

        for v in versions:
            changes = self.repo.get_changes(v["id"])
            for op in reversed(changes):
                content = op.apply(content)

        return content

    def compare_versions(self, name_a: str, name_b: str) -> VersionLineDiff:
        raw_a = self._get_raw_content(name_a)
        raw_b = self._get_raw_content(name_b)

        hunks = list(
            difflib.unified_diff(
                raw_a.splitlines(keepends=True),
                raw_b.splitlines(keepends=True),
                fromfile=name_a,
                tofile=name_b,
            )
        )

        return VersionLineDiff(name_a=name_a, name_b=name_b, hunks=hunks)

    def compare_versions_chars(self, name_a: str, name_b: str) -> VersionDiff:
        raw_a = self._get_raw_content(name_a)
        raw_b = self._get_raw_content(name_b)

        sm = difflib.SequenceMatcher(None, raw_a, raw_b)
        chunks = [
            DiffChunk(
                tag=tag,
                old_start=i1,
                old_end=i2,
                new_start=j1,
                new_end=j2,
                old_text=raw_a[i1:i2],
                new_text=raw_b[j1:j2],
            )
            for tag, i1, i2, j1, j2 in sm.get_opcodes()
        ]

        return VersionDiff(name_a=name_a, name_b=name_b, chunks=chunks)

    def compare_versions_structured(self, name_a: str, name_b: str) -> StructuredDiff:
        """Структурное сравнение двух версий на уровне сообщений (ВИ-7).

        Возвращает StructuredDiff с:
          - added   — сообщения, присутствующие только в name_b
          - deleted — сообщения, присутствующие только в name_a
          - changed — сообщения с изменённым content (при совпадении роли по позиции)
        """
        msgs_a = self.get_version_content(name_a)
        msgs_b = self.get_version_content(name_b)

        added: list[tuple[str, str]] = []
        deleted: list[tuple[str, str]] = []
        changed: list[ChangedMessage] = []

        len_a, len_b = len(msgs_a), len(msgs_b)
        common = min(len_a, len_b)

        for i in range(common):
            role_a, content_a = msgs_a[i]
            role_b, content_b = msgs_b[i]

            if role_a != role_b:
                # Роли различаются — удаление старого, добавление нового
                deleted.append((role_a, content_a))
                added.append((role_b, content_b))
            elif content_a != content_b:
                line_diff = list(
                    difflib.unified_diff(
                        content_a.splitlines(keepends=True),
                        content_b.splitlines(keepends=True),
                        fromfile=f"{name_a}[{i}]",
                        tofile=f"{name_b}[{i}]",
                    )
                )
                changed.append(ChangedMessage(
                    index=i,
                    role=role_a,
                    old_content=content_a,
                    new_content=content_b,
                    line_diff=line_diff,
                ))

        # Дополнительные сообщения в name_a (удалённые)
        for role, content in msgs_a[common:]:
            deleted.append((role, content))

        # Дополнительные сообщения в name_b (добавленные)
        for role, content in msgs_b[common:]:
            added.append((role, content))

        return StructuredDiff(
            name_a=name_a,
            name_b=name_b,
            added=added,
            deleted=deleted,
            changed=changed,
        )

    def _build_changeset(self, old: str, new: str):
        ops = []
        sm = difflib.SequenceMatcher(None, old, new)

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            if tag == "insert":
                ops.append(InsertOperation(i1, new[j1:j2]))
            elif tag == "delete":
                ops.append(DeleteOperation(i1, i2))
            elif tag == "replace":
                ops.append(ReplaceOperation(i1, i2, new[j1:j2]))

        return ops
