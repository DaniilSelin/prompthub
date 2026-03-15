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