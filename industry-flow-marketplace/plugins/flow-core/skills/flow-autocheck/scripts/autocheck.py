#!/usr/bin/env python3
"""flow-autocheck: детермінована автоперевірка кроку флоу (stdlib, без PyYAML для перевірок).

Запуск: python3 -I autocheck.py --mode inputs|result|form --naryad <файл.json|yaml> --repo <тека> [--base SHA] [--head SHA]
        [--only <id перевірки>] [--out <тека>] [--agent-pattern REGEX]
        python3 -I autocheck.py --selftest
Специфікації кроків — ../references/checks/<крок>.yaml (синтаксис JSON, валідний YAML 1.2). Контракт — ../references/checks.md.
Код виходу: 0 PASS, 1 FAIL, 2 INCOMPLETE (є ERROR). Репо не змінюється; єдиний запис — `git fetch origin <повний SHA|гілка>`.
Однаковий вхід (ті самі SHA) -> однакова таблиця. Вміст файлів репо не виконується (маніфести — ast.literal_eval)."""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PLUGIN = os.path.dirname(os.path.dirname(SKILL))
SHA_RE = re.compile(r"(?i)\b(SHA|commit)\b[:\s]*([0-9a-f]{7,40})")  # id-patterns.md
TAG_RE = re.compile(r"^package/v\d+\.\d+(-odoo\d+)?$")  # id-patterns.md, q19
ORDER = ["FAIL", "ERROR", "WARN", "MANUAL", "SKIP", "PASS"]
PII = [  # pii-patterns.md; (тип, regex, статус при client_data != none)
    ("email", re.compile(r"[\w.+-]+@(?!example\.)[\w-]+\.[\w.-]+", re.I), "FAIL"),
    ("iban", re.compile(r"\bUA\d{2}[\s\d]{20,}", re.I), "FAIL"),
    ("edrpou", re.compile(r"ЄДРПОУ\D{0,5}\d{8}\b", re.I), "FAIL"),
    ("phone", re.compile(r"(?<![\w:])(\+?380[\s()-]?\d{2}[\s()-]?\d{3}[\s-]?\d{2}[\s-]?\d{2})(?!\w)"), "FAIL"),
    ("phone-bare", re.compile(r"(?<![\w:.,/-])(0\d{9})(?![\w.,/-])"), "WARN"),
    ("secret", re.compile(r"(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+", re.I), "FAIL"),
]


class Ctx:
    def __init__(self, a, naryad):
        self.repo, self.n, self.mode = a.repo, naryad, a.mode
        self.params = naryad.get("params") or {}
        g = naryad.get("git") or {}
        self.base = a.base or g.get("base")
        self.head = a.head or g.get("head")
        self.prev_arg = g.get("prev_tag")
        self.agent_pattern = a.agent_pattern
        self.rows = []
        self.cache = {}

    def add(self, i, st, msg="", ev="", route=None):
        self.rows.append({"id": i, "status": st, "msg": msg, "evidence": ev[:200], "route_on_fail": route})


def git(ctx, *args):
    p = subprocess.run(["git", "-c", "core.quotepath=off", "-C", ctx.repo, *args], capture_output=True, text=True)
    return p.returncode, p.stdout


def ensure_obj(ctx, sha):
    if not sha or git(ctx, "cat-file", "-e", sha + "^{commit}")[0] == 0:
        return True
    if re.fullmatch(r"[0-9a-f]{40}", sha):
        git(ctx, "fetch", "origin", sha)
    else:
        git(ctx, "fetch", "origin", (ctx.n.get("repo") or {}).get("base_branch", "main"))
    return git(ctx, "cat-file", "-e", sha + "^{commit}")[0] == 0


def prev_tag(ctx):
    if "prev" in ctx.cache:
        return ctx.cache["prev"]
    t = ctx.prev_arg if ctx.prev_arg and ctx.prev_arg != "null" else None
    if not t and ctx.head:
        rc, out = git(ctx, "tag", "--merged", ctx.head, "--list", "package/v*", "--sort=-v:refname")
        c = [x for x in out.split() if TAG_RE.match(x)]
        t = c[0] if c else None
    ctx.cache["prev"] = t
    return t


def read_rev(ctx, rev, path):
    rc, out = git(ctx, "show", f"{rev}:{path}")
    return out if rc == 0 else None


def resolve(ctx, ref):
    """ref: head:<p> | base:<p> | prev:<p> | in:<крок>  -> (текст|None, мітка)"""
    kind, _, p = ref.partition(":")
    if kind == "in":
        for i in ctx.n.get("inputs") or []:
            if i.get("from") == p and i.get("path"):
                return (read_rev(ctx, i.get("sha") or ctx.base, i["path"]), f"{i['path']}@{(i.get('sha') or '')[:8]}")
        return None, f"вхід {p} відсутній у наряді"
    rev = {"head": ctx.head, "base": ctx.base, "prev": prev_tag(ctx)}.get(kind)
    if not rev:
        return None, ref
    return read_rev(ctx, rev, p), p


def lsdir(ctx, rev, path):
    rc, out = git(ctx, "ls-tree", "--name-only", rev, path.rstrip("/") + "/")
    return [x.rsplit("/", 1)[-1] for x in out.split("\n") if x] if rc == 0 else []


# ---------- розбір md / yaml-схеми ----------
def norm(s):
    return re.sub(r"[`*_]", "", s).strip().lower()


def tables(text):
    out, lines = [], text.split("\n")
    for i in range(len(lines) - 1):
        if lines[i].lstrip().startswith("|") and re.match(r"^\s*\|[\s:|-]+\|?\s*$", lines[i + 1]) and "-" in lines[i + 1]:
            cells = lambda l: [c.strip() for c in l.strip().strip("|").split("|")]
            hdr, rows, j = [norm(c) for c in cells(lines[i])], [], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                r = cells(lines[j])
                rows.append({"cells": r + [""] * (len(hdr) - len(r)), "line": j + 1, "raw": lines[j]})
                j += 1
            out.append({"hdr": hdr, "rows": rows, "line": i + 1})
    return out


def colidx(hdr, aliases):
    for a in aliases:
        for k, h in enumerate(hdr):
            if h == a.lower() or h.startswith(a.lower()):
                return k
    return None


def find_table(text, req):
    for t in tables(text):
        if all(colidx(t["hdr"], al) is not None for al in req):
            return t
    return None


