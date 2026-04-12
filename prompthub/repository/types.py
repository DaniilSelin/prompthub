from typing import Any, TypeAlias, TypedDict

SQLParam: TypeAlias = str | int | float | bytes | None
ExecuteResult: TypeAlias = list[dict[str, Any]] | int


class PromptRow(TypedDict):
    id: int
    name: str
    snapshot_interval: int
    created_at: str


class PromptIdRow(TypedDict):
    id: int


class VersionRow(TypedDict):
    id: int
    prompt_id: int
    name: str
    seq: int
    parent_version_id: int | None
    snapshot_content: str | None
    message: str | None
    created_at: str


class VersionRangeRow(TypedDict):
    id: int
    seq: int


class TagRow(TypedDict):
    name: str
    type: str
    provider: str | None


class ModelTagRow(TypedDict):
    name: str
    provider: str | None


class PromptMetadata(TypedDict):
    name: str
    created_at: str
    updated_at: str | None
    tags: list[str]
    model_tags: list[ModelTagRow] | None


class TariffRow(TypedDict):
    tag_name: str
    provider: str
    input_price_per_1m: float
    output_price_per_1m: float


class CostEntry(TypedDict):
    token_count: int
    cost: float | None


class PromptListItem(PromptMetadata):
    costs: dict[str, CostEntry] | None
