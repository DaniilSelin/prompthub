import sqlite3

from prompthub.core.domain.operations import (
    InsertOperation,
    DeleteOperation,
    ReplaceOperation,
    Operation,
)
from prompthub.repository import Fields, _INIT_SCHEMA_SQL, SNAPSHOT_INTERVAL, TAG_MODEL_TYPE
from prompthub.repository.queries import BaseQuery, SearchQuery


class PromptRepo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(_INIT_SCHEMA_SQL)
        # миграция: добавить колонки если существующая БД создана без них
        for col, definition in [
            ("input_price_per_1k", "REAL DEFAULT 0.0"),
            ("output_price_per_1k", "REAL DEFAULT 0.0"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
        ]:
            try:
                self.conn.execute(
                    f"ALTER TABLE model_tariffs ADD COLUMN {col} {definition}"
                )
            except Exception:
                pass  # колонка уже существует
        self.conn.commit()

    def execute(self, query: BaseQuery):
        sql, params = query.build()

        cur = self.conn.cursor()
        cur.execute(sql, params)

        if isinstance(query, SearchQuery):
            return [dict(r) for r in cur.fetchall()]

        self.conn.commit()
        return cur.rowcount

    def create_prompt(
        self,
        name: str,
        author: str | None = None,
    ) -> int:
        cur = self.conn.cursor()

        cur.execute(
            f"""
                INSERT INTO {Fields._PROMPTS_TABLE}
                ({Fields.PROMPT_NAME}, {Fields.PROMPT_AUTHOR}, snapshot_interval)
                VALUES (?, ?, ?)
            """,
            (name, author, SNAPSHOT_INTERVAL),
        )

        self.conn.commit()
        return cur.lastrowid

    def get_prompt_by_name(self, name: str):
        cur = self.conn.cursor()

        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPTS_TABLE}
            WHERE {Fields.PROMPT_NAME} = ?
        """,
            (name,),
        )

        return cur.fetchone()

    def find_by_name_exact(self, name: str):
        return self.get_prompt_by_name(name)

    def delete_prompt(self, prompt_id: int):
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

    def get_prompt(self, prompt_id: int):
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPTS_TABLE}
            WHERE {Fields._PROMPT_ID} = ?
        """,
            (prompt_id,),
        )
        return cur.fetchone()

    def get_latest_version(self, prompt_id: int):
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
            ORDER BY seq DESC LIMIT 1
        """,
            (prompt_id,),
        )
        return cur.fetchone()

    def get_version_by_name(self, prompt_id: int, name: str):
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT * FROM {Fields._PROMPT_VERSIONS_TABLE}
            WHERE {Fields.PROMPT_VERSIONS_PROMPT_ID} = ?
              AND {Fields.PROMPT_VERSIONS_NAME} = ?
        """,
            (prompt_id, name),
        )
        return cur.fetchone()

    def list_versions(self, prompt_id: int):
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
        return cur.fetchall()

    def insert_version(
        self,
        prompt_id: int,
        name: str,
        seq: int,
        parent_id: int | None,
        snapshot_content: str | None,
        author: str | None,
        message: str | None,
        changes: list[Operation],
    ):
        cur = self.conn.cursor()

        cur.execute(
            f"""
            INSERT INTO {Fields._PROMPT_VERSIONS_TABLE}
            ({Fields.PROMPT_VERSIONS_PROMPT_ID}, {Fields.PROMPT_VERSIONS_NAME},
             seq, parent_version_id, snapshot_content,
             {Fields.PROMPT_VERSIONS_AUTHOR}, {Fields.PROMPT_VERSIONS_MESSAGE})
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (prompt_id, name, seq, parent_id, snapshot_content, author, message),
        )

        version_id = cur.lastrowid

        for i, op in enumerate(changes):
            self._insert_change(version_id, i, op)

        self.conn.commit()
        return version_id

    def delete_version(self, version_id: int):
        row = self.conn.execute(
            f"SELECT prompt_id FROM {Fields._PROMPT_VERSIONS_TABLE} WHERE id = ?",
            (version_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Версия с id={version_id} не найдена")

        count = self.conn.execute(
            f"SELECT COUNT(*) FROM {Fields._PROMPT_VERSIONS_TABLE} WHERE prompt_id = ?",
            (row["prompt_id"],),
        ).fetchone()[0]
        if count <= 1:
            raise ValueError("Нельзя удалить единственную версию промпта")

        cur = self.conn.cursor()
        cur.execute(
            f"DELETE FROM {Fields._PROMPT_VERSIONS_TABLE} WHERE id = ?", (version_id,)
        )
        self.conn.commit()

    def _insert_change(self, version_id: int, idx: int, op: Operation):
        cur = self.conn.cursor()

        if isinstance(op, InsertOperation):
            cur.execute(
                """
                INSERT INTO prompt_changes (version_id, op_index, op_type, pos, text)
                VALUES (?, ?, 'insert', ?, ?)
            """,
                (version_id, idx, op.pos, op.text),
            )

        elif isinstance(op, DeleteOperation):
            cur.execute(
                """
                INSERT INTO prompt_changes (version_id, op_index, op_type, start, end)
                VALUES (?, ?, 'delete', ?, ?)
            """,
                (version_id, idx, op.start, op.end),
            )

        elif isinstance(op, ReplaceOperation):
            cur.execute(
                """
                INSERT INTO prompt_changes (version_id, op_index, op_type, start, end, text)
                VALUES (?, ?, 'replace', ?, ?, ?)
            """,
                (version_id, idx, op.start, op.end, op.text),
            )

    def get_nearest_snapshot(self, prompt_id: int, seq: int):
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
        return cur.fetchone()

    def get_versions_range(self, prompt_id: int, start: int, end: int):
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
        return cur.fetchall()

    def get_changes(self, version_id: int) -> list[Operation]:
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT * FROM prompt_changes
            WHERE version_id = ?
            ORDER BY op_index
        """,
            (version_id,),
        )

        ops = []
        for r in cur.fetchall():
            if r["op_type"] == "insert":
                ops.append(InsertOperation(r["pos"], r["text"]))
            elif r["op_type"] == "delete":
                ops.append(DeleteOperation(r["start"], r["end"]))
            else:
                ops.append(ReplaceOperation(r["start"], r["end"], r["text"]))
        return ops

    def list_tags(self, prompt_id: int):
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT t.{Fields.TAG_NAME}, t.{Fields.TAG_TYPE}
            FROM {Fields._TAG_TABLE} t
            JOIN prompt_tags pt ON pt.tag_id = t.id
            WHERE pt.prompt_id = ?
            ORDER BY t.{Fields.TAG_TYPE}, t.{Fields.TAG_NAME}
        """,
            (prompt_id,),
        )
        return cur.fetchall()

    def execute_tag_filter_query(self, filter_obj) -> list:
        from repository.queries import SearchQuery

        q = SearchQuery(Fields._PROMPTS_TABLE)
        q.filter(filter_obj)
        sql, params = q.build()
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def fetch_metadata(self, prompt_id: int) -> dict:
        prompt = self.get_prompt(prompt_id)
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
        last_ver = cur.fetchone()
        return {
            "name": prompt["name"],
            "author": prompt["author"],
            "created_at": prompt["created_at"],
            "updated_at": last_ver["created_at"] if last_ver else None,
            "tags": [r["name"] for r in tags if r["type"] == "prompt"],
            "model_tags": [r["name"] for r in tags if r["type"] == "model"],
        }

    def fetch_all_prompts(self) -> list:
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT id FROM {Fields._PROMPTS_TABLE} ORDER BY {Fields.PROMPT_NAME}"
        )
        return cur.fetchall()

    def fetch_tariffs(self, tag_names: list[str]) -> dict:
        if not tag_names:
            return {}
        placeholders = ",".join("?" * len(tag_names))
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT tag_name, input_price_per_1k, output_price_per_1k "
            f"FROM model_tariffs WHERE tag_name IN ({placeholders})",
            tag_names,
        )
        return {r["tag_name"]: r for r in cur.fetchall()}

    def fetch_all_tags(self) -> list:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            SELECT {Fields.TAG_NAME}, {Fields.TAG_TYPE}
            FROM {Fields._TAG_TABLE}
            ORDER BY {Fields.TAG_TYPE}, {Fields.TAG_NAME}
        """
        )
        return cur.fetchall()

    def register_tariff(self, tag_name: str):
        cur = self.conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO model_tariffs (tag_name) VALUES (?)
        """,
            (tag_name,),
        )
        self.conn.commit()

    def fetch_available_tariffs(self) -> set[str]:
        cur = self.conn.cursor()
        cur.execute("SELECT tag_name FROM model_tariffs")
        return {r["tag_name"] for r in cur.fetchall()}

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
        return {r["name"] for r in cur.fetchall()}

    def delete_prompt_model_tag_links(self, prompt_id: int, tag_names: list[str]):
        for name in tag_names:
            self.remove_tag(prompt_id, name, TAG_MODEL_TYPE)

    def create_prompt_model_tag_links(self, prompt_id: int, tag_names: list[str]):
        for name in tag_names:
            self.add_tag(prompt_id, name, TAG_MODEL_TYPE)

    def add_tag(self, prompt_id: int, tag_name: str, tag_type: str):
        cur = self.conn.cursor()

        cur.execute(
            f"""
            INSERT OR IGNORE INTO {Fields._TAG_TABLE} ({Fields.TAG_NAME}, {Fields.TAG_TYPE})
            VALUES (?, ?)
        """,
            (tag_name, tag_type),
        )

        cur.execute(
            f"""
            INSERT OR IGNORE INTO prompt_tags (prompt_id, tag_id)
            SELECT ?, id FROM {Fields._TAG_TABLE}
            WHERE {Fields.TAG_NAME} = ? AND {Fields.TAG_TYPE} = ?
        """,
            (prompt_id, tag_name, tag_type),
        )

        self.conn.commit()

    def remove_tag(self, prompt_id: int, tag_name: str, tag_type: str):
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

        self.conn.commit()
