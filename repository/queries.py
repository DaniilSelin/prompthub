from typing import Any, Union
from abc import abstractmethod

from search.filters import (
    Filter,
    FieldEquals,
    FieldGreater,
    FieldLike,
    FieldIn,
    RawCondition,
    FieldBetween,
    FieldNotNull,
    FieldIsNull,
)


class BaseQuery:
    def __init__(self, table: str):
        self.table = table
        self.filters: Filter | None = None
        self._order_by: str | None = None
        self._limit: int | None = None
        self._offset: int | None = None
        self.params: list[Any] = []

    def clone(self):
        q = self.__class__(self.table)
        q.filters = self.filters
        q._order_by = self._order_by
        q._limit = self._limit
        q._offset = self._offset
        return q

    def filter(self, filter_obj: Filter):
        if self.filters is None:
            self.filters = filter_obj
        else:
            self.filters = self.filters & filter_obj
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

    def compile(self, condition) -> str:
        if condition is None:
            return "1=1"

        if isinstance(condition, FieldEquals):
            self.params.append(condition.value)
            return f"{condition.field} = ?"

        if isinstance(condition, FieldGreater):
            self.params.append(condition.value)
            return f"{condition.field} > ?"

        if isinstance(condition, FieldLike):
            self.params.append(condition.pattern)
            return f"{condition.field} LIKE ?"

        if isinstance(condition, FieldIn):
            if not condition.values:
                return "0=1"
            placeholders = ", ".join("?" for _ in condition.values)
            self.params.extend(condition.values)
            return f"{condition.field} IN ({placeholders})"

        if isinstance(condition, FieldBetween):
            self.params.extend([condition.low, condition.high])
            return f"{condition.field} BETWEEN ? AND ?"

        if isinstance(condition, FieldIsNull):
            return f"{condition.field} IS NULL"

        if isinstance(condition, FieldNotNull):
            return f"{condition.field} IS NOT NULL"

        if isinstance(condition, RawCondition):
            self.params.extend(condition.params)
            return f"({condition.sql})"

        if isinstance(condition, Filter):
            return self.compile_filter(condition)

        raise ValueError("Unknown condition type: %r" % (type(condition),))

    def compile_group(self, conditions: list, joiner: str) -> str:
        if not conditions:
            return ""

        parts = []
        for cond in conditions:
            sql = self.compile(cond)
            parts.append(f"({sql})")
        return f" {joiner} ".join(parts)

    def compile_filter(self, filter_obj: Filter) -> str:
        if not filter_obj or (
            not filter_obj.must and not filter_obj.should and not filter_obj.must_not
        ):
            return "1=1"

        parts = []

        if filter_obj.must:
            parts.append(self.compile_group(filter_obj.must, "AND"))

        if filter_obj.should:
            parts.append("(" + self.compile_group(filter_obj.should, "OR") + ")")

        if filter_obj.must_not:
            parts.append("NOT (" + self.compile_group(filter_obj.must_not, "AND") + ")")

        return " AND ".join(p for p in parts if p)

    @abstractmethod
    def build(self):
        pass


class SearchQuery(BaseQuery):
    def __init__(self, table: str, text: str | None = None):
        super().__init__(table)
        self.text = text

    def build(self) -> tuple[str, list[Any]]:
        self.params.clear()
        where_parts: list[str] = []

        text = self.text
        if text:
            where_parts.append("content LIKE ?")
            self.params.append(f"%{text}%")

        if self.filters:
            where_parts.append(self.compile(self.filters))

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"

        sql = f"SELECT * FROM {self.table} WHERE {where_sql}"
        if self._order_by:
            sql += f" ORDER BY {self._order_by}"

        if self._limit != None:
            sql += " LIMIT ?"
            self.params.append(self._limit)
        if self._offset != None:
            sql += " OFFSET ?"
            self.params.append(self._offset)

        return sql, self.params.copy()


class UpdateQuery(BaseQuery):
    def __init__(self, table: str, values: dict):
        super().__init__(table)
        self.values = values

    def build(self):
        self.params.clear()
        if not self.values:
            raise ValueError("UpdateQuery.values is empty")

        set_parts = []

        for field, value in self.values.items():
            set_parts.append(f"{field} = ?")
            self.params.append(value)

        where_sql = self.compile(self.filters) if self.filters else "1=1"

        sql = f"UPDATE {self.table} SET {', '.join(set_parts)} WHERE {where_sql}"

        return sql, self.params.copy()


class DeleteQuery(BaseQuery):
    def __init__(self, table: str):
        super().__init__(table)

    def build(self):
        self.params.clear()
        where_sql = self.compile(self.filters) if self.filters else "1=1"

        sql = f"DELETE FROM {self.table} WHERE {where_sql}"

        return sql, self.params.copy()


class InsertQuery(BaseQuery):
    def __init__(self, table: str, rows: Union[dict[str, Any], list[dict[str, Any]]]):
        super().__init__(table)
        if isinstance(rows, dict):
            self.rows = [rows]
        else:
            self.rows = rows

        if not self.rows:
            raise ValueError("InsertQuery.rows is empty")

        keys_set = set(self.rows[0].keys())
        for r in self.rows:
            if set(r.keys()) != keys_set:
                raise ValueError("All rows must have the same columns")
        self.columns = list(self.rows[0].keys())

    def build(self):
        if not self.rows:
            raise ValueError("InsertQuery.rows is empty")

        placeholders = "(" + ", ".join("?" for _ in self.columns) + ")"
        values_sql = ", ".join([placeholders] * len(self.rows))

        sql = (
            f"INSERT INTO {self.table} ({', '.join(self.columns)}) VALUES {values_sql}"
        )

        params = []
        for row in self.rows:
            params.extend([row[col] for col in self.columns])

        return sql, params
