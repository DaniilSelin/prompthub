from dataclasses import dataclass, field


@dataclass
class VersionLineDiff:
    name_a: str
    name_b: str
    hunks: list[str] = field(default_factory=list)  # строки unified diff

    @property
    def has_changes(self) -> bool:
        return bool(self.hunks)

    def unified(self) -> str:
        return "".join(self.hunks)


@dataclass
class DiffChunk:
    tag: str  # 'equal' | 'insert' | 'delete' | 'replace'
    old_start: int  # позиция в content_a
    old_end: int
    new_start: int  # позиция в content_b
    new_end: int
    old_text: str  # фрагмент из version_a (пусто для 'insert')
    new_text: str  # фрагмент из version_b (пусто для 'delete')


@dataclass
class VersionDiff:
    name_a: str
    name_b: str
    chunks: list[DiffChunk]

    @property
    def has_changes(self) -> bool:
        return any(c.tag != "equal" for c in self.chunks)

    def only_changes(self) -> list[DiffChunk]:
        return [c for c in self.chunks if c.tag != "equal"]
