from search.filters import FieldEquals, FieldGreater, FieldLike
from facade.storage import Storage

storage = Storage("/tmp/mydb.sqlite")

results = (
    storage.search("prompts", text="important")
    .filter(
        (FieldEquals("author", "daniel") & FieldGreater("version", 2))
        | FieldLike("content", "%agent%")
        & ~FieldEquals("status", "archived")
    )
    .order_by("version")
    .limit(5)
    .offset(10)
    .execute()
)

storage.update("prompts", {"status": "reviewed"}) \
    .filter(
        (FieldEquals("author", "daniel") | FieldEquals("status", "active"))
        & ~FieldLike("content", "%deprecated%")
    ) \
    .execute()

storage.insert("prompts", {
    "author": "daniel",
    "content": "Очень важный промпт",
    "version": 3,
    "status": "active"
}).execute()

storage.delete("prompts") \
    .filter(
        (FieldEquals("status", "deprecated") | FieldGreater("version", 5))
        & ~FieldEquals("author", "admin")
    ) \
    .execute()