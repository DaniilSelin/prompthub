from typing import Any

from prompthub.repository.queries import (
    DeleteQuery,
    InsertQuery,
    SearchQuery,
    UpdateQuery,
)


class QueryFactory:
    table: str = "table"

    def make_search_query(self, text: str = "") -> SearchQuery:
        return SearchQuery(self.table, text)

    def make_insert_query(
        self, values: dict[str, Any] | list[dict[str, Any]]
    ) -> InsertQuery:
        return InsertQuery(self.table, values)

    def make_update_query(self, values: dict[str, Any]) -> UpdateQuery:
        return UpdateQuery(self.table, values)

    def make_delete_query(self) -> DeleteQuery:
        return DeleteQuery(self.table)
