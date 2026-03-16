from search.filters import Filter, FieldEquals, FieldGreater, FieldLike
from repository.queries import SearchQuery

A = FieldEquals("a", 1)
B = FieldEquals("b", 2)
C = FieldEquals("c", 3)
D = FieldEquals("d", 4)
E = FieldEquals("e", 5)
F = FieldEquals("f", 6)
G = FieldEquals("g", 7)

expr = ((A & B) | (C & D)) & ~(E | F) | G

query = SearchQuery("table")
query.filter(expr)
sql, params = query.compile(query.filters), query.params

print("COMPILED SQL:")
print(sql)
print("PARAMS:", params)