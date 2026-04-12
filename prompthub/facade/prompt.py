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
import sqlite3

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
    def _coerce_seq(version_seq: int | str) -> int:
        if isinstance(version_seq, int):
            return version_seq
        if isinstance(version_seq, str):
            if version_seq.startswith("v") and version_seq[1:].isdigit():
                return int(version_seq[1:])
            if version_seq.startswith("seq-") and version_seq[4:].isdigit():
                return int(version_seq[4:])
        raise TypeError("version_seq должен быть целым числом")

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
        description: str | None = None,
        commit: bool = True,
        *,
        name: str | None = None,
        message: str | None = None,
    ):
        if description is None:
            description = message

        self._validate_messages(content)
        serialized = self._serialize(content)

        def _insert_once() -> int:
            latest = self.repo.get_latest_version(self.id)

            if latest is None:
                return self.repo.insert_version(
                    prompt_id=self.id,
                    name="seq-1",
                    seq=1,
                    parent_id=None,
                    snapshot_content=serialized,
                    message=description,
                    changes=[],
                    commit=False,
                )

            prev_raw = self._assemble(latest["seq"])

            if prev_raw == serialized:
                return latest["id"]

            changes = self._build_changeset(prev_raw, serialized)
            new_seq = latest["seq"] + 1
            snapshot = serialized if new_seq % self.snapshot_interval == 0 else None

            return self.repo.insert_version(
                prompt_id=self.id,
                name=f"seq-{new_seq}",
                seq=new_seq,
                parent_id=latest["id"],
                snapshot_content=snapshot,
                message=description,
                changes=changes,
                commit=False,
            )

        if not commit:
            return _insert_once()

        # Если транзакция уже открыта выше по стеку — не начинаем новую.
        if self.repo.conn.in_transaction:
            return _insert_once()

        for _ in range(3):
            try:
                self.repo.conn.execute("BEGIN IMMEDIATE")
                version_id = _insert_once()
                self.repo.conn.commit()
                return version_id
            except sqlite3.IntegrityError:
                self.repo.conn.rollback()
            except sqlite3.OperationalError as e:
                self.repo.conn.rollback()
                if "locked" not in str(e).lower():
                    raise
            except Exception:
                self.repo.conn.rollback()
                raise

        raise RuntimeError("Не удалось добавить версию из-за конкурентной записи")

    def rollback_hard(
        self,
        target_seq: int | None = None,
        steps_back: int | None = None,
        name: str | None = None,
    ):
        versions = self.list_versions()
        if not versions:
            raise ValueError("Нет версий для отката")

        if target_seq is None and name is not None:
            target_seq = self._coerce_seq(name)

        if target_seq is not None:
            target = next((v for v in versions if v.seq == target_seq), None)
            if not target:
                raise ValueError(f"Версия seq={target_seq} не найдена")
        elif steps_back is not None:
            if steps_back < 0 or steps_back >= len(versions):
                raise ValueError(f"Некорректное количество шагов: {steps_back}")
            target = versions[-(steps_back + 1)]
        else:
            raise ValueError("Нужно указать target_seq или steps_back")

        for v in reversed(versions):
            if v.seq > target.seq:
                self.repo.delete_version(v.id)

        return target

    def rollback(
        self,
        target_seq: int | None = None,
        steps_back: int | None = None,
        description: str | None = None,
        name: str | None = None,
        name_rollback_version: str | None = None,
    ):
        import warnings as _warnings

        versions = self.list_versions()
        if not versions:
            raise ValueError("Нет версий для отката")

        if target_seq is None and name is not None:
            target_seq = self._coerce_seq(name)

        if target_seq is not None:
            target = next((v for v in versions if v.seq == target_seq), None)
            if not target:
                raise ValueError(f"Версия seq={target_seq} не найдена")
            rollback_version_content = self.get_version_content(target.seq)
        elif steps_back is not None:
            if steps_back < 0 or steps_back >= len(versions):
                raise ValueError(f"Некорректное количество шагов: {steps_back}")
            target = versions[-(steps_back + 1)]
            rollback_version_content = self.get_version_content(target.seq)
        else:
            raise ValueError("Нужно указать target_seq или steps_back")

        latest_id = self.repo.get_latest_version(self.id)["id"]
        result_id = self.add_version(
            content=rollback_version_content,
            description=description or f"rollback to seq {target.seq}",
        )

        # ВИ-8, альт. 7а: если содержимое целевой версии идентично актуальной
        if result_id == latest_id:
            _warnings.warn(
                f"Already at target state: откат на seq={target.seq} не нужен — "
                f"содержимое идентично актуальной версии.",
                stacklevel=2,
            )

        return result_id

    def _get_raw_content(self, version_seq: int) -> str:
        seq = self._coerce_seq(version_seq)
        v = self.repo.get_version_by_seq(self.id, seq)
        if not v:
            raise ValueError("version not found")
        return self._assemble(v["seq"])

    def get_version_content(self, version_seq: int | str) -> Messages:
        return self._deserialize(self._get_raw_content(version_seq))

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

    def add_prompt_tag(self, tag, commit: bool = True) -> None:
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
        self.repo.add_tag(self.id, value, TAG_PROMPT_TYPE, commit=commit)

    def remove_prompt_tag(self, tag, commit: bool = True) -> None:
        """Отвязывает PromptTag от промпта."""
        from prompthub.repository import TAG_PROMPT_TYPE
        value = tag.value if hasattr(tag, "value") else str(tag)
        self.repo.remove_tag(self.id, value, TAG_PROMPT_TYPE, commit=commit)

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

    def compare_versions(self, seq_a: int | str, seq_b: int | str) -> VersionLineDiff:
        seq_a = self._coerce_seq(seq_a)
        seq_b = self._coerce_seq(seq_b)
        raw_a = self._get_raw_content(seq_a)
        raw_b = self._get_raw_content(seq_b)

        label_a = f"seq-{seq_a}"
        label_b = f"seq-{seq_b}"

        hunks = list(
            difflib.unified_diff(
                raw_a.splitlines(keepends=True),
                raw_b.splitlines(keepends=True),
                fromfile=label_a,
                tofile=label_b,
            )
        )

        return VersionLineDiff(name_a=label_a, name_b=label_b, hunks=hunks)

    def compare_versions_chars(self, seq_a: int | str, seq_b: int | str) -> VersionDiff:
        seq_a = self._coerce_seq(seq_a)
        seq_b = self._coerce_seq(seq_b)
        raw_a = self._get_raw_content(seq_a)
        raw_b = self._get_raw_content(seq_b)

        label_a = f"seq-{seq_a}"
        label_b = f"seq-{seq_b}"

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

        return VersionDiff(name_a=label_a, name_b=label_b, chunks=chunks)

    def compare_versions_structured(self, seq_a: int | str, seq_b: int | str) -> StructuredDiff:
        """Структурное сравнение двух версий на уровне сообщений (ВИ-7).

        Возвращает StructuredDiff с:
          - added   — сообщения, присутствующие только в seq_b
          - deleted — сообщения, присутствующие только в seq_a
          - changed — сообщения с изменённым content (при совпадении роли по позиции)
        """
        seq_a = self._coerce_seq(seq_a)
        seq_b = self._coerce_seq(seq_b)
        msgs_a = self.get_version_content(seq_a)
        msgs_b = self.get_version_content(seq_b)

        label_a = f"seq-{seq_a}"
        label_b = f"seq-{seq_b}"

        added: list[tuple[str, str]] = []
        deleted: list[tuple[str, str]] = []
        changed: list[ChangedMessage] = []

        len_a, len_b = len(msgs_a), len(msgs_b)
        common = min(len_a, len_b)

        for i in range(common):
            role_a, content_a = msgs_a[i]
            role_b, content_b = msgs_b[i]

            if role_a != role_b:
                deleted.append((role_a, content_a))
                added.append((role_b, content_b))
            elif content_a != content_b:
                line_diff = list(
                    difflib.unified_diff(
                        content_a.splitlines(keepends=True),
                        content_b.splitlines(keepends=True),
                        fromfile=f"{label_a}[{i}]",
                        tofile=f"{label_b}[{i}]",
                    )
                )
                changed.append(
                    ChangedMessage(
                        index=i,
                        role=role_a,
                        old_content=content_a,
                        new_content=content_b,
                        line_diff=line_diff,
                    )
                )

        for role, content in msgs_a[common:]:
            deleted.append((role, content))

        for role, content in msgs_b[common:]:
            added.append((role, content))

        return StructuredDiff(
            name_a=label_a,
            name_b=label_b,
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