def sections(text):
    """[(рівень, заголовок, текст розділу до наступного заголовка того ж чи вищого рівня, рядок)]"""
    lines, hs = text.split("\n"), []
    for i, l in enumerate(lines):
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", l)
        if m:
            hs.append((len(m.group(1)), m.group(2), i))
    out = []
    for k, (lv, t, i) in enumerate(hs):
        end = len(lines)
        for lv2, _, i2 in hs[k + 1:]:
            if lv2 <= lv:
                end = i2
                break
        out.append((lv, t, "\n".join(lines[i + 1:end]), i + 1))
    return out


def parse_schema(text):
    """answers.yaml схема (answers-schema.md §2): ключі VP-xx, поля з відступом; повертає {vp: {поле: значення}}."""
    res, cur = {}, None
    for l in text.split("\n"):
        if not l.strip() or l.lstrip().startswith("#"):
            continue
        m = re.match(r"^(VP-\d{2,3}):\s*$", l)
        if m:
            cur = res.setdefault(m.group(1), {})
            continue
        m = re.match(r"^\s+([\w]+):\s*(.*?)\s*$", l)
        if m and cur is not None:
            cur[m.group(1)] = scalar(m.group(2))
        elif not re.match(r"^\s", l):
            raise ValueError(f"невідомий рядок схеми: {l[:40]}")
    return res


def scalar(v):
    v = v.strip()
    if v.startswith("[") and v.endswith("]"):
        return [scalar(x) for x in re.split(r",(?![^\[{]*[\]}])", v[1:-1]) if x.strip()]
    if v.startswith("{"):
        return v
    if v in ("true", "false"):
        return v == "true"
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    return v.strip("\"'")


def deprecated(d):
    return bool(d.get("deprecated")) and d.get("deprecated") not in ("false", False)


def glob_match(p, pat):
    if pat.endswith("/"):
        return p.startswith(pat)
    rx = re.escape(pat).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(rx, p) is not None


# ---------- витяг ID ----------
def extract(ctx, spec):
    """повертає (set|None, мітка); None — файл відсутній"""
    text, lab = resolve(ctx, spec["ref"])
    if text is None:
        return None, lab
    drop = re.compile(spec["drop_line_regex"]) if spec.get("drop_line_regex") else None
    if "schema_keys" in spec:
        sch = parse_schema(text)
        want = spec["schema_keys"]
        return {k for k, d in sch.items() if want == "all" or (want == "active") != deprecated(d)}, lab
    if "table_col" in spec:
        ids = set()
        for t in tables(text):
            k = colidx(t["hdr"], spec["table_col"])
            if k is None:
                continue
            for r in t["rows"]:
                if drop and drop.search(r["raw"]):
                    continue
                ids |= set(re.findall(spec["regex"], r["cells"][k]))
        return ids, lab
    if spec.get("section"):
        body = "\n".join(s[2] for s in sections(text) if re.search(spec["section"], s[1]))
        text = body
    ids = set()
    for l in text.split("\n"):
        if drop and drop.search(l):
            continue
        ids |= set(re.findall(spec["regex"], l))
    return ids, lab


def sha_of(ctx, src):
    if src in ("head", "base"):
        return getattr(ctx, src), src
    if src == "prev":
        t = prev_tag(ctx)
        return (git(ctx, "rev-list", "-n1", t)[1].strip() or None, t) if t else (None, "prev")
    ref = src.split("extract:", 1)[1]
    text, lab = resolve(ctx, ref)
    m = SHA_RE.search(text or "")
    return (m.group(2) if m else None), lab


def full(ctx, sha):
    rc, out = git(ctx, "rev-parse", "--verify", "--quiet", sha + "^{commit}")
    return out.strip() if rc == 0 else None


# ---------- примітиви ----------
def p_id_set(ctx, c):
    s = c["args"]
    L, ll = extract(ctx, s["left"])
    R, rl = extract(ctx, s["right"])
    for v, lab in ((L, ll), (R, rl)):
        if v is None:
            return ctx.add(c["id"], "ERROR", f"Немає джерела {lab}: перевірку не виконано", lab)
    miss, extra = sorted(L - R), sorted(R - L)
    bad = []
    if miss:
        bad.append(s.get("msg_missing", "Бракує у правій множині: {ids}").format(ids=", ".join(miss)))
    if s.get("relation") == "equal" and extra:
        bad.append(s.get("msg_extra", "Зайве у правій множині: {ids}").format(ids=", ".join(extra)))
    status = c.get("severity", "FAIL") if bad else "PASS"
    ctx.add(c["id"], status, " ".join(bad), rl, c.get("route_on_fail") if bad else None)


def p_table_rules(ctx, c):
    s = c["args"]
    text, lab = resolve(ctx, s["ref"])
    if text is None:
        return ctx.add(c["id"], "ERROR", f"Немає файлу {lab}", lab)
    t = find_table(text, s["require"])
    if not t:
        return ctx.add(c["id"], "ERROR", f"table-not-found: у {lab} немає таблиці з колонками {[a[0] for a in s['require']]}", lab)
    kc = colidx(t["hdr"], s["key"])
    drop = re.compile(s["drop_row_regex"]) if s.get("drop_row_regex") else None
    bad, seen = [], {}
    for r in t["rows"]:
        if drop and drop.search(r["raw"]):
            continue
        key = r["cells"][kc]
        if s.get("unique_key"):
            if key in seen:
                bad.append(f"{key}: дубль рядка (один трек на AC)")
            seen[key] = 1
        for rule in s["rules"]:
            w = rule.get("when")
            if w:
                k = colidx(t["hdr"], w["col"])
                if k is None or r["cells"][k].strip().lower() not in [x.lower() for x in w["in"]]:
                    continue
            k = colidx(t["hdr"], rule["col"])
            val = "" if k is None else r["cells"][k].strip()
            kind, ok = rule["kind"], True
            if kind == "nonempty":
                ok = bool(val) and not re.fullmatch(r"[-—–]+", val)
            elif kind == "enum":
                ok = val.lower() in [x.lower() for x in rule["values"]]
            elif kind == "regex":
                ok = re.search(rule["pattern"], val) is not None
            if not ok:
                bad.append(f"{key}: {rule['msg']} (зараз «{val[:40]}»)")
    ctx.add(c["id"], "FAIL" if bad else "PASS", "Виправ " + "; ".join(bad) if bad else "", f"{lab}:{t['line']}")


