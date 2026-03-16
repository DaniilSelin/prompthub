import sqlite3
from core.domain.prompt_group import PromptGroup
from facade.storage import Storage
from repository.queries import SearchQuery
from repository import _Fields, TAG_MODEL_TYPE, TAG_PROMPT_TYPE, _INIT_SCHEMA_SQL
from search.filters import FieldGreater

import sqlite3
from repository import _Fields, TAG_MODEL_TYPE, TAG_PROMPT_TYPE, _INIT_SCHEMA_SQL

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
        INSERT INTO {_Fields._PROMPTS_TABLE} ({_Fields.PROMPT_NAME}, {_Fields.PROMPT_AUTHOR})
        VALUES (?, ?)
    """, (name, author))

cur.execute(f"SELECT id FROM {_Fields._PROMPTS_TABLE}")
prompt_ids = [row["id"] for row in cur.fetchall()]

for pid, (_, author) in zip(prompt_ids, prompts_data):
    for version_idx in range(1, 4):
        cur.execute(f"""
            INSERT INTO {_Fields._PROMPT_VERSIONS_TABLE} 
            ({_Fields.PROMPT_VERSIONS_PROMPT_ID}, {_Fields.PROMPT_VERSIONS_NAME}, seq, {_Fields.PROMPT_VERSIONS_AUTHOR}, {_Fields.PROMPT_VERSIONS_MESSAGE})
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
        INSERT INTO {_Fields._TAG_TABLE} (name, type) VALUES (?, ?)
    """, (name, ttype))

cur.execute(f"SELECT id FROM {_Fields._TAG_TABLE}")
tag_ids = [row["id"] for row in cur.fetchall()]

for pid in prompt_ids:
    for tid in tag_ids:
        cur.execute("INSERT INTO prompt_tags (prompt_id, tag_id) VALUES (?, ?)", (pid, tid))

conn.commit()

print("Промпты:")
for row in cur.execute(f"SELECT * FROM {_Fields._PROMPTS_TABLE}"):
    print(dict(row))

print("\nВерсии:")
for row in cur.execute(f"SELECT * FROM {_Fields._PROMPT_VERSIONS_TABLE}"):
    print(dict(row))

print("\nТеги:")
for row in cur.execute(f"SELECT * FROM {_Fields._TAG_TABLE}"):
    print(dict(row))

print("\nСвязи prompt ↔ tag:")
for row in cur.execute("SELECT * FROM prompt_tags"):
    print(dict(row))

storage = Storage(":memory:")
storage._conn = conn

base_query = storage.make_search_query()
pg = storage.make_group_prompt(base_query)

pg_model_2 = pg.with_tag("model_tag_2", TAG_MODEL_TYPE)
print("Промпты с моделью 2:", pg_model_2._fetch_prompt_ids())

pg_prompt_tag_1 = pg.with_tag("prompt_tag_1", TAG_PROMPT_TYPE)
print("Промпты с промт-тегом 1:", pg_prompt_tag_1._fetch_prompt_ids())

pg_combined = pg.with_tag("model_tag_1", TAG_MODEL_TYPE).with_tag("prompt_tag_1", TAG_PROMPT_TYPE)
print("Комбинация модель 1 + промт-тег 1:", pg_combined._fetch_prompt_ids())

version_filter = FieldGreater("seq", 0)
versions = pg.list_versions(version_filter)
print("Все версии группы:", [(v["prompt_id"], v["seq"]) for v in versions])
print("Количество промптов в группе:", pg.count())

from search.filters import FieldEquals, Filter

print(storage.execute(
    storage.make_group_prompt(
         storage.make_search_query().filter(FieldEquals(_Fields.PROMPT_NAME, "Prompt 1")) # фильтруем промпты, которые войдут в группу
        ).with_tag("prompt_tag_1", TAG_PROMPT_TYPE) \
            .make_search_query() 
           .filter(
                FieldEquals(_Fields.PROMPT_VERSIONS_AUTHOR, "Author 3") | 
                FieldEquals(_Fields.PROMPT_VERSIONS_AUTHOR, "Author 2")
            ) # фильруем версии промптов группы
        )
)
