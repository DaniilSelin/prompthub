from repository import Fields
from repository import SNAPSHOT_INTERVAL
from repository.queries import BaseQuery
from repository.query_factory import QueryFactory
from core.domain.operations import (
    InsertOperation,
    DeleteOperation,
    ReplaceOperation,
)
from core.domain.diff import DiffChunk, VersionDiff, VersionLineDiff

import difflib


class PromptVersion:
    def __init__(
        self,
        id: int,
        prompt_id: int,
        name: str,
        seq: int,
        parent_id: int | None,
        snapshot_content: str | None,
        author: str | None,
        message: str | None,
        created_at: str,
    ):
        self.id = id
        self.prompt_id = prompt_id
        self.name = name
        self.seq = seq
        self.parent_id = parent_id
        self.snapshot_content = snapshot_content
        self.author = author
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

    def add_version(
        self,
        content: str,
        name: str,
        author: str | None = None,
        message: str | None = None,
    ):
        latest = self.repo.get_latest_version(self.id)

        if latest is None:
            return self.repo.insert_version(
                prompt_id=self.id,
                name=name,
                seq=1,
                parent_id=None,
                snapshot_content=content,
                author=author,
                message=message,
                changes=[],
            )

        prev_content = self.get_version_content(latest[Fields.PROMPT_VERSIONS_NAME])

        if prev_content == content:
            raise ValueError("Новая версия не отличается от предыдущей")

        changes = self._build_changeset(prev_content, content)
        new_seq = latest["seq"] + 1

        snapshot = content if new_seq % self.snapshot_interval == 0 else None

        return self.repo.insert_version(
            prompt_id=self.id,
            name=name,
            seq=new_seq,
            parent_id=latest["id"],
            snapshot_content=snapshot,
            author=author,
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

        for v in versions:
            if v.seq > target.seq:
                self.repo.delete_version(v.id)

        return target

    def rollback(
        self,
        name: str | None = None,
        steps_back: int | None = None,
        name_rollback_version: str = "rollback_version",
        author: str | None = None,
    ):
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

        return self.add_version(
            content=rollback_version_content,
            name=name_rollback_version,
            author=author,
            message="rollback to " + target.name,
        )

    def get_version_content(self, name: str) -> str:
        v = self.repo.get_version_by_name(self.id, name)
        if not v:
            raise ValueError("version not found")

        return self._assemble(v["seq"])

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
                author=r["author"],
                message=r["message"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def add_tag(self, tag_name: str, tag_type: str):
        self.repo.add_tag(self.id, tag_name, tag_type)

    def remove_tag(self, tag_name: str, tag_type: str):
        self.repo.remove_tag(self.id, tag_name, tag_type)

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
        content_a = self.get_version_content(name_a)
        content_b = self.get_version_content(name_b)

        hunks = list(
            difflib.unified_diff(
                content_a.splitlines(keepends=True),
                content_b.splitlines(keepends=True),
                fromfile=name_a,
                tofile=name_b,
            )
        )

        return VersionLineDiff(name_a=name_a, name_b=name_b, hunks=hunks)

    def compare_versions_chars(self, name_a: str, name_b: str) -> VersionDiff:
        content_a = self.get_version_content(name_a)
        content_b = self.get_version_content(name_b)

        sm = difflib.SequenceMatcher(None, content_a, content_b)
        chunks = [
            DiffChunk(
                tag=tag,
                old_start=i1,
                old_end=i2,
                new_start=j1,
                new_end=j2,
                old_text=content_a[i1:i2],
                new_text=content_b[j1:j2],
            )
            for tag, i1, i2, j1, j2 in sm.get_opcodes()
        ]

        return VersionDiff(name_a=name_a, name_b=name_b, chunks=chunks)

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
