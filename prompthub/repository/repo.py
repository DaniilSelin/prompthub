import sqlite3
from typing import Any, cast

from prompthub.core.domain.operations import (
    DeleteOperation,
    InsertOperation,
    Operation,
    ReplaceOperation,
)
from prompthub.repository import (
    _INIT_SCHEMA_SQL,
    SNAPSHOT_INTERVAL,
    TAG_MODEL_TYPE,
    TAG_PROMPT_TYPE,
    Fields,
)
from prompthub.repository.queries import BaseQuery, SearchQuery
from prompthub.repository.types import (
    ExecuteResult,
    ModelTagRow,
    PromptIdRow,
    PromptMetadata,
    PromptRow,
    TagRow,
    TariffRow,
    VersionRangeRow,
    VersionRow,
)
from prompthub.search.filters import Condition


class PromptRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._init_schema()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]

    def _init_schema(self) -> None:
        self.conn.executescript(_INIT_SCHEMA_SQL)
        self.conn.commit()

    def execute(self, query: BaseQuery) -> ExecuteResult:
        sql, params = query.build()

        cur = self.conn.cursor()
        cur.execute(sql, params)

        if isinstance(query, SearchQuery):
            return self._rows_to_dicts(cur.fetchall())

        self.conn.commit()
        return cur.rowcount

    def create_prompt(self, name: str, commit: bool = True) -> int:
        cur = self.conn.cursor()

        cur.execute(
            f"""
                INSERT INTO {Fields._PROMPTS_TABLE}
                ({Fields.PROMPT_NAME}, snapshot_interval)
                VALUES (?, ?)
            """,
            (name, SNAPSHOT_INTERVAL),
        )

        if commit:
            self.conn.commit()
        return cast(int, cur.lastrowid)

    def get_prompt_by_name(self, name: str) -> PromptRow | None:
        cur = self.conn.cursor()

        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPTS_TABLE}
            WHERE {Fields.PROMPT_NAME} = ?
        """,
            (name,),
        )

        return cast(PromptRow | None, self._row_to_dict(cur.fetchone()))

    def delete_prompt(self, prompt_id: int) -> int:
        cur = self.conn.cursor()

        cur.execute(
            f"""
            DELETE FROM {Fields._PROMPTS_TABLE}
            WHERE {Fields._PROMPT_ID} = ?
        """,
            (prompt_id,),
        )

        self.conn.commit()
        return cur.rowcount

    def get_prompt(self, prompt_id: int) -> PromptRow | None:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPTS_TABLE}
            WHERE {Fields._PROMPT_ID} = ?
        """,
            (prompt_id,),
        )
        return cast(PromptRow | None, self._row_to_dict(cur.fetchone()))

    def get_latest_version(self, prompt_id: int) -> VersionRow | None:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
            ORDER BY seq DESC LIMIT 1
        """,
            (prompt_id,),
        )
        return cast(VersionRow | None, self._row_to_dict(cur.fetchone()))

    def get_version_by_name(self, prompt_id: int, name: str) -> VersionRow | None:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
              AND {Fields.PROMPT_VERSIONS_NAME} = ?
        """,
            (prompt_id, name),
        )
        return cast(VersionRow | None, self._row_to_dict(cur.fetchone()))

    def get_version_by_seq(self, prompt_id: int, seq: int) -> VersionRow | None:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
              AND seq = ?
        """,
            (prompt_id, seq),
        )
        return cast(VersionRow | None, self._row_to_dict(cur.fetchone()))

    def list_versions(self, prompt_id: int) -> list[VersionRow]:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT *
            FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
            ORDER BY seq ASC
        """,
            (prompt_id,),
        )
        return cast(list[VersionRow], self._rows_to_dicts(cur.fetchall()))

    def insert_version(
        self,
        prompt_id: int,
        name: str,
        seq: int,
        parent_id: int | None,
        snapshot_content: str | None,
        message: str | None,
        changes: list[Operation],
        commit: bool = True,
    ) -> int:
        cur = self.conn.cursor()

        cur.execute(
            f"""
            INSERT INTO {Fields._PROMPT_VERSIONS_TABLE}
            ({Fields.PROMPT_VERSIONS_PROMPT_ID}, {Fields.PROMPT_VERSIONS_NAME},
             seq, parent_version_id, snapshot_content,
             {Fields.PROMPT_VERSIONS_MESSAGE})
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (prompt_id, name, seq, parent_id, snapshot_content, message),
        )

        version_id = cast(int, cur.lastrowid)

        for i, op in enumerate(changes):
            self._insert_change(version_id, i, op)

        if commit:
            self.conn.commit()
        return version_id

    def delete_version(self, version_id: int) -> None:
        raw_row = self.conn.execute(
            f"SELECT prompt_id FROM {Fields._PROMPT_VERSIONS_TABLE} WHERE id = ?",
            (version_id,),
        ).fetchone()
        row = self._row_to_dict(cast(sqlite3.Row | None, raw_row))
        if row is None:
            raise ValueError(f"Версия с id={version_id} не найдена")

        count_row = self.conn.execute(
            f"SELECT COUNT(*) FROM {Fields._PROMPT_VERSIONS_TABLE} WHERE prompt_id = ?",
            (row["prompt_id"],),
        ).fetchone()
        count = int(cast(sqlite3.Row, count_row)[0])
        if count <= 1:
            raise ValueError("Нельзя удалить единственную версию промпта")

        cur = self.conn.cursor()
        cur.execute(
            f"DELETE FROM {Fields._PROMPT_VERSIONS_TABLE} WHERE id = ?", (version_id,)
        )
        self.conn.commit()

    def _insert_change(self, version_id: int, idx: int, op: Operation) -> None:
        cur = self.conn.cursor()

        if isinstance(op, InsertOperation):
            cur.execute(
                f"""
                INSERT INTO {Fields._PROMPT_CHANGES_TABLE} (version_id, op_index, op_type, pos, text)
                VALUES (?, ?, 'insert', ?, ?)
            """,
                (version_id, idx, op.pos, op.text),
            )

        elif isinstance(op, DeleteOperation):
            cur.execute(
                f"""
                INSERT INTO {Fields._PROMPT_CHANGES_TABLE} (version_id, op_index, op_type, start, end)
                VALUES (?, ?, 'delete', ?, ?)
            """,
                (version_id, idx, op.start, op.end),
            )

        elif isinstance(op, ReplaceOperation):
            cur.execute(
                f"""
                INSERT INTO {Fields._PROMPT_CHANGES_TABLE} (version_id, op_index, op_type, start, end, text)
                VALUES (?, ?, 'replace', ?, ?, ?)
            """,
                (version_id, idx, op.start, op.end, op.text),
            )

    def get_nearest_snapshot(self, prompt_id: int, seq: int) -> VersionRow | None:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
              AND snapshot_content IS NOT NULL
              AND seq <= ?
            ORDER BY seq DESC
            LIMIT 1
        """,
            (prompt_id, seq),
        )
        return cast(VersionRow | None, self._row_to_dict(cur.fetchone()))

    def get_versions_range(
        self, prompt_id: int, start: int, end: int
    ) -> list[VersionRangeRow]:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT id, seq FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
              AND seq >= ? AND seq <= ?
            ORDER BY seq ASC
        """,
            (prompt_id, start, end),
        )
        return cast(list[VersionRangeRow], self._rows_to_dicts(cur.fetchall()))

    def get_changes(self, version_id: int) -> list[Operation]:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPT_CHANGES_TABLE}
            WHERE version_id = ?
            ORDER BY op_index
        """,
            (version_id,),
        )

        ops: list[Operation] = []
        for r in cur.fetchall():
            if r["op_type"] == "insert":
                ops.append(InsertOperation(r["pos"], r["text"]))
            elif r["op_type"] == "delete":
                ops.append(DeleteOperation(r["start"], r["end"]))
            else:
                ops.append(ReplaceOperation(r["start"], r["end"], r["text"]))
        return ops

    def list_tags(self, prompt_id: int) -> list[TagRow]:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT t.{Fields.TAG_NAME}, t.{Fields.TAG_TYPE}, t.{Fields.TAG_PROVIDER}
            FROM {Fields._TAG_TABLE} t
            JOIN prompt_tags pt ON pt.tag_id = t.id
            WHERE pt.prompt_id = ?
            ORDER BY t.{Fields.TAG_TYPE}, t.{Fields.TAG_NAME}
        """,
            (prompt_id,),
        )
        return cast(list[TagRow], self._rows_to_dicts(cur.fetchall()))

    def execute_tag_filter_query(self, filter_obj: Condition) -> list[dict[str, Any]]:
        q = SearchQuery(Fields._PROMPTS_TABLE)
        q.filter(filter_obj)
        sql, params = q.build()
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return self._rows_to_dicts(cur.fetchall())

    def fetch_metadata(self, prompt_id: int) -> PromptMetadata:
        prompt = self.get_prompt(prompt_id)
        if prompt is None:
            raise KeyError(f"Промпт с id={prompt_id} не найден")
        tags = self.list_tags(prompt_id)
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT {Fields.PROMPT_VERSIONS_CREATED_AT}
            FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
            ORDER BY seq DESC LIMIT 1
        """,
            (prompt_id,),
        )
        last_ver = self._row_to_dict(cur.fetchone())
        model_tags: list[ModelTagRow] = [
            {"name": r["name"], "provider": r["provider"]}
            for r in tags
            if r["type"] == TAG_MODEL_TYPE
        ]
        return {
            "name": prompt["name"],
            "created_at": prompt["created_at"],
            "updated_at": cast(
                str | None, last_ver["created_at"] if last_ver else None
            ),
            "tags": [r["name"] for r in tags if r["type"] == TAG_PROMPT_TYPE],
            "model_tags": model_tags if model_tags else None,
        }

    def fetch_all_prompts(self) -> list[PromptIdRow]:
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT id FROM {Fields._PROMPTS_TABLE} ORDER BY {Fields.PROMPT_NAME}"
        )
        return cast(list[PromptIdRow], self._rows_to_dicts(cur.fetchall()))

    def fetch_tariffs(self, model_names: list[str]) -> dict[str, TariffRow]:
        if not model_names:
            return {}
        result: dict[str, TariffRow] = {}
        cur = self.conn.cursor()
        for name in model_names:
            cur.execute(
                "SELECT tag_name, input_price_per_1m, output_price_per_1m "
                "FROM model_tariffs "
                "WHERE tag_name = ? OR tag_name LIKE ? "
                "LIMIT 1",
                (name, f"%/{name}"),
            )
            row = cur.fetchone()
            if row:
                d = self._row_to_dict(row)
                result[name] = {
                    "tag_name": cast(str, d["tag_name"]),
                    "input_price_per_1m": float(d["input_price_per_1m"]),
                    "output_price_per_1m": float(d["output_price_per_1m"]),
                }
        return result

    def fetch_all_tags(self) -> list[TagRow]:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT {Fields.TAG_NAME}, {Fields.TAG_TYPE}, {Fields.TAG_PROVIDER}
            FROM {Fields._TAG_TABLE}
            ORDER BY {Fields.TAG_TYPE}, {Fields.TAG_NAME}
        """
        )
        return cast(list[TagRow], self._rows_to_dicts(cur.fetchall()))

    def fetch_all_model_tag_names(self) -> set[str]:
        """Возвращает имена всех model-тегов в БД (независимо от привязки к промпту)."""
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT {Fields.TAG_NAME} FROM {Fields._TAG_TABLE} WHERE {Fields.TAG_TYPE} = ?",
            (TAG_MODEL_TYPE,),
        )
        return {cast(str, r["name"]) for r in cur.fetchall()}

    def fetch_current_model_tags(self, prompt_id: int) -> set[str]:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT t.{Fields.TAG_NAME}
            FROM {Fields._TAG_TABLE} t
            JOIN prompt_tags pt ON pt.tag_id = t.id
            WHERE pt.prompt_id = ? AND t.{Fields.TAG_TYPE} = ?
        """,
            (prompt_id, TAG_MODEL_TYPE),
        )
        return {cast(str, r["name"]) for r in cur.fetchall()}

    def fetch_current_prompt_tags(self, prompt_id: int) -> set[str]:
        """Возвращает множество имён категорийных тегов, привязанных к промпту."""
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT t.{Fields.TAG_NAME}
            FROM {Fields._TAG_TABLE} t
            JOIN prompt_tags pt ON pt.tag_id = t.id
            WHERE pt.prompt_id = ? AND t.{Fields.TAG_TYPE} = ?
        """,
            (prompt_id, TAG_PROMPT_TYPE),
        )
        return {cast(str, r["name"]) for r in cur.fetchall()}

    def delete_prompt_model_tag_links(
        self, prompt_id: int, tag_names: list[str], commit: bool = True
    ) -> None:
        for name in tag_names:
            self.remove_tag(prompt_id, name, TAG_MODEL_TYPE, commit=False)
        if commit:
            self.conn.commit()

    def create_prompt_model_tag_links(
        self, prompt_id: int, tags: list[ModelTagRow], commit: bool = True
    ) -> None:
        """tags — список словарей {"name": ..., "provider": ...}"""
        for tag in tags:
            self.add_tag(
                prompt_id,
                tag["name"],
                TAG_MODEL_TYPE,
                tag.get("provider"),
                commit=False,
            )
        if commit:
            self.conn.commit()

    def add_tag(
        self,
        prompt_id: int,
        tag_name: str,
        tag_type: str,
        provider: str | None = None,
        commit: bool = True,
    ) -> None:
        cur = self.conn.cursor()

        cur.execute(
            f"""
            INSERT OR IGNORE INTO {Fields._TAG_TABLE}
                ({Fields.TAG_NAME}, {Fields.TAG_TYPE}, {Fields.TAG_PROVIDER})
            VALUES (?, ?, ?)
        """,
            (tag_name, tag_type, provider),
        )

        cur.execute(
            f"""
            INSERT OR IGNORE INTO prompt_tags (prompt_id, tag_id)
            SELECT ?, id FROM {Fields._TAG_TABLE}
            WHERE {Fields.TAG_NAME} = ? AND {Fields.TAG_TYPE} = ?
        """,
            (prompt_id, tag_name, tag_type),
        )

        if commit:
            self.conn.commit()

    def remove_tag(
        self, prompt_id: int, tag_name: str, tag_type: str, commit: bool = True
    ) -> None:
        cur = self.conn.cursor()

        cur.execute(
            f"""
            DELETE FROM prompt_tags
            WHERE prompt_id = ?
              AND tag_id IN (
                  SELECT id FROM {Fields._TAG_TABLE}
                  WHERE {Fields.TAG_NAME} = ? AND {Fields.TAG_TYPE} = ?
              )
        """,
            (prompt_id, tag_name, tag_type),
        )

        if commit:
            self.conn.commit()
