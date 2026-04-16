from dataclasses import dataclass, field


@dataclass
class ChangedMessage:
    """Сообщение, присутствующее в обеих версиях, но с измененным content."""

    index: int
    role: str
    old_content: str
    new_content: str
    line_diff: list[str] = field(default_factory=list)


@dataclass
class StructuredDiff:
    """Структурный diff между двумя версиями промпта на уровне сообщений (ВИ-7)."""

    name_a: str
    name_b: str
    added: list[tuple[str, str]] = field(default_factory=list)
    deleted: list[tuple[str, str]] = field(default_factory=list)
    changed: list[ChangedMessage] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.deleted or self.changed)


@dataclass
class VersionLineDiff:
    name_a: str
    name_b: str
    hunks: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.hunks)

    def unified(self) -> str:
        return "".join(self.hunks)


@dataclass
class DiffChunk:
    tag: str
    old_start: int
    old_end: int
    new_start: int
    new_end: int
    old_text: str
    new_text: str


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
