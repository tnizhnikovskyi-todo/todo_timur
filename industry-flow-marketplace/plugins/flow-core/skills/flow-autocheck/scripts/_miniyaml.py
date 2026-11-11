"""Мінімальний розбір YAML-підмножини (stdlib) для check_*.py: блокові відображення/списки, потокові {..} і [..], скаляри.
Не універсальний парсер: якорі, багаторядкові рядки, теги не підтримуються. Підключається за шляхом (python3 -I не додає теку скрипта в sys.path)."""
import re


def _strip_comment(s):
    q = None
    for i, ch in enumerate(s):
        if q:
            if ch == q:
                q = None
        elif ch in "\"'":
            q = ch
        elif ch == "#" and (i == 0 or s[i - 1] in " \t"):
            return s[:i].rstrip()
    return s.rstrip()


def _split_top(s, sep=","):
    out, depth, q, cur = [], 0, None, ""
    for ch in s:
        if q:
            cur += ch
            if ch == q:
                q = None
            continue
        if ch in "\"'":
            q = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def scalar(v):
    v = v.strip()
    if v == "":
        return None
    if v.startswith("{{"):  # плейсхолдер шаблону, а не потокова мапа
        return v
    if v[0] in "\"'" and v[-1] == v[0] and len(v) >= 2:
        return v[1:-1]
    if v[0] == "[" and v[-1] == "]":
        return [scalar(x) for x in _split_top(v[1:-1])]
    if v[0] == "{" and v[-1] == "}":
        d = {}
        for part in _split_top(v[1:-1]):
            k, _, val = part.partition(":")
            d[k.strip().strip("\"'")] = scalar(val)
        return d
    low = v.lower()
    if low in ("null", "~"):
        return None
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d+\.\d+", v):
        return float(v)
    return v


def loads(text):
    lines = []
    for raw in text.splitlines():
        s = _strip_comment(raw.replace("\t", "  "))
        if s.strip() and not s.strip().startswith("---"):
            lines.append((len(s) - len(s.lstrip()), s.strip()))
    pos = [0]

    def block(indent):
        if pos[0] >= len(lines):
            return None
        if lines[pos[0]][1].startswith("- ") or lines[pos[0]][1] == "-":
            res = []
            while pos[0] < len(lines) and lines[pos[0]][0] == indent and (lines[pos[0]][1].startswith("- ") or lines[pos[0]][1] == "-"):
                body = lines[pos[0]][1][1:].strip()
                pos[0] += 1
                m = re.match(r"^([^\s\"'{\[][^:]*?):(\s+(.*))?$", body)
                if body and m and not body.startswith(("{", "[")):
                    d = {m.group(1).strip(): scalar(m.group(3) or "") if (m.group(3) or "").strip() else None}
                    if not (m.group(3) or "").strip() and pos[0] < len(lines) and lines[pos[0]][0] > indent:
                        d[m.group(1).strip()] = block(lines[pos[0]][0])
                    while pos[0] < len(lines) and lines[pos[0]][0] > indent:
                        d.update(block(lines[pos[0]][0]) or {})
                    res.append(d)
                elif body:
                    res.append(scalar(body))
                elif pos[0] < len(lines) and lines[pos[0]][0] > indent:
                    res.append(block(lines[pos[0]][0]))
                else:
                    res.append(None)
            return res
        d = {}
        while pos[0] < len(lines) and lines[pos[0]][0] == indent and not lines[pos[0]][1].startswith("- "):
            ind, body = lines[pos[0]]
            m = re.match(r"^(\"[^\"]*\"|'[^']*'|[^:]+?):(?:\s+(.*))?$", body)
            if not m:
                pos[0] += 1
                continue
            key = m.group(1).strip().strip("\"'")
            val = (m.group(2) or "").strip()
            pos[0] += 1
            if val:
                d[key] = scalar(val)
            elif pos[0] < len(lines) and (lines[pos[0]][0] > ind or (lines[pos[0]][0] == ind and lines[pos[0]][1].startswith("- "))):
                d[key] = block(lines[pos[0]][0])
            else:
                d[key] = None
        return d

    return block(lines[0][0]) if lines else {}


def flatten(obj, prefix=""):
    """{'a': {'b': [1, {'c': 2}]}} -> {'a.b.0': 1, 'a.b.1.c': 2}"""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.update(flatten(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out.update(flatten(v, f"{prefix}.{i}"))
    else:
        out[prefix] = obj
    return out
