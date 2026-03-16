import sqlite3
from typing import List
from repository.queries import BaseQuery, SearchQuery, InsertQuery, DeleteQuery, UpdateQuery
from repository import _Fields, TAG_PROMPT_TYPE
from repository.query_factory import QueryFactory
from search.filters import FieldEquals, FieldIn, RawCondition, Filter
from .tag import PromptTag

"""
попытка нейронки сгенерить хоть что то, неудачно. Потом всё перепишу. Но идея с PromptGroup оказалась очень даже хорошей.
"""
class PromptGroup(QueryFactory):
    table: str = _Fields._PROMPT_VERSIONS_TABLE

    def __init__(self, base_query: BaseQuery, conn: sqlite3.Connection):
        self.base_query = base_query
        self._conn = conn

    def _execute(self, query: BaseQuery):
        sql, params = query.build()
        cur = self._conn.cursor()
        cur.execute(sql, params)
        if isinstance(query, SearchQuery):
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        self._conn.commit()
        return cur.rowcount

    def _fetch_prompt_ids(self) -> list[int]:
        cur = self._conn.cursor()

        if self.base_query.filters is None:
            cur.execute(f"SELECT id FROM {_Fields._PROMPTS_TABLE}")
            return [r["id"] for r in cur.fetchall()]

        query = SearchQuery(_Fields._PROMPT_VERSIONS_TABLE)
        query.filters = self.base_query.filters
        where_sql, params = query.compile(self.base_query.filters), query.params

        sql = f"""
        SELECT DISTINCT p.id
        FROM {_Fields._PROMPTS_TABLE} p
        JOIN {_Fields._PROMPT_VERSIONS_TABLE} pv
        ON pv.{_Fields.PROMPT_VERSIONS_PROMPT_ID} = p.id
        WHERE {where_sql}
        """

        cur.execute(sql, params)
        return [r["id"] for r in cur.fetchall()]
    
    def _add_group_condition(self, query: BaseQuery) -> BaseQuery:
        prompt_ids = self._fetch_prompt_ids()
        if not prompt_ids:
            return query.filter(RawCondition("0=1", []))

        cond = FieldIn(f"{self.table}.prompt_id", prompt_ids)

        if query.filters:
            new_filter = query.filters & cond
            query.filter(new_filter)
        else:
            query.filter(cond)

        return query

    def make_search_query(self, text: str = "") -> SearchQuery:
        q = SearchQuery(self.table, text)
        return self._add_group_condition(q)
    
    def make_insert_query(self, values: dict):
        raise NotImplementedError

    def make_update_query(self, values: dict):
        raise NotImplementedError

    def make_delete_query(self):
        raise NotImplementedError

    def with_tag(self, tag_name: str, tag_type: str = TAG_PROMPT_TYPE) -> 'PromptGroup':
        ids = self._fetch_prompt_ids()
        if not ids:
            empty_q = SearchQuery(self.table)
            empty_q.filter(RawCondition("0=1", []))
            return PromptGroup(empty_q, self._conn)

        sql = f"""
        SELECT pt.prompt_id
        FROM prompt_tags pt
        JOIN tags t ON t.id = pt.tag_id
        WHERE t.name = ? AND t.type = ? AND pt.prompt_id IN ({','.join(['?']*len(ids))})
        """
        params = [tag_name, tag_type] + ids
        cur = self._conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        found_ids = [r["prompt_id"] for r in rows]

        if not found_ids:
            empty_q = SearchQuery(self.table)
            empty_q.filter(RawCondition("0=1", []))
            return PromptGroup(empty_q, self._conn)

        new_base = SearchQuery(self.table)
        new_base.filter(FieldIn(f"{self.table}.{_Fields.PROMPT_VERSIONS_PROMPT_ID}", found_ids))
        return PromptGroup(new_base, self._conn)
    
    def without_tag(self, tag_name: str, tag_type: str = TAG_PROMPT_TYPE) -> 'PromptGroup':
        ids = self._fetch_prompt_ids()
        if not ids:
            empty_q = SearchQuery(self.table)
            empty_q.filter(RawCondition("0=1", []))
            return PromptGroup(empty_q, self._conn)

        sql = f"""
        SELECT pt.prompt_id
        FROM prompt_tags pt
        JOIN tags t ON t.id = pt.tag_id
        WHERE t.name = ? AND t.type = ? AND pt.prompt_id IN ({','.join(['?']*len(ids))})
        """
        params = [tag_name, tag_type] + ids
        cur = self._conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        tagged_ids = {r["prompt_id"] for r in rows}

        remain_ids = [i for i in ids if i not in tagged_ids]
        if not remain_ids:
            empty_q = SearchQuery(self.table)
            empty_q.filter(RawCondition("0=1", []))
            return PromptGroup(empty_q, self._conn)

        new_base = SearchQuery(self.table)
        new_base.filter(FieldIn(f"{self.table}.{_Fields.PROMPT_VERSIONS_PROMPT_ID}", remain_ids))
        return PromptGroup(new_base, self._conn)

    def list_versions(self, version_filter: BaseQuery | Filter) -> List[dict]:
        prompt_ids = self._fetch_prompt_ids()
        if not prompt_ids:
            return []

        q = SearchQuery(_Fields._PROMPT_VERSIONS_TABLE)
        if isinstance(version_filter, Filter):
            q.filter(FieldIn(_Fields.PROMPT_VERSIONS_PROMPT_ID, prompt_ids) & version_filter)
            return self._execute(q)

        if isinstance(version_filter, BaseQuery):
            q.filter(FieldIn(_Fields.PROMPT_VERSIONS_PROMPT_ID, prompt_ids))
            return self._execute(q)

        q.filter(FieldIn(_Fields.PROMPT_VERSIONS_PROMPT_ID, prompt_ids))
        return self._execute(q)

    def count(self) -> int:
        ids = self._fetch_prompt_ids()
        return len(ids)