def p_headings(ctx, c):
    s = c["args"]
    text, lab = resolve(ctx, s["ref"])
    if text is None:
        return ctx.add(c["id"], "ERROR", f"Немає файлу {lab}", lab)
    want = list(s.get("headings", []))
    if s.get("headings_from"):
        tpl = os.path.join(PLUGIN, s["headings_from"])
        if not os.path.exists(tpl):
            return ctx.add(c["id"], "ERROR", f"template-missing: немає {s['headings_from']}", s["headings_from"])
        with open(tpl, encoding="utf-8") as f:
            want += [h for lv, h, _, _ in sections(f.read()) if lv == 2 and h not in s.get("exclude", [])]
        if s.get("expect_count") and len(want) != s["expect_count"]:
            return ctx.add(c["id"], "ERROR", f"template-malformed: заголовків {len(want)}, очікувано {s['expect_count']}", s["headings_from"])
    have = [norm(h) for _, h, _, _ in sections(text)]
    miss = [w for w in want if not any((re.search(w[3:], h, re.I) if w.startswith("re:") else norm(w) in h) for h in have)]
    if miss and s.get("or_text") and s["or_text"].lower() in text.lower():
        miss = []
    ctx.add(c["id"], "FAIL" if miss else "PASS", ("Додай заголовки в " + lab + ": " + "; ".join(miss)) if miss else "", lab,
            c.get("route_on_fail") if miss else None)


def p_sha_eq(ctx, c):
    vals, labs = [], []
    for ref in c["args"]["refs"]:
        text, lab = resolve(ctx, ref)
        if text is None:
            return ctx.add(c["id"], "ERROR", f"Немає файлу {lab}", lab)
        m = SHA_RE.search(text)
        labs.append(lab)
        vals.append(m.group(2).lower() if m else None)
    if not any(vals):
        return ctx.add(c["id"], "MANUAL", "Мітку SHA не знайдено в жодному файлі (формат id-patterns.md): звір вручну " + ", ".join(labs))
    if None in vals:
        return ctx.add(c["id"], "FAIL", "Додай мітку «SHA: <коміт>» у " + ", ".join(l for l, v in zip(labs, vals) if v is None), ",".join(labs))
    ok = all(v.startswith(vals[0][:7]) and (v.startswith(vals[0]) or vals[0].startswith(v)) for v in vals)
    ctx.add(c["id"], "PASS" if ok else "FAIL", "" if ok else "SHA різні: " + "; ".join(f"{l}={v[:12]}" for l, v in zip(labs, vals)),
            ",".join(labs), None if ok else c.get("route_on_fail"))


def need_sha(ctx, c, src):
    sha, lab = sha_of(ctx, src)
    if not sha:
        ctx.add(c["id"], "FAIL", f"missing-sha: додай мітку «SHA: <коміт>» у {lab}", lab)
        return None
    if not ensure_obj(ctx, sha) or not full(ctx, sha):
        ctx.add(c["id"], "ERROR", f"git-object-missing: {sha[:12]} немає в репо (fetch повним SHA не допоміг)", lab)
        return None
    return full(ctx, sha)


def p_git_ancestor(ctx, c):
    a, b = need_sha(ctx, c, c["args"]["a"]), None
    if a:
        b = need_sha(ctx, c, c["args"]["b"])
    if not (a and b):
        return
    rc, _ = git(ctx, "merge-base", "--is-ancestor", a, b)
    ctx.add(c["id"], "PASS" if rc == 0 else ("FAIL" if rc == 1 else "ERROR"),
            "" if rc == 0 else c["args"].get("msg", "{a} не є предком {b}").format(a=a[:12], b=b[:12]), f"{a[:12]}..{b[:12]}",
            c.get("route_on_fail") if rc == 1 else None)


def p_git_diff_allowed(ctx, c):
    s = c["args"]
    a = need_sha(ctx, c, s["from"])
    b = need_sha(ctx, c, s["to"]) if a else None
    if not (a and b):
        return
    rc, out = git(ctx, "diff", "--name-only", a, b)
    files = [x for x in out.split("\n") if x]
    extra = [f for f in files if not any(glob_match(f, p) for p in s["allow"])]
    ctx.add(c["id"], "FAIL" if extra else "PASS", ("Зайві файли поза дозволеним переліком: " + ", ".join(extra)) if extra else "",
            f"{a[:12]}..{b[:12]}", c.get("route_on_fail") if extra else None)
    if s.get("compare_done"):
        done = str(ctx.n.get("done", ""))
        lost = [p for p in s["allow"] if p not in done]
        ctx.add(c["id"] + "-spec-vs-naryad", "WARN" if lost else "PASS",
                ("Дозволені файли специфікації не згадано в done наряду: " + ", ".join(lost)) if lost else "", "naryad.done")


def xy(v):
    p = str(v).split(".")
    return f"{p[2]}.{p[3]}" if len(p) >= 4 else (f"{p[0]}.{p[1]}" if len(p) >= 2 else str(v))


def manifest_versions(ctx):
    vals = {}
    for d in lsdir(ctx, ctx.head, "package/addons"):
        if not d.startswith("td_"):
            continue
        t = read_rev(ctx, ctx.head, f"package/addons/{d}/__manifest__.py")
        if t is None:
            vals[d] = None
            continue
        try:
            node = next(n.value for n in ast.parse(t).body if isinstance(n, (ast.Expr, ast.Assign)) and isinstance(n.value, ast.Dict))
            vals[d] = xy(ast.literal_eval(node).get("version", ""))
        except Exception:
            vals[d] = None
    return vals


def p_version_eq(ctx, c):
    vals = {}
    for s in c["args"]["sources"]:
        if s["kind"] == "manifests":
            mv = manifest_versions(ctx)
            if not mv:
                return ctx.add(c["id"], "ERROR", "У package/addons немає td_* з __manifest__.py", "package/addons")
            for d, v in mv.items():
                if v is None:
                    return ctx.add(c["id"], "ERROR", f"Не прочитано version з {d}/__manifest__.py", d)
                vals[f"td-модуль {d}"] = v
        elif s["kind"] == "param":
            if ctx.params.get(s["key"]):
                vals[s["name"]] = xy(ctx.params[s["key"]])
        else:
            text, lab = resolve(ctx, s["ref"])
            if text is None:
                return ctx.add(c["id"], "ERROR", f"Немає файлу {lab}", lab)
            m = re.findall(s["pattern"], text)
            if not m:
                if s.get("optional"):
                    continue
                return ctx.add(c["id"], "ERROR", f"У {lab} не знайдено версію за шаблоном (id-patterns.md)", lab)
            vals[s["name"]] = max(m, key=lambda x: [int(i) for i in x.split(".")]) if s.get("pick") == "max" else m[0]
    ok = len(set(vals.values())) <= 1
    ctx.add(c["id"], "PASS" if ok else "FAIL", "" if ok else "Узгодь версію X.Y: " + "; ".join(f"{k}={v}" for k, v in vals.items()),
            "", None if ok else c.get("route_on_fail"))


