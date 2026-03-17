from repository import Fields
from repository.queries import BaseQuery
from repository.query_factory import QueryFactory
from core.domain.operations import (
    Operation,
    InsertOperation,
    DeleteOperation, 
    ReplaceOperation,
)

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
        snapshot_interval: int = 5,
    ):
        self.id = id
        self.repo = repo
        self.tags = tags or []
        self.snapshot_interval = snapshot_interval

    def execute(self, query: BaseQuery):
        return self.repo.execute(query)

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

    def get_version_content(self, name: str) -> str:
        v = self.repo.get_version_by_name(self.id, name)
        if not v:
            raise ValueError("version not found")

        return self._assemble(v["seq"])

    def list_versions(self):
        return self.repo.list_versions(self.id)

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
            for op in changes:
                content = op.apply(content)

        return content

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