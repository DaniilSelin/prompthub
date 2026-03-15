from .tag import PromptTag, ModelTag
from repository.queries import BaseQuery
from repository.query_factory import QueryFactory

class PromptVersion:
    def __init__(self, version: str):
        self.version: str = version

class Prompt(QueryFactory):
    tabel: str  = "prompt_versions"

    def __init__(self, id: str, tags: list[PromptTag] | None = None):
        self.id: str = id
        self.versions: list[PromptVersion] = []
        self.tags: list[PromptTag] = tags or []

    def execute(self, query: BaseQuery):
        sql, params = query.build()

        print(sql)
        print(params)
        return []

    def add_tag_prompt(self, tag: PromptTag):
        raise NotImplementedError("не реализовано")
    
    def add_tag_model(self, tag: ModelTag) -> None:
        raise NotImplementedError("не реализовано")   

    def remove_tag(self, tag_name: str) -> None:
        raise NotImplementedError("не реализовано")

    def list_tags(self) -> list[PromptTag]:
        raise NotImplementedError("не реализовано")

    def latest_version_ref(self) -> str:
        raise NotImplementedError("не реализовано")
    
    def version_history(self):
        raise NotImplementedError("не реализовано")