def p_exists(ctx, c):
    miss = [p for p in c["args"]["paths"] if not (read_rev(ctx, ctx.head, p) or "").strip()]
    ctx.add(c["id"], "FAIL" if miss else "PASS", ("Створи непорожні файли: " + ", ".join(miss)) if miss else "", ",".join(miss)[:200])


def p_vendored_license(ctx, c):
    bad = [d for d in lsdir(ctx, ctx.head, "package/addons") if not re.match(r"^td_", d)
           and not any(re.match(r"(?i)^(LICENSE|COPYING)", f) for f in lsdir(ctx, ctx.head, f"package/addons/{d}"))]
    ctx.add(c["id"], "FAIL" if bad else "PASS", ("Додай файл ліцензії у вендорені модулі: " + ", ".join(bad)) if bad else "", "package/addons")


def p_addons_in_text(ctx, c):
    text, lab = resolve(ctx, c["args"]["ref"])
    if text is None:
        return ctx.add(c["id"], "ERROR", f"Немає файлу {lab}", lab)
    miss = [d for d in lsdir(ctx, ctx.head, "package/addons") if d not in text]
    ctx.add(c["id"], "FAIL" if miss else "PASS", ("Додай у склад " + lab + " модулі з версією/джерелом: " + ", ".join(miss)) if miss else "", lab)


def p_allocation_coverage(ctx, c):
    text, lab = resolve(ctx, "head:package/ALLOCATION.md")
    chk, cl = resolve(ctx, "head:package/CHECKS.md")
    if text is None or chk is None:
        return ctx.add(c["id"], "ERROR", f"spec-missing: немає {'ALLOCATION.md' if text is None else 'CHECKS.md'} на head", "package/")
    t = find_table(text, [["ac"], ["трек"], ["модуль"]])
    if not t:
        return ctx.add(c["id"], "ERROR", "table-not-found: ALLOCATION.md без колонок AC/трек/модуль", lab)
    tc, mc = colidx(t["hdr"], ["трек"]), colidx(t["hdr"], ["модуль"])
    alloc, need_dir = set(), set()
    for r in t["rows"]:
        mods = {m.strip() for m in r["cells"][mc].split(",") if m.strip()}
        alloc |= mods
        if r["cells"][tc].strip().lower() in ("код", "готове"):
            need_dir |= mods
    dirs = set(lsdir(ctx, ctx.head, "package/addons"))
    cfg = [f for f in lsdir(ctx, ctx.head, "package/config")]
    bad = [f"теки {d} немає в ALLOCATION" for d in sorted(dirs - alloc)] + [f"модуль {m} (код/готове) без теки в package/addons" for m in sorted(need_dir - dirs)]
    bad += [f"файл package/config/{f} не перелічено в CHECKS.md" for f in cfg if f not in chk]
    ctx.add(c["id"], "FAIL" if bad else "PASS", ("Узгодь ALLOCATION, package/addons і package/config: " + "; ".join(bad)) if bad else "", lab,
            c.get("route_on_fail") if bad else None)


def p_grep_clients(ctx, c):
    reg, lab = resolve(ctx, "head:clients/REGISTRY.md")
    t = find_table(reg or "", [["ідентифікатор"]])
    ids = [r["cells"][0] for r in t["rows"]] if t else []
    ids = [i for i in ids if len(i) >= 4 and i != "н/д"]
    if not ids:
        return ctx.add(c["id"], "SKIP", "no-clients: у clients/REGISTRY.md немає ідентифікаторів клієнтів", lab)
    hits = []
    for i in ids:
        rc, out = git(ctx, "grep", "-n", "-I", "-F", "-e", i, ctx.head, "--", "package/")
        hits += [x.split(":", 1)[1].rsplit(":", 1)[0] + ":" + x.split(":")[2] for x in out.split("\n") if x.count(":") >= 3]
    ctx.add(c["id"], "FAIL" if hits else "PASS", ("Прибери ідентифікатори клієнтів з package/: " + ", ".join(sorted(set(hits))[:10])) if hits else "",
            ",".join(sorted(set(hits)))[:200])


def p_section_contains(ctx, c):
    s = c["args"]
    text, lab = resolve(ctx, s["ref"])
    if text is None:
        return ctx.add(c["id"], "ERROR", f"Немає файлу {lab}", lab)
    body = "\n".join(x[2] for x in sections(text) if re.search(s["heading"], x[1], re.I))
    miss = [p for p in s["patterns"] if not re.search(p, body, re.I)]
    ctx.add(c["id"], "FAIL" if miss else "PASS", ("Доповни розділ «" + s["heading_name"] + "»: " + "; ".join(s["names"][s["patterns"].index(p)] for p in miss)) if miss else "", lab)


def keyset_blocks(text):
    sch = parse_schema(text)
    return sch


def p_keys_diff_eq(ctx, c):
    s = c["args"]
    if not prev_tag(ctx):
        return ctx.add(c["id"], "SKIP", "first-release: попереднього тега package/vX.Y немає")
    new, nl = resolve(ctx, "head:" + s["file"])
    old, ol = resolve(ctx, "prev:" + s["file"])
    log, ll = resolve(ctx, "head:" + s["changelog"])
    if None in (new, old, log):
        return ctx.add(c["id"], "ERROR", "Немає файлу для diff ключів (head/prev/CHANGELOG)", s["file"])
    try:
        a, b = parse_schema(old), parse_schema(new)
    except ValueError as e:
        return ctx.add(c["id"], "ERROR", f"schema-parse: {e}", s["file"])
    ch = {k for k in b if k not in a} | {k for k in b if deprecated(b[k]) and k in a and not deprecated(a[k])}
    body = "\n".join(x[2] for x in sections(log) if re.search(s["heading"], x[1], re.I))
    listed = set(re.findall(r"VP-\d{2,3}", body))
    d1, d2 = sorted(ch - listed), sorted(listed - ch)
    bad = ([f"додай у «Зміни анкети» {', '.join(d1)}"] if d1 else []) + ([f"прибери з «Зміни анкети» {', '.join(d2)} (немає в diff ключів)"] if d2 else [])
    ctx.add(c["id"], "FAIL" if bad else "PASS", "Виправ CHANGELOG: " + "; ".join(bad) if bad else "", ll)


