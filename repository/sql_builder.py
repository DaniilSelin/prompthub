from typing import Any

from search.filters import Filter, FieldEquals, FieldGreater, FieldLike
from search.queries import SearchQuery, UpdateQuery, InsertQuery, DeleteQuery

class SQLBuilder:
    def __init__(self) -> None:
        self.params: list[Any] = []

    def _reset(self) -> None:
        self.params = []

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

        if isinstance(condition, Filter):
            return self.compile_filter(condition)

        raise ValueError("Unknown condition type")

    def compile_group(self, conditions: list, joiner: str) -> str:
        if not conditions:
            return ""
        parts = []
        for cond in conditions:
            sql = self.compile(cond)
            parts.append(f"({sql})")
        return f" {joiner} ".join(parts)

    def compile_filter(self, filter_obj: Filter) -> str:
        if not filter_obj:
            return "1=1"

        parts = []

        if filter_obj.must:
            parts.append(self.compile_group(filter_obj.must, "AND"))

        if filter_obj.should:
            sql = self.compile_group(filter_obj.should, "OR")
            parts.append(f"({sql})")

        if filter_obj.must_not:
            sql = self.compile_group(filter_obj.must_not, "AND")
            parts.append(f"NOT ({sql})")

        return " AND ".join(p for p in parts if p)

    def build_select(self, table: str, query: SearchQuery) -> tuple[str, list[Any]]:
        self._reset()
        where_parts: list[str] = []

        text = getattr(query, "text", None)
        if text:
            where_parts.append("content LIKE ?")
            self.params.append(f"%{text}%")

        if getattr(query, "filters", None):
            where_parts.append(self.compile(query.filters))

        where_sql = " AND ".join(where_parts) if where_parts else "1=1"

        order_by = getattr(query, "_order_by", None)
        limit = getattr(query, "_limit", 20) or 20
        offset = getattr(query, "_offset", 0) or 0

        sql = f"SELECT * FROM {table} WHERE {where_sql}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        sql += " LIMIT ? OFFSET ?"

        self.params.append(limit)
        self.params.append(offset)

        return sql, self.params.copy()

    def build_insert(self, table: str, query: InsertQuery) -> tuple[str, list[Any]]:
        self._reset()
        values = query.values
        if not values:
            raise ValueError("InsertQuery.values is empty")

        fields = ", ".join(values.keys())
        placeholders = ", ".join(["?"] * len(values))
        sql = f"INSERT INTO {table} ({fields}) VALUES ({placeholders})"
        return sql, list(values.values())

    def build_update(self, table: str, query: UpdateQuery) -> tuple[str, list[Any]]:
        self._reset()
        if not getattr(query, "values", None):
            raise ValueError("UpdateQuery.values is empty")

        set_parts: list[str] = []
        for field, value in query.values.items():
            set_parts.append(f"{field} = ?")
            self.params.append(value)

        where_sql = self.compile(query.filters) if getattr(query, "filters", None) else "1=1"

        sql = f"UPDATE {table} SET {', '.join(set_parts)} WHERE {where_sql}"
        return sql, self.params.copy()

    def build_delete(self, table: str, query: DeleteQuery) -> tuple[str, list[Any]]:
        self._reset()
        where_sql = self.compile(query.filters) if getattr(query, "filters", None) else "1=1"
        sql = f"DELETE FROM {table} WHERE {where_sql}"
        return sql, self.params.copy()