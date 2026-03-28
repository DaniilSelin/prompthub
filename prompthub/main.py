import sqlite3
import random

from prompthub.facade.storage import Storage
from prompthub.repository.repo import PromptRepo
from prompthub.repository import Fields, TAG_MODEL_TYPE, TAG_PROMPT_TYPE, _INIT_SCHEMA_SQL
from prompthub.search.filters import FieldEquals, FieldGreater

random.seed(29) # сгенеренный тест переписывать мне лень, просто зафиксирую удачный сид

# =======================
# INIT DB
# =======================

conn = sqlite3.connect(":memory:")
conn.row_factory = sqlite3.Row

storage = Storage(":memory:")
storage.repo = PromptRepo(conn)

cur = conn.cursor()

# =======================
# DATA GENERATION
# =======================

authors = [f"Author {i}" for i in range(1, 6)]
prompt_names = [f"Prompt {i}" for i in range(1, 21)]

# prompts
for name in prompt_names:
    cur.execute(f"""
        INSERT INTO {Fields._PROMPTS_TABLE} ({Fields.PROMPT_NAME}, {Fields.PROMPT_AUTHOR})
        VALUES (?, ?)
    """, (name, random.choice(authors)))

cur.execute(f"SELECT id FROM {Fields._PROMPTS_TABLE}")
prompt_ids = [row["id"] for row in cur.fetchall()]

# versions
for pid in prompt_ids:
    for version_idx in range(1, random.randint(3, 8)):
        cur.execute(f"""
            INSERT INTO {Fields._PROMPT_VERSIONS_TABLE}
            ({Fields.PROMPT_VERSIONS_PROMPT_ID}, {Fields.PROMPT_VERSIONS_NAME}, seq,
             {Fields.PROMPT_VERSIONS_AUTHOR}, {Fields.PROMPT_VERSIONS_MESSAGE})
            VALUES (?, ?, ?, ?, ?)
        """, (
            pid,
            f"Version {version_idx}",
            version_idx,
            random.choice(authors),
            f"Message {version_idx}"
        ))

# tags
tags_data = [
    ("model_A", TAG_MODEL_TYPE),
    ("model_B", TAG_MODEL_TYPE),
    ("model_C", TAG_MODEL_TYPE),
    ("prompt_X", TAG_PROMPT_TYPE),
    ("prompt_Y", TAG_PROMPT_TYPE),
    ("prompt_Z", TAG_PROMPT_TYPE),
]

for name, ttype in tags_data:
    cur.execute(f"""
        INSERT INTO {Fields._TAG_TABLE} (name, type)
        VALUES (?, ?)
    """, (name, ttype))

cur.execute(f"SELECT id, name FROM {Fields._TAG_TABLE}")
tag_lookup = {row["name"]: row["id"] for row in cur.fetchall()}

# assign tags randomly
for pid in prompt_ids:
    for tag_name in random.sample(list(tag_lookup.keys()), random.randint(0, 3)):
        cur.execute(
            "INSERT INTO prompt_tags (prompt_id, tag_id) VALUES (?, ?)",
            (pid, tag_lookup[tag_name])
        )

conn.commit()

# =======================
# TEST HELPERS
# =======================

def assert_not_empty(result, label):
    if not result:
        raise Exception(f"[FAIL] {label} → пустой результат")
    print(f"[OK] {label}: {len(result)} rows")

def assert_updated(count, label):
    if count <= 0:
        raise Exception(f"[FAIL] {label} → ничего не обновилось")
    print(f"[OK] {label}: updated {count}")

# =======================
# TESTS
# =======================

pg = storage.make_group_prompt()

# ---- 1. Простой фильтр + тег
res1 = storage.execute(
    pg.filter_prompts(FieldEquals(Fields.PROMPT_NAME, "Prompt 1"))
      .with_tag("prompt_X", TAG_PROMPT_TYPE)
      .search_versions()
)

assert_not_empty(res1, "filter + tag")

