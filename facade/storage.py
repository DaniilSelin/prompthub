from facade.prompt import Prompt
from facade.prompt_group import PromptGroup
from repository.repo import PromptRepo
from repository import Fields
from repository.query_factory import QueryFactory
from repository.queries import BaseQuery 

from pathlib import Path
import sqlite3

class Storage(QueryFactory):
    table: str = Fields._PROMPTS_TABLE

    def __init__(self, path: str):
        self.storage_path: Path = Path(path)
        self._conn = sqlite3.connect(self.storage_path)
        self._conn.row_factory = sqlite3.Row

        self.repo = PromptRepo(self._conn)

    def execute(self, query: BaseQuery):
        return self.repo.execute(query)

    def create_prompt(
        self,
        name: str,
        author: str | None = None,
    ) -> Prompt:
        prompt_id = self.repo.create_prompt(name, author)
        return Prompt(prompt_id, self.repo)

    def get_prompt(self, name: str) -> Prompt:
        row = self.repo.get_prompt_by_name(name)
        if not row:
            raise ValueError("prompt not found")

        return Prompt(row["id"], self.repo)

    def delete_prompt(self, name: str):
        row = self.repo.get_prompt_by_name(name)
        if not row:
            return 0

        return self.repo.delete_prompt(row["id"])

    def make_group_prompt(self) -> PromptGroup:
        return PromptGroup(self.repo)