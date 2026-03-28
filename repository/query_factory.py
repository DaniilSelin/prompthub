from repository.queries import SearchQuery, InsertQuery, UpdateQuery, DeleteQuery


class QueryFactory:
    table: str = "table"

    def make_search_query(self, text: str = ""):
        return SearchQuery(self.table, text)

    def make_insert_query(self, values: dict):
        return InsertQuery(self.table, values)

    def make_update_query(self, values: dict):
        return UpdateQuery(self.table, values)

    def make_delete_query(self):
        return DeleteQuery(self.table)
