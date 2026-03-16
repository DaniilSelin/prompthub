from typing import Any
from datetime import datetime

from repository.queries import BaseQuery, SearchQuery
from repository.query_factory import QueryFactory
from core.domain.operations import (
    Operation,
    InsertOperation,
    DeleteOperation, 
    ReplaceOperation,
)

import sqlite3
import difflib

"""
неудача 2. перепишу так же потом.
"""

class PromptVersion:
    def __init__(
        self,
        version_id: str,
        parent_id: str | None,
        change_set: list[Operation] | None = None,
        is_snapshot: bool = False,
        snapshot_content: str | None = None,
        meta: dict[str, Any] | None = None,
    ):
        self.version_id: str = version_id
        self.parent_id: str | None = parent_id
        self.change_set: list[Operation] = change_set or []
        self.is_snapshot: bool = is_snapshot
        self.snapshot_content: str | None = snapshot_content
        self.meta: dict[str, Any] = meta or {}
        if "timestamp" not in self.meta:
            self.meta["timestamp"] = datetime.utcnow().isoformat()

    def apply_to(self, content: str) -> str:
        out = content
        for op in self.change_set:
            out = op.apply(out)
        return out

    def __repr__(self) -> str:
        return f"PromptVersion(id={self.version_id!r}, parent={self.parent_id!r}, ops={len(self.change_set)}, snapshot={self.is_snapshot})"

class Prompt(QueryFactory):
    tabel: str = "prompt_versions"

    def __init__(self, id: str, db_path: str, tags: list | None = None, snapshot_interval: int = 10):
        self.id: str = id
        self.tags = tags or []
        self._versions_list: list[PromptVersion] = []
        self._versions_map: dict[str, PromptVersion] = {}
        self._next_int: int = 1
        self.snapshot_interval = max(1, snapshot_interval)
        
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row

    def execute(self, query: BaseQuery):
        sql, params = query.build()

        cur = self._conn.cursor()
        cur.execute(sql, params)

        if isinstance(query, SearchQuery):
            rows = cur.fetchall()
            return [dict(r) for r in rows]

        self._conn.commit()
        return cur.rowcount

    def _make_new_id(self) -> str:
        vid = str(self._next_int)
        self._next_int += 1
        return vid

    def _build_changeset(self, old: str, new: str) -> list[Operation]:
        ops: list[Operation] = []

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

    def add_version(
        self,
        new_content: str,
        author: str | None = None,
        message: str | None = None,
    ) -> PromptVersion:

        parent = self._versions_list[-1].version_id if self._versions_list else None
        vid = self._make_new_id()

        if parent is None:
            pv = PromptVersion(
                version_id=vid,
                parent_id=None,
                change_set=[],
                is_snapshot=True,
                snapshot_content=new_content,
                meta={"author": author, "message": message},
            )
        else:
            prev_content = self.assemble_version(parent)

            change_set = self._build_changeset(prev_content, new_content)

            pv = PromptVersion(
                version_id=vid,
                parent_id=parent,
                change_set=change_set,
                is_snapshot=False,
                snapshot_content=None,
                meta={"author": author, "message": message},
            )

        self._versions_list.append(pv)
        self._versions_map[vid] = pv

        self._maybe_create_snapshot()

        return pv

    def _maybe_create_snapshot(self):
        last_snapshot_index = -1
        for i in range(len(self._versions_list) - 1, -1, -1):
            if self._versions_list[i].is_snapshot:
                last_snapshot_index = i
                break

        distance = len(self._versions_list) - 1 - last_snapshot_index
        if distance >= self.snapshot_interval:
            last = self._versions_list[-1]
            if not last.is_snapshot:
                content = self.assemble_version(last.version_id)
                snap_id = self._make_new_id()
                snap = PromptVersion(
                    version_id=snap_id,
                    parent_id=last.version_id,
                    change_set=[],
                    is_snapshot=True,
                    snapshot_content=content,
                    meta={"auto_snapshot": True, "timestamp": datetime.utcnow().isoformat()},
                )
                self._versions_list.append(snap)
                self._versions_map[snap_id] = snap

    def get_version(self, version_id: str | None) -> PromptVersion | None:
        if version_id is None:
            return None
        return self._versions_map.get(version_id)

    def latest_version_ref(self) -> str | None:
        return self._versions_list[-1].version_id if self._versions_list else None

    def list_versions(self) -> list[PromptVersion]:
        return list(self._versions_list)

    def assemble_version(self, version_id: str | None) -> str:
        if version_id is None:
            return ""

        target = self.get_version(version_id)
        if target is None:
            raise ValueError(f"version {version_id!r} not found")

        chain: list[PromptVersion] = []
        node = target
        base_content: str | None = None
        
        while node is not None:
            chain.append(node)
            if node.is_snapshot and node.snapshot_content is not None:
                base_content = node.snapshot_content
                break
            if node.parent_id is None:
                break
            node = self.get_version(node.parent_id)
            if node is None:
                raise ValueError(f"Broken chain: parent {node.parent_id} not found")

        if base_content is None:
            base_content = ""
            forward_chain = list(reversed(chain))
        else:
            snapshot_index = -1
            for i, v in enumerate(chain):
                if v.is_snapshot and v.snapshot_content is not None:
                    snapshot_index = i
                    break
            
            if snapshot_index == -1:
                forward_chain = list(reversed(chain))
            else:
                forward_chain = list(reversed(chain[:snapshot_index]))
        
        content = base_content
        for v in forward_chain:
            if v.is_snapshot and v.snapshot_content is not None:
                content = v.snapshot_content
            else:
                content = v.apply_to(content)
        
        return content

    def create_initial_version(
        self,
        content: str,
        author: str | None = None,
        message: str | None = None
    ) -> PromptVersion:
        vid = self._make_new_id()
        pv = PromptVersion(version_id=vid, parent_id=None, change_set=[], is_snapshot=True, snapshot_content=content, meta={"author": author, "message": message})
        self._versions_list.append(pv)
        self._versions_map[vid] = pv
        return pv

    def find_version_by_meta(self, key: str, value: Any) -> PromptVersion | None:
        for v in self._versions_list:
            if v.meta.get(key) == value:
                return v
        return None