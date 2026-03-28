import pytest

from prompthub.core.domain.operations import DeleteOperation, InsertOperation, ReplaceOperation
from prompthub.facade.prompt import Prompt


@pytest.mark.unit
def test_uc03_002_build_changeset_produces_insert_delete_replace_with_indices():
    prompt = Prompt(id=1, repo=None)

    insert_ops = prompt._build_changeset("abc", "abXc")
    assert len(insert_ops) == 1
    assert isinstance(insert_ops[0], InsertOperation)
    assert insert_ops[0].pos == 2
    assert insert_ops[0].text == "X"

    delete_ops = prompt._build_changeset("abXc", "abc")
    assert len(delete_ops) == 1
    assert isinstance(delete_ops[0], DeleteOperation)
    assert delete_ops[0].start == 2
    assert delete_ops[0].end == 3

    replace_ops = prompt._build_changeset("abc", "aZc")
    assert len(replace_ops) == 1
    assert isinstance(replace_ops[0], ReplaceOperation)
    assert replace_ops[0].start == 1
    assert replace_ops[0].end == 2
    assert replace_ops[0].text == "Z"


@pytest.mark.unit
def test_uc07_001_changeset_operations_transform_old_into_new():
    prompt = Prompt(id=1, repo=None)
    old = "Hello brave world"
    new = "Hello world!"

    ops = prompt._build_changeset(old, new)

    transformed = old
    for op in ops:
        transformed = op.apply(transformed)

    assert transformed == new