def p_stable_on_rerun(ctx, c):
    s = c["args"]
    if not prev_tag(ctx):
        return ctx.add(c["id"], "SKIP", "first-release: попереднього тега package/vX.Y немає")
    new, nl = resolve(ctx, "head:" + s["file"])
    old, ol = resolve(ctx, "prev:" + s["file"])
    allow, al = extract(ctx, s["allowed"])
    if None in (new, old) or allow is None:
        return ctx.add(c["id"], "ERROR", "Немає файлу для порівняння з попереднім тегом", s["file"])

    def blocks(text):
        if s["kind"] == "table":
            t = find_table(text, s["require"])
            return {r["cells"][colidx(t["hdr"], s["key"])]: r["raw"].strip() for r in t["rows"]} if t else {}
        out, cur = {}, None
        for l in text.split("\n"):
            m = re.match(r"^(VP-\d{2,3}):", l)
            if m:
                cur = m.group(1)
                out[cur] = ""
            elif cur and l.strip() and not l.lstrip().startswith("#"):
                out[cur] += l.strip() + "\n"
        return out
    a, b = blocks(old), blocks(new)
    changed = {k for k in a if k in b and a[k] != b[k]}
    bad = sorted(changed - allow)
    ctx.add(c["id"], "FAIL" if bad else "PASS", ("Поверни без змін (немає в «Зміни версії»): " + ", ".join(bad)) if bad else "", nl)


def p_example_valid(ctx, c):
    sch_t, sl = resolve(ctx, "head:package/templates/answers.yaml")
    ex_t, el = resolve(ctx, "head:package/templates/answers.example.yaml")
    if sch_t is None or ex_t is None:
        return ctx.add(c["id"], "ERROR", "Немає answers.yaml або answers.example.yaml", "package/templates/")
    try:
        sch = parse_schema(sch_t)
    except ValueError as e:
        return ctx.add(c["id"], "ERROR", f"schema-parse: {e}", sl)
    ex = {}
    for l in ex_t.split("\n"):
        m = re.match(r"^(VP-\d{2,3}):\s*(.*)$", l)
        if m:
            ex[m.group(1)] = scalar(m.group(2))
    bad = []
    if not re.search(r"(?m)^#\s*schema:\s*1\b", sch_t):
        bad.append("додай коментар «# schema: 1» у шапку схеми")
    act = {k for k, d in sch.items() if not deprecated(d)}
    for k in sorted(act - set(ex)):
        bad.append(f"додай {k} в example")
    for k in sorted(set(ex) - act):
        bad.append(f"прибери {k} з example (немає в схемі або deprecated)")
    for k in sorted(act & set(ex)):
        d, v = sch[k], ex[k]
        if v != d.get("default"):
            bad.append(f"{k}: значення example ≠ default схеми")
        if d.get("type") == "enum" and v not in (d.get("allowed") or []):
            bad.append(f"{k}: значення поза allowed")
        if d.get("type") == "int" and not (isinstance(v, int) and d.get("min", v) <= v <= d.get("max", v)):
            bad.append(f"{k}: int поза min..max")
        if str(v) == "уточнити":
            bad.append(f"{k}: «уточнити» заборонено")
    ctx.add(c["id"], "FAIL" if bad else "PASS", "Виправ answers.example.yaml/схему: " + "; ".join(bad) if bad else "", el)


def p_signature_by_ai(ctx, c):
    s = c["args"]
    text, lab = resolve(ctx, "head:" + s["file"])
    if text is None:
        return ctx.add(c["id"], "ERROR", f"Немає файлу {lab}", lab)
    sec = "\n".join(x[2] for x in sections(text) if re.search(s["heading"], x[1], re.I))
    if not sec.strip():
        return ctx.add(c["id"], "MANUAL", f"У {lab} не знайдено блок підпису/рішення людини: перевір вручну, що AI його не заповнив")
    old = "\n".join(x[2] for x in sections(read_rev(ctx, ctx.base, s["file"]) or "") if re.search(s["heading"], x[1], re.I))
    if old == sec:
        return ctx.add(c["id"], "PASS", "", lab)
    if not ctx.agent_pattern:
        return ctx.add(c["id"], "MANUAL", "Блок підпису змінено; автора-агента не визначено (--agent-pattern не задано): перевір, що змінив людина", lab)
    rc, out = git(ctx, "log", f"{ctx.base}..{ctx.head}", "--format=%an <%ae>", "--", s["file"])
    ag = [x for x in out.split("\n") if x and re.search(ctx.agent_pattern, x)]
    ctx.add(c["id"], "FAIL" if ag else "PASS", "Поверни поля підпису/рішення людині: їх змінив коміт агента" if ag else "", lab)


def p_evals_schema(ctx, c):
    """кожен evals/**/evals.json на head: валідний JSON, обов'язкові поля (evals-format.md)"""
    rc, out = git(ctx, "ls-tree", "-r", "--name-only", ctx.head, "evals/")
    files = [x for x in out.split("\n") if x.endswith("/evals.json")] if rc == 0 else []
    if not files:
        return ctx.add(c["id"], "FAIL", "Немає жодного evals/**/evals.json на head", "evals/")
    bad, ids_rx = [], re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    for f in files:
        try:
            d = json.loads(read_rev(ctx, ctx.head, f) or "")
            assert isinstance(d, dict) and d.get("skill") and isinstance(d.get("cases"), list)
            seen = set()
            for k in d["cases"]:
                assert ids_rx.match(k.get("id", "")) and k["id"] not in seen
                seen.add(k["id"])
                assert k.get("source") and k.get("status") and k.get("prompt")
                e = k.get("expected") or {}
                assert e.get("checks") and e.get("must_not")
        except Exception as ex:
            bad.append(f"{f} ({type(ex).__name__})")
    ctx.add(c["id"], "FAIL" if bad else "PASS", ("Невалідна схема: " + "; ".join(bad[:8])) if bad else "", ",".join(files)[:200])


