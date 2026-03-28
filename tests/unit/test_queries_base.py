import pytest

from prompthub.repository.queries import DeleteQuery, InsertQuery, SearchQuery, UpdateQuery
from prompthub.search.filters import FieldEquals, FieldGreater, FieldIn


@pytest.mark.unit
def test_search_query_build_with_text_filter_sort_limit_offset():
    query = (
        SearchQuery("prompt_versions", text="hello")
        .filter(FieldEquals("prompt_id", 42))
        .order_by("seq DESC")
        .limit(5)
        .offset(10)
    )

    sql, params = query.build()

    assert (
        sql
        == "SELECT * FROM prompt_versions WHERE content LIKE ? AND prompt_id = ? ORDER BY seq DESC LIMIT ? OFFSET ?"
    )
    assert params == ["%hello%", 42, 5, 10]


@pytest.mark.unit
def test_search_query_build_without_text_and_filters_uses_true_predicate():
    query = SearchQuery("prompts")

    sql, params = query.build()

    assert sql == "SELECT * FROM prompts WHERE 1=1"
    assert params == []


@pytest.mark.unit
def test_search_query_build_resets_params_on_rebuild():
    query = SearchQuery("prompts", text="x").limit(1)

    _, first_params = query.build()
    _, second_params = query.build()

    assert first_params == ["%x%", 1]
    assert second_params == ["%x%", 1]


@pytest.mark.unit
def test_search_query_field_in_with_empty_values_compiles_to_false_predicate():
    query = SearchQuery("prompts").filter(FieldIn("id", []))

    sql, params = query.build()

    assert sql == "SELECT * FROM prompts WHERE 0=1"
    assert params == []


@pytest.mark.unit
def test_update_query_build_with_values_and_filter():
    query = UpdateQuery("prompts", {"name": "new_name", "author": "qa"}).filter(
        FieldEquals("id", 7)
    )

    sql, params = query.build()

    assert sql == "UPDATE prompts SET name = ?, author = ? WHERE id = ?"
    assert params == ["new_name", "qa", 7]


@pytest.mark.unit
def test_update_query_without_values_raises_value_error():
    with pytest.raises(ValueError, match="UpdateQuery.values is empty"):
        UpdateQuery("prompts", {}).build()


@pytest.mark.unit
def test_delete_query_build_with_filter():
    query = DeleteQuery("prompts").filter(FieldGreater("id", 100))

    sql, params = query.build()

    assert sql == "DELETE FROM prompts WHERE id > ?"
    assert params == [100]


@pytest.mark.unit
def test_delete_query_without_filter_targets_all_rows_explicitly():
    query = DeleteQuery("prompts")

    sql, params = query.build()

    assert sql == "DELETE FROM prompts WHERE 1=1"
    assert params == []


@pytest.mark.unit
def test_insert_query_single_row_builds_expected_sql_and_params():
    query = InsertQuery("tags", {"name": "tag_a", "type": "prompt"})

    sql, params = query.build()

    assert sql == "INSERT INTO tags (name, type) VALUES (?, ?)"
    assert params == ["tag_a", "prompt"]


@pytest.mark.unit
def test_insert_query_multiple_rows_builds_bulk_insert_sql_and_params():
    query = InsertQuery(
        "tags",
        [
            {"name": "tag_a", "type": "prompt"},
            {"name": "tag_b", "type": "model"},
        ],
    )

    sql, params = query.build()

    assert sql == "INSERT INTO tags (name, type) VALUES (?, ?), (?, ?)"
    assert params == ["tag_a", "prompt", "tag_b", "model"]


@pytest.mark.unit
def test_insert_query_inconsistent_columns_raises_value_error():
    with pytest.raises(ValueError, match="All rows must have the same columns"):
        InsertQuery(
            "tags",
            [
                {"name": "tag_a", "type": "prompt"},
                {"name": "tag_b", "kind": "model"},
            ],
        )


@pytest.mark.unit
def test_insert_query_empty_rows_raises_value_error():
    with pytest.raises(ValueError, match="InsertQuery.rows is empty"):
        InsertQuery("tags", [])
