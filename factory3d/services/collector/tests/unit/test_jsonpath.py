"""AC-79 (частина): util.jsonpath."""
from __future__ import annotations

import pytest

from collector.util import jsonpath


def test_get_paths():
    obj = {"a": {"b": [{"c": 5}, {"c": 6}]}, "online": True, "n": None, "x-y": 1}
    assert jsonpath.get("$.a.b[0].c", obj) == 5
    assert jsonpath.get("$.a.b[1].c", obj) == 6
    assert jsonpath.get("$.online", obj) is True
    assert jsonpath.get("$.n", obj) is None
    assert jsonpath.get("$.x-y", obj) == 1
    assert jsonpath.get("$", obj) is obj
    assert jsonpath.get("$['a'].b[0]", obj) == {"c": 5}


def test_missing_path():
    with pytest.raises(KeyError):
        jsonpath.get("$.a.zz", {"a": {}})
    with pytest.raises(KeyError):
        jsonpath.get("$.a[3]", {"a": [1]})
    assert jsonpath.get("$.a.zz", {"a": {}}, default=None) is None
    assert jsonpath.get("$.a.b", {"a": 5}, default="d") == "d"


@pytest.mark.parametrize("path", ["$..x", "a.b", "$.a[", "$.a[*]", "", "$.a b", "$.[0]"])
def test_invalid_paths(path):
    with pytest.raises(ValueError, match="invalid jsonpath"):
        jsonpath.get(path, {"a": 1})
