from pathlib import Path
import sqlite3

from core.domain.prompt_group import PromptGroup
from repository.queries import BaseQuery, SearchQuery
from repository.query_factory import QueryFactory
from repository import Fields

class Storage(QueryFactory):
    table: str = Fields._PROMPTS_TABLE

    def __init__(self, path: str):
        self.storage_path: Path = Path(path)
        self._conn = sqlite3.connect(self.storage_path)
        self._conn.row_factory = sqlite3.Row
        self._diff_engine = None

    def execute(self, query: BaseQuery):
        sql, params = query.build()

        cur = self._conn.cursor()
        cur.execute(sql, params)

        if isinstance(query, SearchQuery):
            rows = cur.fetchall()
            return [dict(r) for r in rows]

        self._conn.commit()
        return cur.rowcount
    
    def make_group_prompt(self, query: BaseQuery) -> PromptGroup:
        return PromptGroup( self._conn, query)