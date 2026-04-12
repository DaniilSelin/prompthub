import pytest

from prompthub.facade.storage import Storage


@pytest.fixture
def storage(tmp_path):
    storage_obj = Storage(str(tmp_path / "test.sqlite3"))
    yield storage_obj
    storage_obj._conn.close()
