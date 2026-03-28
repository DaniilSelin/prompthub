from typing import TypeVar

from repository.queries import BaseQuery, SearchQuery, DeleteQuery, UpdateQuery
from repository import Fields, TAG_PROMPT_TYPE
from search.filters import RawCondition, Filter

TQuery = TypeVar("TQuery", bound=BaseQuery)


class PromptGroup:
    table: str = Fields._PROMPT_VERSIONS_TABLE

    def __init__(self, repo, prompt_query: BaseQuery | None = None):
        self.repo = repo
        self.prompt_query = prompt_query or SearchQuery(Fields._PROMPTS_TABLE)

    def _compile_prompt_query(self) -> tuple[str, list[object]]:
        sql, params = self.prompt_query.build()
        return f"SELECT {Fields._PROMPT_ID} FROM ({sql}) AS sub", params

    def _add_group_condition(self, query: TQuery) -> TQuery:
        sub_sql, sub_params = self._compile_prompt_query()

        cond = RawCondition(
            f"{self.table}.{Fields.PROMPT_VERSIONS_PROMPT_ID} IN ({sub_sql})",
            sub_params,
        )

        query.filters = query.filters & cond if query.filters else cond
        return query

    def filter_prompts(self, filter_obj: Filter):
        new_query = self.prompt_query.clone()
        new_query.filter(filter_obj)
        return PromptGroup(self.repo, new_query)

    def search_versions(self, text: str = "") -> SearchQuery:
        q = SearchQuery(self.table, text)
        return self._add_group_condition(q)

    def update_versions(self, values: dict) -> UpdateQuery:
        q = UpdateQuery(self.table, values)
        return self._add_group_condition(q)

    def delete_versions(self) -> DeleteQuery:
        q = DeleteQuery(self.table)
        return self._add_group_condition(q)

    def with_tag(self, tag_name: str, tag_type: str = TAG_PROMPT_TYPE):
        cond = RawCondition(
            f"""
            EXISTS (
                SELECT 1
                FROM prompt_tags pt
                JOIN {Fields._TAG_TABLE} t ON t.id = pt.tag_id
                WHERE pt.prompt_id = {Fields._PROMPTS_TABLE}.id
                AND t.{Fields.TAG_NAME} = ?
                AND t.{Fields.TAG_TYPE} = ?
            )
            """,
            [tag_name, tag_type],
        )

        new_query = self.prompt_query.clone()
        new_query.filters = new_query.filters & cond if new_query.filters else cond

        return PromptGroup(self.repo, new_query)

    def without_tag(self, tag_name: str, tag_type: str = TAG_PROMPT_TYPE):
        cond = RawCondition(
            f"""
            NOT EXISTS (
                SELECT 1
                FROM prompt_tags pt
                JOIN {Fields._TAG_TABLE} t ON t.id = pt.tag_id
                WHERE pt.prompt_id = {Fields._PROMPTS_TABLE}.id
                AND t.{Fields.TAG_NAME} = ?
                AND t.{Fields.TAG_TYPE} = ?
            )
            """,
            [tag_name, tag_type],
        )

        new_query = self.prompt_query.clone()
        new_query.filters = new_query.filters & cond if new_query.filters else cond

        return PromptGroup(self.repo, new_query)

    def list_versions(self, version_filter: Filter | None = None):
        q = SearchQuery(self.table)

        if version_filter:
            q.filter(version_filter)

        q = self._add_group_condition(q)
        return self.repo.execute(q)

    def execute(self, query: BaseQuery):
        return self.repo.execute(self._add_group_condition(query))

    def count(self) -> int:
        q = SearchQuery(Fields._PROMPTS_TABLE)

        sub_sql, params = self._compile_prompt_query()

        cond = RawCondition(
            f"{Fields._PROMPT_ID} IN ({sub_sql})",
            params,
        )

        q.filters = cond
        result = self.repo.execute(q)

        return len(result)
