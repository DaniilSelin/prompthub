TAG_MODEL_TYPE, TAG_PROMPT_TYPE = "model", "prompt"

class _Fields():
    _PROMPTS_TABLE = "prompts"
    _PROMPT_VERSIONS_TABLE = "prompt_versions"
    _TAG_TABLE = "tags"

    _PROMPT_ID = "id"
    PROMPT_NAME = "name"
    PROMPT_AUTHOR = "author"
    PROMPT_CREATED_AT = "created_at"

    PROMPT_VERSIONS_PROMPT_ID = "prompt_id"
    PROMPT_VERSIONS_NAME = "name"

    PROMPT_VERSIONS_AUTHOR = "author"
    PROMPT_VERSIONS_MESSAGE = "message"
    PROMPT_VERSIONS_HAVE_SNAPSHOT = "have_snapshot"

    PROMPT_VERSIONS_CREATED_AT = "created_at"

    TAG_NAME = "name"
    TAG_TYPE = "type"

_INIT_SCHEMA_SQL = f"""
CREATE TABLE {_Fields._PROMPTS_TABLE} (
    {_Fields._PROMPT_ID} INTEGER PRIMARY KEY AUTOINCREMENT,
    {_Fields.PROMPT_NAME} TEXT NOT NULL,
    {_Fields.PROMPT_AUTHOR} TEXT NULL,
    {_Fields.PROMPT_CREATED_AT} TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE {_Fields._PROMPT_VERSIONS_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    {_Fields.PROMPT_VERSIONS_PROMPT_ID} INTEGER NOT NULL,

    {_Fields.PROMPT_VERSIONS_NAME} TEXT NOT NULL,
    seq INTEGER NOT NULL,

    parent_version_id INTEGER NULL,
    snapshot_content TEXT NULL,

    {_Fields.PROMPT_VERSIONS_AUTHOR} TEXT NULL,
    {_Fields.PROMPT_VERSIONS_MESSAGE} TEXT NULL,

    {_Fields.PROMPT_VERSIONS_CREATED_AT} TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY ({_Fields.PROMPT_VERSIONS_PROMPT_ID}) REFERENCES {_Fields._PROMPTS_TABLE}(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_version_id) REFERENCES {_Fields._PROMPT_VERSIONS_TABLE}(id),

    UNIQUE({_Fields.PROMPT_VERSIONS_PROMPT_ID}, seq)
);

CREATE TABLE prompt_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL,

    op_index INTEGER NOT NULL,
    op_type TEXT NOT NULL,

    pos INTEGER NULL,
    start INTEGER NULL,
    end INTEGER NULL,
    text TEXT NULL,

    CHECK (
        (op_type='insert'  AND pos IS NOT NULL AND text IS NOT NULL) OR
        (op_type='delete'  AND start IS NOT NULL AND end IS NOT NULL) OR
        (op_type='replace' AND start IS NOT NULL AND end IS NOT NULL AND text IS NOT NULL)
    ),

    FOREIGN KEY (version_id) REFERENCES {_Fields._PROMPT_VERSIONS_TABLE}(id) ON DELETE CASCADE,
    UNIQUE(version_id, op_index)
);

CREATE TABLE {_Fields._TAG_TABLE} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    {_Fields.TAG_NAME} TEXT NOT NULL,
    {_Fields.TAG_TYPE} TEXT NOT NULL CHECK({_Fields.TAG_TYPE} IN ('{TAG_MODEL_TYPE}', '{TAG_PROMPT_TYPE}')),
    UNIQUE({_Fields.TAG_NAME}, {_Fields.TAG_TYPE})
);

CREATE TABLE prompt_tags (
    prompt_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,

    PRIMARY KEY(prompt_id, tag_id),

    FOREIGN KEY(prompt_id) REFERENCES {_Fields._PROMPTS_TABLE}(id) ON DELETE CASCADE,
    FOREIGN KEY(tag_id) REFERENCES {_Fields._TAG_TABLE}(id) ON DELETE CASCADE
);

CREATE INDEX idx_prompt_tags_prompt ON prompt_tags(prompt_id);
CREATE INDEX idx_prompt_tags_tag ON prompt_tags(tag_id);

CREATE INDEX idx_pv_prompt_seq
ON {_Fields._PROMPT_VERSIONS_TABLE}({_Fields.PROMPT_VERSIONS_PROMPT_ID}, seq);

CREATE INDEX idx_pv_prompt_name
ON {_Fields._PROMPT_VERSIONS_TABLE}({_Fields.PROMPT_VERSIONS_PROMPT_ID}, {_Fields.PROMPT_VERSIONS_NAME});

CREATE INDEX idx_pv_snapshot
ON {_Fields._PROMPT_VERSIONS_TABLE}({_Fields.PROMPT_VERSIONS_PROMPT_ID}, seq DESC)
WHERE snapshot_content IS NOT NULL;
"""