def p_pii_strict(ctx, c):
    """PII у доданих рядках diff за шляхами args.paths: FAIL незалежно від client_data (pii-patterns.md)"""
    rc, diff = git(ctx, "diff", "-U0", ctx.base, ctx.head, "--", *c["args"]["paths"])
    hits, path, ln = [], "", 0
    for l in diff.split("\n"):
        if l.startswith("+++ "):
            path = l[6:]
        elif l.startswith("@@"):
            m = re.search(r"\+(\d+)", l)
            ln = int(m.group(1)) - 1 if m else 0
        elif l.startswith("+") and not l.startswith("+++"):
            ln += 1
            hits += [(n, f"{path}:{ln}") for n, rx, st in PII if st == "FAIL" and rx.search(l)]
    ctx.add(c["id"], "FAIL" if hits else "PASS", ("Прибери/знеособ ПДн (значення не наводимо): " + "; ".join(f"{n} {e}" for n, e in hits[:8])) if hits else "", ",".join(e for _, e in hits)[:200])


def p_manual(ctx, c):
    ctx.add(c["id"], "MANUAL", c["args"]["text"] + f" ({c['args']['who']})")


PRIMS = {k[2:]: v for k, v in globals().items() if k.startswith("p_")}


# ---------- загальні перевірки C-06 ----------
def where_paths(ctx):
    return [w.strip() for w in re.split(r"\s+\+\s+|,\s*", str(ctx.n.get("where", ""))) if w.strip()]


def changed_files(ctx):
    return [x for x in git(ctx, "diff", "--name-only", ctx.base, ctx.head)[1].split("\n") if x]


def generic(ctx, extra_allowed):
    wh = where_paths(ctx)
    bad = [w for w in wh if w.startswith("/") or ".." in w.split("/")]
    if bad:
        ctx.add("path-outside-repo", "FAIL", "Шлях вийшов за межі репо: " + ", ".join(bad))
        return
    ph = [w for w in wh if re.search(r"<[^>]+>", w)]
    if ph:
        ctx.add("path-placeholder", "FAIL", "Непідставлений плейсхолдер у where: " + ", ".join(ph))
        return
    allowed = wh + ["observations/"] + list(extra_allowed or [])
    extra = [f for f in changed_files(ctx) if not any(glob_match(f, a) or f == a.rstrip("/") for a in allowed)]
    ctx.add("where-only", "FAIL" if extra else "PASS", ("Прибери зміни поза where: " + ", ".join(extra)) if extra else "", f"{ctx.base[:8]}..{ctx.head[:8]}")
    miss = []
    for w in wh:
        if w.endswith("/"):
            if not lsdir(ctx, ctx.head, w):
                miss.append(w)
        elif not (read_rev(ctx, ctx.head, w) or "").strip():
            miss.append(w)
    ctx.add("where-exists", "FAIL" if miss else "PASS", ("Створи непорожні: " + ", ".join(miss)) if miss else "", ",".join(miss))
    tpl = str(ctx.n.get("template", ""))
    files = [w for w in wh if w.endswith(".md")]
    if not tpl or tpl.lower().startswith("немає") or len(files) != 1:
        ctx.add("template-headings", "SKIP" if not files else "MANUAL", "Шаблону файлом немає або where не один .md: форму перевіряє людина")
    else:
        template_headings(ctx, "template-headings", tpl, files[0])
    pii(ctx, wh)
    hint = []
    for f in files:
        t = read_rev(ctx, ctx.head, f) or ""
        hint += [f"{f}:{ln}" for lv, h, body, ln in sections(t) if lv == 2 and not re.search(r"AC-|VP-|ТР|SPEC|https?://", body)]
    ctx.add("sources-hint", "WARN" if hint else "PASS", ("Додай посилання на джерело в розділи: " + ", ".join(hint[:8])) if hint else "")


def template_headings(ctx, cid, tpl, res):
    t = read_rev(ctx, ctx.base, tpl) or read_rev(ctx, ctx.head, tpl)
    r = read_rev(ctx, ctx.head, res)
    if t is None or r is None:
        return ctx.add(cid, "ERROR", f"template-missing: немає {tpl if t is None else res} на SHA", tpl)
    have = [norm(h) for _, h, _, _ in sections(r)]
    miss = []
    for _, h, _, _ in sections(t):
        rx = "^" + re.sub(r"\\<[^>]*\\>", ".+", re.escape(norm(h))) + "$"
        if not any(re.search(rx, x) for x in have):
            miss.append(h)
    ctx.add(cid, "FAIL" if miss else "PASS", ("Додай заголовки шаблону в " + res + ": " + "; ".join(miss)) if miss else "", res)


def pii(ctx, wh):
    cd = ctx.n.get("client_data", "none")
    rc, diff = git(ctx, "diff", "-U0", ctx.base, ctx.head, "--", *[w for w in wh if not w.startswith("/")])
    reg = resolve(ctx, "head:clients/REGISTRY.md")[0] or ""
    t = find_table(reg, [["ідентифікатор"]])
    ids = [r["cells"][0] for r in t["rows"] if len(r["cells"][0]) >= 4 and r["cells"][0] != "н/д"] if t else []
    hits, path, ln = [], "", 0
    for l in diff.split("\n"):
        if l.startswith("+++ "):
            path = l[6:]
        elif l.startswith("@@"):
            m = re.search(r"\+(\d+)", l)
            ln = int(m.group(1)) - 1 if m else 0
        elif l.startswith("+") and not l.startswith("+++"):
            ln += 1
            for name, rx, st in PII:
                if rx.search(l):
                    hits.append((name, "FAIL" if (cd != "none" and st == "FAIL") else "WARN", f"{path}:{ln}"))
            if any(i in l for i in ids):
                hits.append(("client-id", "FAIL", f"{path}:{ln}"))
    fails = [h for h in hits if h[1] == "FAIL"]
    st = "FAIL" if fails else ("WARN" if hits else "PASS")
    msg = ("Прибери/знеособ ПДн (значення не наводимо): " + "; ".join(f"{n} {e}" for n, _, e in (fails or hits)[:8])) if hits else ""
    ctx.add("no-pii", st, msg, ",".join(e for _, _, e in hits)[:200])


