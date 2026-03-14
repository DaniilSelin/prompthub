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

"""
Примечание, которое надо когда нибудь удалить - 
Сюда я добавил перегрузку операторов для того, чтобы интерпретатор не создавал вложенные условия
То есть, перегружегнного Condition может хватить для F1 & F2, он создаст условно F3 = (must {F1, F2})
Но для F1&F2&F3 он будет создавать F4 (must {F5 must {F1, F2}, F3}), то есть будет создавать лишние обёртки.

Я не уверен, что сделал это правильно, надо проверить допустимо ли такое сплющивание, не приводит ли оно к ошибкам.
"""
class Filter(Condition):
    def __init__(
        self,
        must: list[Condition] | None = None,
        should: list[Condition] | None = None,
        must_not: list[Condition] | None = None
    ):
        self.must: list[Condition] = must or []
        self.should: list[Condition] = should or []
        self.must_not: list[Condition] = must_not or []

    def __and__(self, other: Condition) -> "Filter":
        if isinstance(other, Filter):
            return Filter(must=self.must + other.must, should=self.should + other.should, must_not=self.must_not + other.must_not)
        return Filter(must=self.must + [other], should=self.should, must_not=self.must_not)

    def __rand__(self, other: Condition) -> "Filter":
        if isinstance(other, Filter):
            return Filter(must=other.must + self.must, should=other.should + self.should, must_not=other.must_not + self.must_not)
        return Filter(must=[other] + self.must, should=self.should, must_not=self.must_not)

    def __or__(self, other: Condition) -> "Filter":
        if isinstance(other, Filter):
            return Filter(must=self.must + other.must, should=self.should + other.should, must_not=self.must_not + other.must_not)
        return Filter(must=self.must, should=self.should + [other], must_not=self.must_not)

    def __ror__(self, other: Condition) -> "Filter":
        if isinstance(other, Filter):
            return Filter(must=other.must + self.must, should=other.should + self.should, must_not=other.must_not + self.must_not)
        return Filter(must=self.must, should=[other] + self.should, must_not=self.must_not)

    def __invert__(self) -> "Filter":
        return Filter(must=self.must, should=self.should, must_not=self.must_not + [self])

    def __repr__(self) -> str:
        parts = []
        if self.must:
            parts.append("AND[" + ", ".join(repr(p) for p in self.must) + "]")
        if self.should:
            parts.append("OR[" + ", ".join(repr(p) for p in self.should) + "]")
        if self.must_not:
            parts.append("NOT[" + ", ".join(repr(p) for p in self.must_not) + "]")
        return "Filter(" + " ".join(parts) + ")"