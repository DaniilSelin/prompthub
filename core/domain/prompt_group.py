from .tag import PromptTag
from .prompt import Prompt

class PromptGroupInfo:
    pass

"""
Была какач то идея. Существование класса под вопросом.
"""
class PromptGroup:
    def __init__(self, prompts: list[Prompt]):
        self.prompts: list[Prompt] = prompts

    def search(selfy) -> 'PromptGroup':
        raise NotImplementedError("не реализовано")

    def with_tag(self) -> 'PromptGroup':
        raise NotImplementedError("не реализовано")

    def without_tag(self) -> 'PromptGroup':
        raise NotImplementedError("не реализовано")

    # batch операции
    def add_tag(self):
        raise NotImplementedError("не реализовано")

    def remove_tag(self):
        raise NotImplementedError("не реализовано")

    def add_version_to_all(self):
        raise NotImplementedError("не реализовано")

    def remove_version_from_all(self):
        raise NotImplementedError("не реализовано")

    def update_version_content(self):
        raise NotImplementedError("не реализовано")

    # статистики группы
    def list_all_versions(self) -> PromptGroupInfo:
        raise NotImplementedError("не реализовано")

    def list_all_tags(self) -> list[PromptTag]:
        raise NotImplementedError("не реализовано")

    def count(self) -> int:
        return len(self.prompts)
