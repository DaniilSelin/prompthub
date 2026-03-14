from search.filters import Filter

class BaseQuery:
    def __init__(self, table: str):
        self.table = table
        self.filters: Filter | None = None
        self._order_by: str | None = None
        self._limit: int | None = None
        self._offset: int | None = None

    def filter(self, filter_obj: Filter):
        self.filters = filter_obj
        return self

    def order_by(self, field: str):
        self._order_by = field
        return self

    def limit(self, n: int):
        self._limit = n
        return self

    def offset(self, n: int):
        self._offset = n
        return self

class SearchQuery(BaseQuery):
    def __init__(self, table: str, text: str | None = None):
        super().__init__(table)
        self.text = text

class UpdateQuery(BaseQuery):
    def __init__(self, table: str, values: dict):
        super().__init__(table)
        self.values = values

class DeleteQuery(BaseQuery):
    def __init__(self, table: str):
        super().__init__(table)

class InsertQuery(BaseQuery):
    def __init__(self, table: str, values: dict):
        super().__init__(table)
        self.values = values