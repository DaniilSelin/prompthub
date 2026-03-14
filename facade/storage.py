from pathlib import Path
from typing import Any

from search.queries import SearchQuery, UpdateQuery, InsertQuery, DeleteQuery
from repository.sql_builder import SQLBuilder

class Storage:
    def __init__(self, path: str):
        self.storage_path: Path = Path(path)
        self._diff_engine = None

    def execute(self, sql: str, params: list[Any]) -> list[dict[str, Any]]:
        print(sql)
        print(params)
        return []

    """
    Пока не решил как будут поставляться имена таблиц и тп.
    """
    def search(self, table: str, text: str = ""):
        return SearchQueryFluent(self, table, text)

    def insert(self, table: str, values: dict):
        return InsertQueryFluent(self, table, values)

    def update(self, table: str, values: dict):
        return UpdateQueryFluent(self, table, values)

    def delete(self, table: str):
        return DeleteQueryFluent(self, table)

class SearchQueryFluent(SearchQuery):
    def __init__(self, storage: Storage, table: str, text: str = ""):
        super().__init__(table, text)
        self._storage = storage

    def execute(self):
        builder = SQLBuilder()
        sql, params = builder.build_select(self.table, self)
        return self._storage.execute(sql, params)


class UpdateQueryFluent(UpdateQuery):
    def __init__(self, storage: Storage, table: str, values: dict):
        super().__init__(table, values)
        self._storage = storage

    def execute(self):
        builder = SQLBuilder()
        sql, params = builder.build_update(self.table, self)
        return self._storage.execute(sql, params)


class InsertQueryFluent(InsertQuery):
    def __init__(self, storage: Storage, table: str, values: dict):
        super().__init__(table, values)
        self._storage = storage

    def execute(self):
        builder = SQLBuilder()
        sql, params = builder.build_insert(self.table, self)
        return self._storage.execute(sql, params)


class DeleteQueryFluent(DeleteQuery):
    def __init__(self, storage: Storage, table: str):
        super().__init__(table)
        self._storage = storage

    def execute(self):
        builder = SQLBuilder()
        sql, params = builder.build_delete(self.table, self)
        return self._storage.execute(sql, params)