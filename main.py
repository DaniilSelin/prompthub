from search.filters import FieldEquals, FieldGreater, FieldLike
from facade.storage import Storage

storage = Storage("/tmp/mydb.sqlite")

results = (
    storage.execute(storage.make_search_query(text="important")
        .filter(
            (FieldEquals("author", "daniel") & FieldGreater("version", 2))
            | FieldLike("content", "%agent%")
            & ~FieldEquals("status", "archived")
        )
        .order_by("version")
        .limit(5)
    )
)

storage.execute(storage.make_update_query({"status": "reviewed"}) \
    .filter(
        (FieldEquals("author", "daniel") | FieldEquals("status", "active"))
        & ~FieldLike("content", "%deprecated%")
    )
)

storage.execute(storage.make_insert_query({
        "author": "daniel",
        "content": "Очень важный промпт",
        "version": 3,
        "status": "active"
    })
)

storage.execute(storage.make_delete_query() \
    .filter(
        (FieldEquals("status", "deprecated") | FieldGreater("version", 5))
        & ~FieldEquals("author", "admin")
    )
)

from core.domain.prompt import Prompt

p = Prompt("prompt_1", snapshot_interval=3)

p.add_version("Hello world")           # v1 snapshot
p.add_version("Hello amazing world")   # v2 diff
p.add_version("Hi amazing world")      # v3 diff
p.add_version("Hi world")              # v4 diff -> после этого создастся v5 snapshot

print("\n--- BUILD TEST ---")

print("build v1:", p.assemble_version("1"))
print("build v2:", p.assemble_version("2"))
print("build v3:", p.assemble_version("3"))
print("build v4:", p.assemble_version("4"))
print("build v5:", p.assemble_version("5"))
