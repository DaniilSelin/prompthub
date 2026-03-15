from pathlib import Path

from repository.queries import BaseQuery
from repository.query_factory import QueryFactory

class Storage(QueryFactory):
    table: str = "prompts"

    def __init__(self, path: str):
        self.storage_path: Path = Path(path)
        self._diff_engine = None

    def execute(self, query: BaseQuery):
        sql, params = query.build()

        print(sql)
        print(params)
        return []
