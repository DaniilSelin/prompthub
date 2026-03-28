from abc import ABC
from typing import Any

class Condition(ABC):
    def __and__(self, other: "Condition") -> "Filter":
        return Filter(must=[self, other])

    def __rand__(self, other: "Condition") -> "Filter":
        return Filter(must=[other, self])

    def __or__(self, other: "Condition") -> "Filter":
        return Filter(should=[self, other])

    def __ror__(self, other: "Condition") -> "Filter":
        return Filter(should=[other, self])

    def __invert__(self) -> "Filter":
        return Filter(must_not=[self])

    def __repr__(self) -> str:
        return self.__class__.__name__

class FieldEquals(Condition):
    def __init__(self, field: str, value: Any):
        self.field = field
        self.value = value

    def __repr__(self) -> str:
        return f"Eq({self.field!s}={self.value!r})"


class FieldGreater(Condition):
    def __init__(self, field: str, value: Any):
        self.field = field
        self.value = value

    def __repr__(self) -> str:
        return f"Gt({self.field!s}>{self.value!r})"


class FieldLike(Condition):
    def __init__(self, field: str, pattern: str):
        self.field = field
        self.pattern = pattern

    def __repr__(self) -> str:
        return f"Like({self.field!s} LIKE {self.pattern!r})"

class FieldIn(Condition):
    def __init__(self, field: str, values: list):
        self.field = field
        self.values = list(values)

    def __repr__(self):
        return f"In({self.field} IN {self.values})"

class FieldBetween(Condition):
    def __init__(self, field: str, low, high):
        self.field = field
        self.low = low
        self.high = high

    def __repr__(self):
        return f"Between({self.field} BETWEEN {self.low} AND {self.high})"

class FieldIsNull(Condition):
    def __init__(self, field: str):
        self.field = field

    def __repr__(self):
        return f"IsNull({self.field} IS NULL)"

class FieldNotNull(Condition):
    def __init__(self, field: str):
        self.field = field

    def __repr__(self):
        return f"NotNull({self.field} IS NOT NULL)"

class RawCondition(Condition):
    def __init__(self, sql: str, params: list | None = None):
        self.sql = sql
        self.params = params or []

    def __repr__(self):
        return f"Raw({self.sql})"


class TagFilter(RawCondition):
    """Фильтр промптов по тегу. Используется в search_by_tags()."""
    def __init__(self, name: str, tag_type: str | None = None):
        if tag_type:
            sql = (
                "id IN ("
                "SELECT pt.prompt_id FROM prompt_tags pt "
                "JOIN tags t ON t.id = pt.tag_id "
                "WHERE t.name = ? AND t.type = ?"
                ")"
            )
            params = [name, tag_type]
        else:
            sql = (
                "id IN ("
                "SELECT pt.prompt_id FROM prompt_tags pt "
                "JOIN tags t ON t.id = pt.tag_id "
                "WHERE t.name = ?"
                ")"
            )
            params = [name]
        super().__init__(sql, params)

    def __repr__(self):
        return f"TagFilter(sql={self.sql!r})"

"""
Сплющивание всё таки приводило к серьёзным ошибкам. Вернул логику вложенных фильтров.
"""
class Filter(Condition):
    def __init__(self, must=None, should=None, must_not=None):
        self.must = must or []
        self.should = should or []
        self.must_not = must_not or []

    def __and__(self, other):
        if isinstance(other, Filter):
            return Filter(must=[self, other])
        return Filter(must=[self, other])

    def __or__(self, other):
        if isinstance(other, Filter):
            return Filter(should=[self, other])
        return Filter(should=[self, other])

    def __invert__(self):
        return Filter(must_not=[self])

    def __repr__(self):
        parts = []
        if self.must: parts.append("AND[" + ", ".join(repr(p) for p in self.must) + "]")
        if self.should: parts.append("OR[" + ", ".join(repr(p) for p in self.should) + "]")
        if self.must_not: parts.append("NOT[" + ", ".join(repr(p) for p in self.must_not) + "]")
        return "Filter(" + " ".join(parts) + ")"