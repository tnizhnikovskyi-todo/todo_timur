#!/usr/bin/env python3
"""check_data_model.py <addons_dir> --plan <PLAN.md>
Зворотна перевірка стандарту (урок §23, A-21): модель даних зрізу проти таблиці «Модель даних» у PLAN.md.
DM-table: FAIL — кожен `_name = 'td.*'` і кожне нове поле в класах з `_inherit` стандартної моделі мусить бути рядком таблиці
          «Модель даних» PLAN.md (заголовок із «Стандартний аналог» і/або «Чому не стандарт») з непорожньою хоча б однією
          з цих колонок («—», «-», «немає», «n/a» вважаються порожніми). Збіг ТОЧНИЙ: токен першої клітинки рядка
          ([a-z0-9_.]+, без бектиків) дорівнює імені моделі або `<база>.<поле>`. «Чому не стандарт» зі словами
          «борг», «A-11», «зробимо пізніше», «пізніше в …», «тимчасово», «тимчасове рішення», маркер TODO (великими, окреме слово; «ToDo-готовий» — не маркер) в будь-якій з двох колонок — FAIL (це не причина). Нова модель з `_name` не на `td.` і без збігу з `_inherit` — FAIL «модель поза простором td.». Клас з `_inherit` власної `td.*`-моделі
          без `_name` не вимагає рядків для полів. Не знайдено жодного .py — FAIL (перевір шлях).
DM-dup:   WARN (евристика, лише WARN) — (а) нова td_-модель з Many2one на res.partner/product.* і полем Date/Datetime та
          Many2one на sale.order*/mrp.production/mrp.workorder/mrp.bom/stock.picking/stock.move; (б) нове поле БЕЗ compute=/related=
          у класі з `_inherit` документа з DOC_PREFIXES (sale.order*, mrp.*, stock.picking/move): Many2one на res.partner/product.* або Date/Datetime
          (ручний ввід даних стандартного модуля в td_-полі). WARN → письмове рішення Архітектора (checks[]/memo); без нього — FAIL.
Вихід: JSON [{id,status,msg}], код 1 при FAIL. Файли Python шукаються в <addons_dir>/**/*.py (без tests, __init__, __manifest__)."""
import sys, json, re, os, glob, ast

USAGE = "usage: check_data_model.py <addons_dir> --plan <PLAN.md>"
DEBT = re.compile(r"борг|a-11|а-11|зробимо пізніше|пізніше в\b|тимчасово|тимчасове рішення", re.I)
DEBT_TODO = re.compile(r"(?<![A-Za-z])TODO(?![-A-Za-zА-Яа-яІіЇїЄє])")
MIXIN_RE = re.compile(r"^(mail\.|portal\.mixin|utm\.mixin|rating\.mixin|image\.mixin|avatar\.mixin|website\.|format\.address\.mixin)")


def debt_word(*cells):
    for c in cells:
        m = DEBT.search(c) or DEBT_TODO.search(c)
        if m:
            return m.group(0)
    return None
DOC_PREFIXES = ("sale.order", "mrp.production", "mrp.workorder", "mrp.bom", "stock.picking", "stock.move")
EMPTY = {"", "-", "—", "–", "немає", "нема", "n/a", "na", "тбд", "tbd"}
FIELD_RE = re.compile(r"^(Many2one|One2many|Many2many|Char|Text|Html|Integer|Float|Monetary|Boolean|Date|Datetime|Selection|Binary|Image|Reference|Json)$")


def fail(id_, msg):
    print(json.dumps([{"id": id_, "status": "FAIL", "msg": msg}], ensure_ascii=False))
    return 1