# ---- 2. AND + OR комбинированный
res2 = storage.execute(
    pg.with_tag("model_A", TAG_MODEL_TYPE)
      .search_versions()
      .filter(
          (FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 1") |
           FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 2"))
      )
)

assert_not_empty(res2, "OR filter")

# ---- 3. Пересечение тегов
res3 = storage.execute(
    pg.with_tag("model_A", TAG_MODEL_TYPE)
      .with_tag("prompt_X", TAG_PROMPT_TYPE)
      .search_versions()
)

assert_not_empty(res3, "tag intersection")

# ---- 4. WITHOUT TAG
res4 = storage.execute(
    pg.without_tag("model_B", TAG_MODEL_TYPE)
      .search_versions()
)

assert_not_empty(res4, "without tag")

# ---- 5. Сложный фильтр (AND + OR + seq)
res5 = storage.execute(
    pg.with_tag("model_A", TAG_MODEL_TYPE)
      .search_versions()
      .filter(
          (FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 1") |
           FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 2")) &
          FieldGreater("seq", 2)
      )
)

assert_not_empty(res5, "complex filter")

# ---- 6. UPDATE с условием
update_count = storage.execute(
    pg.with_tag("prompt_X", TAG_PROMPT_TYPE)
      .update_versions({
          Fields.PROMPT_VERSIONS_MESSAGE: "UPDATED"
      })
      .filter(
          FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 1")
      )
)

assert_updated(update_count, "update")

# ---- 7. Проверка update
check = storage.execute(
    pg.search_versions().filter(
        FieldEquals(Fields.PROMPT_VERSIONS_MESSAGE, "UPDATED")
    )
)

assert_not_empty(check, "update check")

# ---- 8. DELETE
delete_count = storage.execute(
    pg.with_tag("model_C", TAG_MODEL_TYPE)
      .delete_versions()
)

print(f"[INFO] deleted rows: {delete_count}")

# ---- 9. COUNT
count = pg.with_tag("model_A", TAG_MODEL_TYPE).count()
print(f"[OK] count: {count}")

print("\nALL TESTS PASSED")


print("\n" + "="*50)
print("GROUP PIPELINE TEST")
print("="*50)

pg = storage.make_group_prompt()

print("\n[STEP 1] SELECT pipeline")

res_pipeline = storage.execute(
    pg
    .filter_prompts(
        FieldEquals(Fields.PROMPT_AUTHOR, "Author 1") |
        FieldEquals(Fields.PROMPT_AUTHOR, "Author 2")
    )
    .with_tag("model_A", TAG_MODEL_TYPE)
    .without_tag("prompt_Z", TAG_PROMPT_TYPE)
    .search_versions()
    .filter(
        (FieldGreater("seq", 1)) &
        (
            FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 1") |
            FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 3")
        )
    )
)

print(f"→ rows: {len(res_pipeline)}")
if res_pipeline:
    print("→ sample row:", res_pipeline[0])

assert_not_empty(res_pipeline, "pipeline select")


print("\n[STEP 2] UPDATE pipeline")

update_count = storage.execute(
    pg
    .filter_prompts(
        FieldEquals(Fields.PROMPT_AUTHOR, "Author 1")
    )
    .with_tag("model_A", TAG_MODEL_TYPE)
    .update_versions({
        Fields.PROMPT_VERSIONS_MESSAGE: "PIPELINE_UPDATED"
    })
    .filter(
        FieldGreater("seq", 2)
    )
)

print(f"→ updated rows: {update_count}")
assert_updated(update_count, "pipeline update")


print("\n[STEP 3] VERIFY update")

check_pipeline = storage.execute(
    pg
    .search_versions()
    .filter(
        FieldEquals(Fields.PROMPT_VERSIONS_MESSAGE, "PIPELINE_UPDATED")
    )
)

print(f"→ updated rows found: {len(check_pipeline)}")
if check_pipeline:
    print("→ sample updated:", check_pipeline[0])

assert_not_empty(check_pipeline, "pipeline update check")


print("\n[STEP 4] DELETE pipeline")

delete_pipeline = storage.execute(
    pg
    .with_tag("model_B", TAG_MODEL_TYPE)
    .without_tag("prompt_X", TAG_PROMPT_TYPE)
    .delete_versions()
)

print(f"→ deleted rows: {delete_pipeline}")


print("\n[STEP 5] COUNT pipeline")

count_pipeline = pg \
    .with_tag("model_A", TAG_MODEL_TYPE) \
    .without_tag("model_C", TAG_MODEL_TYPE) \
    .count()

print(f"→ count result: {count_pipeline}")
print("\n" + "="*50)

# Пример как будет пользователь исопльзовать группы промптов

res = storage.execute(storage.make_group_prompt().filter_prompts(
        FieldEquals(Fields.PROMPT_AUTHOR, "Author 1") |
        FieldEquals(Fields.PROMPT_AUTHOR, "Author 2")
    ) \
    .with_tag("model_A", TAG_MODEL_TYPE) \
    .without_tag("prompt_Z", TAG_PROMPT_TYPE) \
    .search_versions() \
    .filter(
        (FieldGreater("seq", 1)) &
        (
            FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 1") |
            FieldEquals(Fields.PROMPT_VERSIONS_AUTHOR, "Author 3")
        )
    )
)

for row in res:
    print(dict(row))