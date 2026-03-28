import pytest

from repository.queries import SearchQuery
from search.filters import (
    FieldBetween,
    FieldEquals,
    FieldGreater,
    FieldIn,
    FieldIsNull,
    FieldLike,
    FieldNotNull,
    Filter,
    RawCondition,
)


@pytest.mark.unit
def test_condition_and_builds_filter_with_must_conditions():
    left = FieldEquals("prompt_id", 10)
    right = FieldGreater("seq", 1)

    combined = left & right

    assert isinstance(combined, Filter)
    assert combined.must == [left, right]
    assert combined.should == []
    assert combined.must_not == []


@pytest.mark.unit
def test_condition_or_builds_filter_with_should_conditions():
    left = FieldEquals("name", "v1")
    right = FieldEquals("name", "v2")

    combined = left | right

    assert isinstance(combined, Filter)
    assert combined.must == []
    assert combined.should == [left, right]
    assert combined.must_not == []


@pytest.mark.unit
def test_condition_invert_builds_filter_with_must_not_condition():
    condition = FieldEquals("name", "draft")

    inverted = ~condition

    assert isinstance(inverted, Filter)
    assert inverted.must == []
    assert inverted.should == []
    assert inverted.must_not == [condition]


@pytest.mark.unit
def test_compile_filter_must_should_must_not_with_stable_param_order():
    query = SearchQuery("prompt_versions")
    condition = Filter(
        must=[FieldEquals("prompt_id", 7)],
        should=[FieldEquals("author", "qa"), FieldEquals("author", "dev")],
        must_not=[FieldGreater("seq", 100)],
    )

    query.filter(condition)
    sql, params = query.build()

    assert (
        sql
        == "SELECT * FROM prompt_versions WHERE (prompt_id = ?) AND ((author = ?) OR (author = ?)) AND NOT ((seq > ?))"
    )
    assert params == [7, "qa", "dev", 100]


@pytest.mark.unit
def test_field_like_compiles_to_like_predicate():
    query = SearchQuery("prompt_versions").filter(FieldLike("name", "v%"))

    sql, params = query.build()

    assert sql == "SELECT * FROM prompt_versions WHERE name LIKE ?"
    assert params == ["v%"]


@pytest.mark.unit
def test_field_in_compiles_to_in_predicate_with_all_placeholders():
    query = SearchQuery("prompt_versions").filter(FieldIn("seq", [1, 2, 3]))

    sql, params = query.build()

    assert sql == "SELECT * FROM prompt_versions WHERE seq IN (?, ?, ?)"
    assert params == [1, 2, 3]


@pytest.mark.unit
def test_field_between_compiles_to_between_predicate():
    query = SearchQuery("prompt_versions").filter(FieldBetween("seq", 2, 5))

    sql, params = query.build()

    assert sql == "SELECT * FROM prompt_versions WHERE seq BETWEEN ? AND ?"
    assert params == [2, 5]


@pytest.mark.unit
def test_field_is_null_and_not_null_compile_without_params():
    is_null_query = SearchQuery("prompts").filter(FieldIsNull("author"))
    not_null_query = SearchQuery("prompts").filter(FieldNotNull("author"))

    is_null_sql, is_null_params = is_null_query.build()
    not_null_sql, not_null_params = not_null_query.build()

    assert is_null_sql == "SELECT * FROM prompts WHERE author IS NULL"
    assert is_null_params == []

    assert not_null_sql == "SELECT * FROM prompts WHERE author IS NOT NULL"
    assert not_null_params == []


@pytest.mark.unit
def test_raw_condition_compiles_verbatim_and_appends_params():
    query = SearchQuery("prompts").filter(
        RawCondition("LENGTH(name) > ? AND name <> ?", [3, "tmp"])
    )

    sql, params = query.build()

    assert sql == "SELECT * FROM prompts WHERE (LENGTH(name) > ? AND name <> ?)"
    assert params == [3, "tmp"]