def parse_plan(path):
    """-> list of (tokens:set, analog:str, why:str) для рядків таблиць із колонкою аналога/причини."""
    rows = []
    ia = iw = None
    in_table = False
    for line in open(path, encoding="utf-8").read().splitlines():
        s = line.strip()
        if not s.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        low = [c.lower() for c in cells]
        if any("стандартний аналог" in c or "чому не стандарт" in c for c in low):
            ia = next((i for i, c in enumerate(low) if "стандартний аналог" in c), None)
            iw = next((i for i, c in enumerate(low) if "чому не стандарт" in c), None)
            in_table = True
            continue
        if not in_table or all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue
        toks = set(re.findall(r"[a-z0-9_.]+", cells[0].replace("`", "").lower())) if cells else set()
        toks = {t.strip(".") for t in toks}
        get = lambda i: cells[i] if i is not None and i < len(cells) else ""
        rows.append((toks, get(ia), get(iw)))
    return rows


def blank(v):
    return re.sub(r"[`*_ ]", "", v).lower() in EMPTY


def const_str(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


def analyze(py, base):
    """-> list of model dicts {name, inherit, fields[{name,type,comodel,computed}], file}"""
    try:
        tree = ast.parse(open(py, encoding="utf-8").read())
    except Exception:
        return []
    out = []
    for c in [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]:
        name = inherit = None
        inh_all = []
        fields = []
        for st in c.body:
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
                t, val = st.targets[0].id, st.value
            elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
                t, val = st.target.id, st.value
            else:
                continue
            if t == "_name":
                name = const_str(val)
            elif t == "_inherit":
                inherit = const_str(val)
                if inherit is None and isinstance(val, (ast.List, ast.Tuple)):
                    inh_all = [x for x in (const_str(e) for e in val.elts) if x]
                    inherit = next((x for x in inh_all if not MIXIN_RE.match(x)), inh_all[0] if inh_all else None)
                elif inherit:
                    inh_all = [inherit]
            elif isinstance(val, ast.Call) and (
                    (isinstance(val.func, ast.Attribute) and FIELD_RE.match(val.func.attr))
                    or (isinstance(val.func, ast.Name) and FIELD_RE.match(val.func.id))):
                ft = val.func.attr if isinstance(val.func, ast.Attribute) else val.func.id
                com = const_str(val.args[0]) if val.args and ft in ("Many2one", "One2many", "Many2many") else None
                computed = False
                for kw in val.keywords:
                    if kw.arg == "comodel_name":
                        com = const_str(kw.value)
                    if kw.arg in ("compute", "related"):
                        computed = True
                fields.append({"name": t, "type": ft, "comodel": com, "computed": computed})
        if name or inherit:
            out.append({"name": name, "inherit": inherit, "inherit_all": inh_all, "fields": fields, "file": os.path.relpath(py, base)})
    return out


def main(argv):
    if not argv or argv[0].startswith("--"):
        return fail("DM-args", f"не задано каталог addons; {USAGE}")
    d = argv[0]; plan = None
    if "--plan" in argv:
        i = argv.index("--plan")
        plan = argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else None
    if not plan or not os.path.isfile(plan):
        return fail("DM-args", f"--plan не задано або файл відсутній; {USAGE}")
    if not os.path.isdir(d):
        return fail("DM-args", f"немає каталогу {d}")
    files = sorted(glob.glob(os.path.join(d, "**", "*.py"), recursive=True))
    files = [f for f in files if "/tests/" not in f and not f.endswith("__manifest__.py") and not f.endswith("__init__.py")]
    models = [m for f in files for m in analyze(f, d)]
    rows = parse_plan(plan)
    table_missing = not rows

    def covered(model, field=None):
        """None — немає рядка; 'debt' — причина-«борг»; False — порожньо; True — є."""
        key = model.lower() if field is None else f"{model}.{field}".lower()
        hit = [r for r in rows if key in r[0]]
        if not hit:
            return None
        w = next((debt_word(r[1], r[2]) for r in hit if debt_word(r[1], r[2])), None)
        if w:
            return "debt:" + w
        return any(not blank(r[1]) or not blank(r[2]) for r in hit)

    if not files:
        return fail("DM-table", f"у {d} не знайдено жодного .py — перевір шлях до addons")
    miss, empty, debt, foreign, td_models, n_checked = [], [], [], [], [], 0
    for m in models:
        if m["name"] and m["name"].startswith("td."):
            n_checked += 1
            td_models.append(m)
            r = covered(m["name"])
            if r is None: miss.append(f"модель {m['name']} ({m['file']})")
            elif isinstance(r, str): debt.append(f"модель {m['name']} (знайдено «{r[5:]}»)")
            elif not r: empty.append(f"модель {m['name']}")
        elif m["name"] and m["name"] != m["inherit"]:
            n_checked += 1
            foreign.append(f"{m['name']} ({m['file']})")
        elif m["inherit"] and not m["inherit"].startswith("td.") and m["fields"]:
            base = m["inherit"]
            for f in m["fields"]:
                n_checked += 1
                r = covered(base, f["name"])
                if r is None: miss.append(f"поле {base}.{f['name']} ({m['file']})")
                elif isinstance(r, str): debt.append(f"поле {base}.{f['name']} (знайдено «{r[5:]}»)")
                elif not r: empty.append(f"поле {base}.{f['name']}")
    if n_checked and table_missing:
        dm = {"id": "DM-table", "status": "FAIL", "msg": f"у {plan} немає таблиці «Модель даних» з колонками «Стандартний аналог»/«Чому не стандарт»; нових td_-моделей і полів: {n_checked}"}
    elif miss or empty or debt or foreign:
        parts = []
        if foreign: parts.append("модель поза простором td.: " + "; ".join(foreign[:12]))
        if miss: parts.append("немає в таблиці «Модель даних»: " + "; ".join(miss[:12]))
        if empty: parts.append("порожній «Стандартний аналог»/«Чому не стандарт»: " + "; ".join(empty[:12]))
        if debt: parts.append("«Стандартний аналог»/«Чому не стандарт» — борг/відкладено, це не причина: " + "; ".join(debt[:12]))
        dm = {"id": "DM-table", "status": "FAIL", "msg": " | ".join(parts)}
    elif not models:
        dm = {"id": "DM-table", "status": "WARN", "msg": "моделей (_name/_inherit) не знайдено в .py — перевір шлях до addons"}
    elif not n_checked:
        dm = {"id": "DM-table", "status": "PASS", "msg": "нових td_-моделей і полів у _inherit немає"}
    else:
        dm = {"id": "DM-table", "status": "PASS", "msg": f"усі td_-моделі й нові поля ({n_checked}) є в таблиці з аналогом/причиною"}
    dup = []
    is_doc = lambda c: c.startswith(DOC_PREFIXES)
    for m in td_models:
        coms = [f["comodel"] or "" for f in m["fields"] if f["type"] == "Many2one"]
        has_party = any(c == "res.partner" or c.startswith("product.") for c in coms)
        has_date = any(f["type"] in ("Date", "Datetime") for f in m["fields"])
        has_doc = any(is_doc(c) for c in coms)
        if has_party and has_date and has_doc:
            dup.append(m["name"])
    manual = []
    for m in models:
        b = m["inherit"] or ""
        if m["name"] and m["name"].startswith("td."):
            continue
        db = next((x for x in m.get("inherit_all", []) if is_doc(x)), None)
        if db:
            b = db
            for f in m["fields"]:
                c = f["comodel"] or ""
                if not f["computed"] and ((f["type"] == "Many2one" and (c == "res.partner" or c.startswith("product."))) or f["type"] in ("Date", "Datetime")):
                    manual.append(f"{b}.{f['name']}")
    parts = []
    if dup: parts.append("td_-модель можливо дублює purchase/stock (партнер/товар + дата + документ продажу/виробництва/складу): " + ", ".join(dup))
    if manual: parts.append("ручне поле (без compute/related) на стандартній моделі — можливий паралельний облік: " + ", ".join(manual))
    dd = {"id": "DM-dup", "status": "WARN" if parts else "PASS",
          "msg": (" | ".join(parts) + " | потрібне письмове рішення Архітектора (checks[]/memo); без нього — FAIL") if parts else "підозрілих td_-моделей і ручних полів немає"}
    out = [dm, dd]
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 1 if any(r["status"] == "FAIL" for r in out) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
