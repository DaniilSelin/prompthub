import sqlite3
from typing import List
from repository.queries import BaseQuery, SearchQuery, InsertQuery, DeleteQuery, UpdateQuery
from repository import Fields, TAG_PROMPT_TYPE
from repository.query_factory import QueryFactory
from search.filters import FieldEquals, FieldIn, RawCondition, Filter
from .tag import PromptTag

class PromptGroup(QueryFactory):
    table: str = Fields._PROMPT_VERSIONS_TABLE

    def __init__(self, conn: sqlite3.Connection, prompt_query: BaseQuery | None = None):
        self._conn = conn
        self.prompt_query = prompt_query or SearchQuery(Fields._PROMPTS_TABLE)

    def _compile_prompt_query(self):
        sql, params = self.prompt_query.build()

        return f"SELECT {Fields._PROMPT_ID} FROM ({sql})", params

    def _execute(self, query: BaseQuery):
        sql, params = query.build()
        cur = self._conn.cursor()
        cur.execute(sql, params)

        if isinstance(query, SearchQuery):
            rows = cur.fetchall()
            return [dict(r) for r in rows]

        self._conn.commit()
        return cur.rowcount
    
    def _add_group_condition(self, query: BaseQuery) -> BaseQuery:

        sub_sql, sub_params = self._compile_prompt_query()

        cond = RawCondition(
            f"{self.table}.{Fields.PROMPT_VERSIONS_PROMPT_ID} IN ({sub_sql})",
            sub_params,
        )

        if query.filters:
            query.filter(query.filters & cond)
        else:
            query.filter(cond)

        return query

    def make_search_query(self, text: str = "") -> SearchQuery:
        q = SearchQuery(self.table, text)
        return self._add_group_condition(q)
    
    # надо переделать ребаоту с insert в целом
    # def make_insert_query(self, values: dict) -> InsertQuery:
    #     return InsertQuery(self.table, values)

    def make_update_query(self, values: dict) -> UpdateQuery:
        q = UpdateQuery(self.table, values)
        return self._add_group_condition(q)

    def make_delete_query(self) -> DeleteQuery:
        q = DeleteQuery(self.table)
        return self._add_group_condition(q)

    def with_tag(self, tag_name: str, tag_type: str = TAG_PROMPT_TYPE):

        cond = RawCondition(
            f"""
            EXISTS (
                SELECT 1
                FROM prompt_tags pt
                JOIN {Fields._TAG_TABLE} t ON t.id = pt.tag_id
                WHERE pt.prompt_id = {Fields._PROMPTS_TABLE}.id
                AND t.{Fields.TAG_NAME} = ?
                AND t.{Fields.TAG_TYPE} = ?
            )
            """,
            [tag_name, tag_type],
        )

        new_query = self.prompt_query.clone()

        if new_query.filters:
            new_query.filters = new_query.filters & cond
        else:
            new_query.filters = cond

        return PromptGroup(self._conn, new_query)
    
    def without_tag(self, tag_name: str, tag_type: str = TAG_PROMPT_TYPE) -> "PromptGroup":

        cond = RawCondition(
            f"""
            NOT EXISTS (
                SELECT 1
                FROM prompt_tags pt
                JOIN {Fields._TAG_TABLE} t ON t.id = pt.tag_id
                WHERE pt.prompt_id = {Fields._PROMPTS_TABLE}.id
                AND t.{Fields.TAG_NAME} = ?
                AND t.{Fields.TAG_TYPE} = ?
            )
            """,
            [tag_name, tag_type],
        )

        new_query = SearchQuery(Fields._PROMPTS_TABLE)
        new_query.filters = cond if not self.prompt_query.filters else self.prompt_query.filters & cond

        return PromptGroup(self._conn, new_query)

    def list_versions(self, version_filter: Filter | None = None):

        q = SearchQuery(self.table)

        if version_filter:
            q.filter(version_filter)

        q = self._add_group_condition(q)

        return self._execute(q)

    def count(self) -> int:

        sub_sql, params = self._compile_prompt_query()

        sql = f"""
        SELECT COUNT(*)
        FROM {Fields._PROMPTS_TABLE}
        WHERE {Fields._PROMPT_ID} IN ({sub_sql})
        """

        cur = self._conn.cursor()
        cur.execute(sql, params)

        return cur.fetchone()[0]