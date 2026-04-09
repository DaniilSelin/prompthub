from dataclasses import dataclass


@dataclass
class PromptMessages:
    """Внутреннее представление промпта, готового к использованию."""

    name: str
    version: str
    content: list[tuple[str, str]]
