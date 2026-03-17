import sqlite3
from core.domain.prompt_group import PromptGroup
from facade.storage import Storage
from repository.queries import SearchQuery
from repository import Fields, TAG_MODEL_TYPE, TAG_PROMPT_TYPE, _INIT_SCHEMA_SQL
from search.filters import FieldGreater

import sqlite3
from repository import Fields, TAG_MODEL_TYPE, TAG_PROMPT_TYPE, _INIT_SCHEMA_SQL

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row
conn.executescript(_INIT_SCHEMA_SQL)
conn.commit()

cur = conn.cursor()

prompts_data = [
    ("Prompt 1", "Author 1"),
    ("Prompt 2", "Author 2"),
    ("Prompt 3", "Author 3"),
    ("Prompt 4", "Author 4"),
]
for name, author in prompts_data:
    cur.execute(f"""
        INSERT INTO {Fields._PROMPTS_TABLE} ({Fields.PROMPT_NAME}, {Fields.PROMPT_AUTHOR})
        VALUES (?, ?)
    """, (name, author))

cur.execute(f"SELECT id FROM {Fields._PROMPTS_TABLE}")
prompt_ids = [row["id"] for row in cur.fetchall()]

for pid, (_, author) in zip(prompt_ids, prompts_data):
    for version_idx in range(1, 4):
        cur.execute(f"""
            INSERT INTO {Fields._PROMPT_VERSIONS_TABLE} 
            ({Fields.PROMPT_VERSIONS_PROMPT_ID}, {Fields.PROMPT_VERSIONS_NAME}, seq, {Fields.PROMPT_VERSIONS_AUTHOR}, {Fields.PROMPT_VERSIONS_MESSAGE})
            VALUES (?, ?, ?, ?, ?)
        """, (
            pid,
            f"Initial Version {version_idx}",
            version_idx,
            f"{author}",
            f"Message {version_idx}"
        ))

tags_data = [
    ("model_tag_1", TAG_MODEL_TYPE),
    ("model_tag_2", TAG_MODEL_TYPE),
    ("prompt_tag_1", TAG_PROMPT_TYPE),
    ("prompt_tag_2", TAG_PROMPT_TYPE),
]
for name, ttype in tags_data:
    cur.execute(f"""
        INSERT INTO {Fields._TAG_TABLE} (name, type) VALUES (?, ?)
    """, (name, ttype))

cur.execute(f"SELECT id, name FROM {Fields._TAG_TABLE}")
tag_lookup = {row["name"]: row["id"] for row in cur.fetchall()}

tag_map = {
    1: ["model_tag_1", "prompt_tag_1"],
    2: ["model_tag_1"],
    3: ["prompt_tag_1"],
    4: []
}

for pid, tag_names in tag_map.items():
    for tag_name in tag_names:
        cur.execute(
            "INSERT INTO prompt_tags (prompt_id, tag_id) VALUES (?, ?)",
            (pid, tag_lookup[tag_name])
        )

conn.commit()

print("Промпты:")
for row in cur.execute(f"SELECT * FROM {Fields._PROMPTS_TABLE}"):
    print(dict(row))

print("\nВерсии:")
for row in cur.execute(f"SELECT * FROM {Fields._PROMPT_VERSIONS_TABLE}"):
    print(dict(row))

print("\nТеги:")
for row in cur.execute(f"SELECT * FROM {Fields._TAG_TABLE}"):
    print(dict(row))

print("\nСвязи prompt ↔ tag:")
for row in cur.execute("SELECT * FROM prompt_tags"):
    print(dict(row))

storage = Storage(":memory:")
storage._conn = conn

base_query = storage.make_search_query()
pg = storage.make_group_prompt(base_query)

pg_model_2 = pg.with_tag("model_tag_2", TAG_MODEL_TYPE)
print("Промпты с моделью 2:", pg_model_2)

pg_prompt_tag_1 = pg.with_tag("prompt_tag_1", TAG_PROMPT_TYPE)
print("Промпты с промт-тегом 1:", pg_prompt_tag_1)

pg_combined = pg.with_tag("model_tag_1", TAG_MODEL_TYPE).with_tag("prompt_tag_1", TAG_PROMPT_TYPE)
print("Комбинация модель 1 + промт-тег 1:", pg_combined)

from search.filters import FieldEquals, Filter

print(storage.execute(
    storage.make_group_prompt(
         storage.make_search_query().filter(FieldEquals(Fields.PROMPT_NAME, "Prompt 1")) # фильтруем промпты, которые войдут в группу
        ).with_tag("prompt_tag_1", TAG_PROMPT_TYPE) \
            .make_search_query() 
           .filter(
                FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 1") | 
                FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 2")
            ) # фильруем версии промптов группы
        )
)

print("\n--- UPDATE TEST ---")

update_count = storage.execute(
    storage.make_group_prompt(
        storage.make_search_query().filter(
            FieldEquals(Fields.PROMPT_NAME, "Prompt 1")
        )
    )
    .with_tag("prompt_tag_1", TAG_PROMPT_TYPE)
    .make_update_query({
        Fields.PROMPT_VERSIONS_MESSAGE: "UPDATED_MESSAGE"
    })
    .filter(
        FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 1")
    )
)

print("updated rows:", update_count)

print("\nПроверка:")

print(storage.execute(
    storage.make_group_prompt(
        storage.make_search_query().filter(
            FieldEquals(Fields.PROMPT_NAME, "Prompt 1")
        )
    ) \
    .without_tag('prompt_tag_2', TAG_PROMPT_TYPE) \
    .make_search_query().filter(
        FieldEquals(Fields.PROMPT_VERSIONS_NAME, "Initial Version 1") & FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 1")
    )
))