# ---------- режим inputs ----------
def inputs_mode(ctx):
    n = ctx.n
    base_branch = (n.get("repo") or {}).get("base_branch", "main")
    reg, lab = resolve(ctx, "base:flow/ARTIFACTS.md")
    t = find_table(reg or "", [["крок", "step", "код"], ["where", "шлях", "де"], ["умова", "condition"]]) if reg else None
    if not t:
        return ctx.add("artifacts-registry", "ERROR", "Немає flow/ARTIFACTS.md на SHA бази або в ньому нема колонок крок/where/умова", "flow/ARTIFACTS.md")
    sc, wc, cc = (colidx(t["hdr"], a) for a in (["крок", "step", "код"], ["where", "шлях", "де"], ["умова", "condition"]))
    uc = colidx(t["hdr"], ["споживач", "consumer", "для кроку"])
    reg_rows = {r["cells"][sc].strip(): r for r in t["rows"]}
    if not ensure_obj(ctx, ctx.base):
        return ctx.add("base-sha", "ERROR", "SHA бази не знайдено в репо", str(ctx.base))
    seen = set()
    for i in n.get("inputs") or []:
        nm, fr, path, sha = i.get("name", "?"), i.get("from", ""), i.get("path", ""), i.get("sha") or ""
        seen.add(fr)
        if not re.match(r"^[A-D]-\d{2}[a-d]?$", fr):
            ctx.add(f"input:{nm}", "SKIP", "external: перевіряє викликач за DATA_POLICY", nm)
            continue
        row = reg_rows.get(fr)
        cond = i.get("condition") or (row["cells"][cc] if row else "")
        if cond.strip() and re.search(r"(?i)повтор", cond) and not (n.get("attempt", 1) > 1 or n.get("returned_from")):
            ctx.add(f"input:{nm}", "SKIP", f"conditional: {cond[:60]}", nm)
            continue
        bad = []
        if row and row["cells"][wc].strip() != path:
            bad.append(("input-path", f"Виправ шлях входу {nm}: «{path}» ≠ where {fr}: «{row['cells'][wc].strip()}»"))
        if not sha:
            bad.append(("input-no-sha", f"Додай sha входу {nm}"))
        else:
            if not ensure_obj(ctx, sha):
                bad.append(("input-missing", f"Коміт {sha[:12]} входу {nm} відсутній у репо"))
            elif git(ctx, "rev-parse", "--verify", "--quiet", f"{sha}:{path.rstrip('/')}")[0] != 0:
                bad.append(("input-missing", f"Файл {path} відсутній на {sha[:12]}"))
            elif git(ctx, "merge-base", "--is-ancestor", sha, ctx.base)[0] != 0:
                bad.append(("input-unmerged", f"Вхід {nm}: {sha[:12]} не злито в origin/{base_branch} (на SHA бази)"))
        for cid, msg in bad:
            ctx.add(cid, "FAIL", msg, f"{path}@{sha[:8]}")
        if not bad:
            ctx.add(f"input:{nm}", "PASS", "", path)
    if uc is not None:
        for fr, row in reg_rows.items():
            if n.get("step") in re.findall(r"[A-D]-\d{2}[a-d]?", row["cells"][uc]) and fr not in seen:
                if row["cells"][cc].strip():
                    ctx.add("input-absent", "SKIP", f"conditional: вхід від {fr} умовний ({row['cells'][cc][:40]})")
                else:
                    ctx.add("input-absent", "FAIL", f"Додай вхід від {fr} ({row['cells'][wc]}) у наряд")


# ---------- специфікації ----------
def load_spec(step):
    p = os.path.join(SKILL, "references", "checks", f"{step}.yaml")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.loads("".join(l for l in f if not l.lstrip().startswith("#")))


def when_ok(ctx, w):
    if not w:
        return True, ""
    hot = ctx.params.get("mode") == "hotfix" or ctx.params.get("hotfix")
    tests = {"prev": (bool(prev_tag(ctx)), "first-release"), "hotfix": (hot, "не hotfix"), "not_hotfix": (not hot, "hotfix"),
             "rerun": (ctx.n.get("attempt", 1) > 1 or bool(ctx.n.get("returned_from")), "перший запуск"),
             "new_version": (ctx.params.get("mode") == "нова-версія", "режим не «нова-версія»")}
    if w.startswith("mode:"):
        vals = w[5:].split("|")
        return ctx.params.get("mode") in vals, f"режим не з {{{', '.join(vals)}}}"
    if w.startswith("in:"):
        ok = any(i.get("from") == w[3:] for i in ctx.n.get("inputs") or [])
        return ok, f"немає входу {w[3:]}"
    ok, why = tests[w]
    return ok, why


def run_spec(ctx, spec, only):
    for c in spec["checks"]:
        if only and c["id"] != only:
            continue
        ok, why = when_ok(ctx, c.get("when"))
        if not ok:
            ctx.add(c["id"], "SKIP", why)
            continue
        PRIMS[c["prim"]](ctx, c)


def split_how(how):
    return [s.strip() for s in re.split(r"(?<=[.;])\s+|\n", str(how or "")) if len(s.strip()) > 3]


