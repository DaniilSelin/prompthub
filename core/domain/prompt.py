from .tag import PromptTag, ModelTag

class PromptVersion:
    def __init__(self, version: str):
        self.version: str = version

class Prompt:
    def __init__(self, id: str, tags: list[PromptTag] | None = None):
        self.id: str = id
        self.versions: list[PromptVersion] = []
        self.tags: list[PromptTag] = tags or []

    def search_versions(self) -> list[PromptVersion]:
        raise NotImplementedError("не реализовано")

    def update_versions(self) -> None:
        raise NotImplementedError("не реализовано")

    def add_version(self) -> PromptVersion:
        raise NotImplementedError("не реализовано")

    def remove_version(self) -> None:
        raise NotImplementedError("не реализовано")

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

