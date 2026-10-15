"""Підмножина JSONPath: `$.a.b[0].c` (SPEC §8.6.2)."""
from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"\.([A-Za-z_][A-Za-z0-9_\-]*)|\[(\d+)\]|\['([^']+)'\]")


class _Missing:
    def __repr__(self) -> str:
        return "MISSING"


MISSING: Any = _Missing()


def parse(path: str) -> list[str | int]:
    """Розбирає шлях у список ключів/індексів; ValueError для недопустимого синтаксису (`$..x`, `a.b`)."""
    if not isinstance(path, str) or not path.startswith("$"):
        raise ValueError(f"invalid jsonpath: {path!r}")
    rest = path[1:]
    out: list[str | int] = []
    pos = 0
    while pos < len(rest):
        m = _TOKEN.match(rest, pos)
        if not m:
            raise ValueError(f"invalid jsonpath: {path!r}")
        if m.group(1) is not None:
            out.append(m.group(1))
        elif m.group(2) is not None:
            out.append(int(m.group(2)))
        else:
            out.append(m.group(3))
        pos = m.end()
    return out


def get(path: str, obj: Any, default: Any = MISSING) -> Any:
    """Значення за шляхом. Відсутній шлях -> `default`; без `default` — KeyError. Невалідний шлях — ValueError."""
    cur = obj
    for key in parse(path):
        try:
            if isinstance(key, int):
                if not isinstance(cur, list):
                    raise KeyError(path)
                cur = cur[key]
            else:
                if not isinstance(cur, dict):
                    raise KeyError(path)
                cur = cur[key]
        except (KeyError, IndexError):
            if default is MISSING:
                raise KeyError(path) from None
            return default
    return cur
