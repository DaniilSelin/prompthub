from prompthub.repository.queries import SearchQuery
from prompthub.search.filters import FieldEquals


def main() -> None:
	a = FieldEquals("a", 1)
	b = FieldEquals("b", 2)
	c = FieldEquals("c", 3)
	d = FieldEquals("d", 4)
	e = FieldEquals("e", 5)
	f = FieldEquals("f", 6)
	g = FieldEquals("g", 7)

	expr = ((a & b) | (c & d)) & ~(e | f) | g

	query = SearchQuery("table")
	query.filter(expr)
	sql, params = query.compile(query.filters), query.params

	print("COMPILED SQL:")
	print(sql)
	print("PARAMS:", params)


if __name__ == "__main__":
	main()