def load_naryad(path):
    t = open(path, encoding="utf-8").read()
    try:
        return json.loads(t)
    except ValueError:
        pass
    try:
        import yaml
        return yaml.safe_load(t)
    except ImportError:
        return None


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="result", choices=["inputs", "result", "form"])
    ap.add_argument("--naryad")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base")
    ap.add_argument("--head")
    ap.add_argument("--only")
    ap.add_argument("--out")
    ap.add_argument("--agent-pattern", dest="agent_pattern")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    n = load_naryad(a.naryad)
    if n is None:
        msg = "no-yaml-parser: передай наряд як JSON або встанови PyYAML"
        js = {"mode": a.mode, "step": "?", "scope": "/x", "base_sha": None, "head_sha": None, "spec_version": "?", "verdict": "INCOMPLETE",
              "checks": [{"id": "no-yaml-parser", "status": "ERROR", "msg": msg, "evidence": "", "route_on_fail": None}]}
        if a.out:
            os.makedirs(a.out, exist_ok=True)
            open(os.path.join(a.out, "unknown-x-1.json"), "w", encoding="utf-8").write(json.dumps(js, ensure_ascii=False, indent=1))
        print("ERROR " + msg)
        print("verdict=INCOMPLETE FAIL=0 ERROR=1 MANUAL=0 out=" + (a.out or "-"))
        return 2
    ctx = Ctx(a, n)
    step = n.get("step", "?")
    need = ["step", "scope", "inputs", "repo"] + (["where", "template", "attempt"] if a.mode == "result" else [])
    miss = [k for k in need if k not in n]
    if miss:
        ctx.add("naryad-incomplete", "ERROR", "У наряді немає ключів: " + ", ".join(miss))
    else:
        br = (n.get("repo") or {}).get("branch")
        if not ctx.head and br:
            ctx.head = git(ctx, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{br}")[1].strip() or git(ctx, "rev-parse", "--verify", "--quiet", f"refs/heads/{br}")[1].strip() or None
        if not ctx.base and ctx.head:
            ctx.base = git(ctx, "merge-base", ctx.head, "origin/" + (n.get("repo") or {}).get("base_branch", "main"))[1].strip() or None
        if a.mode == "inputs":
            ctx.base = ctx.base or git(ctx, "rev-parse", "origin/" + (n.get("repo") or {}).get("base_branch", "main"))[1].strip()
        if not ctx.base or (a.mode != "inputs" and not ctx.head):
            ctx.add("naryad-incomplete", "ERROR", "Не визначено SHA: передай --base/--head або git.base/git.head у наряді")
        elif a.mode == "inputs":
            inputs_mode(ctx)
        else:
            if not (ensure_obj(ctx, ctx.base) and ensure_obj(ctx, ctx.head)):
                ctx.add("git-object-missing", "ERROR", "base/head відсутні в репо після fetch")
            else:
                spec = load_spec(step) if a.mode == "result" else load_spec(step if step.startswith("C-05") else "C-05" if "DATA_POLICY" in str(n.get("where")) else "form")
                if a.mode == "result":
                    if not a.only or a.only.startswith(("where", "template", "no-pii", "sources", "path")):
                        generic(ctx, (spec or {}).get("extra_allowed"))
                    if spec:
                        run_spec(ctx, spec, a.only)
                    else:
                        ctx.add("spec-missing", "ERROR", f"Немає references/checks/{step}.yaml: специфікацію кроку має створити AI-інженер")
                        for k, s in enumerate(split_how((n.get("check") or {}).get("how"))):
                            ctx.add(f"check-how-{k + 1}", "MANUAL", s)
                else:
                    form_mode(ctx, spec)
                    if ctx.rows and all(r["status"] == "MANUAL" for r in ctx.rows):
                        ctx.add("template-missing", "ERROR", "Жодної автоматичної перевірки форми не виконано (немає шаблону й блоку підпису): форму перевіряє людина")
    return finish(ctx, a, step)


def form_mode(ctx, spec):
    if spec:
        return run_spec(ctx, spec, None)
    wh = [w for w in where_paths(ctx) if w.endswith(".md")]
    tpl = str(ctx.n.get("template", ""))
    if len(wh) == 1 and tpl and not tpl.lower().startswith("немає"):
        template_headings(ctx, "template-headings", tpl, wh[0])
    else:
        ctx.add("template-headings", "MANUAL", "Шаблон або один .md у where не задано: форму перевіряє людина")
    if wh:
        p_signature_by_ai(ctx, {"id": "signature-by-ai", "args": {"file": wh[0], "heading": "(?i)підпис|рішення|затверд"}})


def finish(ctx, a, step):
    rows = sorted(ctx.rows, key=lambda r: ORDER.index(r["status"]))
    st = {r["status"] for r in rows}
    verdict = "FAIL" if "FAIL" in st else ("INCOMPLETE" if "ERROR" in st else "PASS")
    ver = "?"
    try:
        ver = json.load(open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json")))["version"]
    except Exception:
        pass
    scope = (ctx.n.get("scope") or {}).get("id", "x")
    js = {"mode": ctx.mode, "step": step, "scope": f"{(ctx.n.get('scope') or {}).get('kind', '')}/{scope}", "base_sha": ctx.base, "head_sha": ctx.head,
          "prev_tag": prev_tag(ctx) if ctx.head else None, "spec_version": ver, "verdict": verdict, "checks": rows}
    md = ["| ID | Статус | Помилка (для повтору) | Повернення |", "|---|---|---|---|"]
    md += [f"| {r['id']} | {r['status']} | {r['msg'].replace('|', '/')} | {('пропозиція, рішення — людина: ' + r['route_on_fail']) if r['route_on_fail'] else ''} |" for r in rows]
    man = [r["msg"] for r in rows if r["status"] == "MANUAL"]
    if man:
        md += ["", "Для чек-листа гейта:"] + [f"- {m}" for m in man]
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        stem = os.path.join(a.out, f"{step}-{scope}-{ctx.n.get('attempt', 1)}")
        open(stem + ".json", "w", encoding="utf-8").write(json.dumps(js, ensure_ascii=False, indent=1))
        open(stem + ".md", "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"verdict={verdict} FAIL={sum(r['status'] == 'FAIL' for r in rows)} ERROR={sum(r['status'] == 'ERROR' for r in rows)} "
          f"MANUAL={sum(r['status'] == 'MANUAL' for r in rows)} out={a.out or '-'}")
    if not a.out:
        print("\n".join(md))
    return {"PASS": 0, "FAIL": 1, "INCOMPLETE": 2}[verdict]


def selftest():
    assert glob_match("package/addons/td_x/a.py", "package/addons/**") and not glob_match("package/SPEC.md", "package/demo/**")
    assert xy("19.0.1.2") == "1.2"
    sch = parse_schema("# schema: 1\nVP-01:\n  param: A\n  type: enum\n  allowed: [a, b]\n  default: a\n  deprecated: false\nVP-02:\n  deprecated: \"з версії 1.1\"\n")
    assert sch["VP-01"]["allowed"] == ["a", "b"] and not deprecated(sch["VP-01"]) and deprecated(sch["VP-02"])
    t = tables("| AC | трек |\n|---|---|\n| AC-01 | конфіг |\n")[0]
    assert t["rows"][0]["cells"] == ["AC-01", "конфіг"] and colidx(t["hdr"], ["ac"]) == 0
    assert SHA_RE.search("SHA: abc1234").group(2) == "abc1234"
    fx = os.path.join(SKILL, "evals", "fixtures")
    for case, want in (("a10-coverage", 1), ("spec-missing", 2)):
        mk = os.path.join(fx, case, "make_repo.sh")
        if not os.path.exists(mk):
            continue
        d = tempfile.mkdtemp()
        subprocess.run(["bash", mk, d], check=True, capture_output=True)
        rc = main(["--mode", "result", "--naryad", os.path.join(d, "naryad.json"), "--repo", os.path.join(d, "repo"), "--out", os.path.join(d, "out")])
        assert rc == want, f"{case}: код {rc}, очікувано {want}"
    print("selftest OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
