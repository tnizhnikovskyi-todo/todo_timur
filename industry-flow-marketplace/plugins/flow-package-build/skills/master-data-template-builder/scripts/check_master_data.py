#!/usr/bin/env python3
"""Автоперевірки A-13 без бази: MD-rows, MD-readme, MD-pii, MD-td, MD-ref, MD-order (+ MD-cols, MD-req з --fields).
Агент перевіряє сам: MD-trace, MD-modules, MD-import, MD-scope, lint (скрипт їх не робить).
Запуск: python3 -I check_master_data.py --dir package/master-data [--fields fields.json]
fields.json: {"<model>": {"<field>": {"required": bool, "selection": [..]|null, "default": bool}}}
Побудова fields.json (агент, через odoo-mcp з явним connection_id):
  1) odoo_get_fields(model, attributes=["type","required","relation","selection"]);
  2) selection у fields_get - пари [value, label]: у файл класти лише value (перші елементи пар);
  3) odoo_execute(model, "default_get", args=[[<імена обов'язкових полів>]]): default=true, якщо ключ є у відповіді,
     інакше false. Не проставляти default=false усім - MD-req дасть хибні FAIL (type, uom_id, categ_id, product_qty).
Вихід: JSON [{id,status,msg}]. Код повернення 1, якщо є FAIL."""
import argparse, csv, json, os, re, sys

HEADERS = ["файли", "порядок імпорту", "залежності між файлами", "трасування тр",
           "потребують модулів a-11", "тест-імпорт", "зміни версії"]
PII = [(r"(?<![\w:])(\+?380\d{9}|0(?:39|50|63|66|67|68|73|9[1-9])\d{7})(?!\w)|\(0\d{2}\)\s?\d{3}", "телефон"), (r"ЄДРПОУ\D{0,5}\d{8}\b", "ЄДРПОУ"), (r"[\w.+-]+@[\w-]+\.[\w.-]+", "email"),
       (r"\bUA\d{27}\b", "IBAN"), (r"\b[А-ЯІЇЄҐ][а-яіїєґ']+\s+[А-ЯІЇЄҐ][а-яіїєґ']+\s+[А-ЯІЇЄҐ][а-яіїєґ']+(ович|евич|ївна|івна|ична)\b", "ПІБ")]
FILE_RE = re.compile(r"^(\d{2}b?)_(.+)\.csv$")

def collect(root):
    out = []
    for sub, td in (("", False), ("td", True)):
        d = os.path.join(root, sub)
        if not os.path.isdir(d):
            continue
        for n in sorted(os.listdir(d)):
            m = FILE_RE.match(n)
            if m:
                out.append({"path": os.path.join(d, n), "name": n, "nn": m.group(1), "model": m.group(2), "td": td})
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--fields")
    a = ap.parse_args()
    res = []
    def add(i, ok, msg=""):
        res.append({"id": i, "status": "PASS" if ok else "FAIL", "msg": msg})
    files = collect(a.dir)
    data = {}
    for f in files:
        with open(f["path"], encoding="utf-8", newline="") as fh:
            rows = list(csv.reader(fh))
        f["header"], f["rows"] = (rows[0] if rows else []), rows[1:]
        data[f["path"]] = f
    # MD-rows
    bad = [f["name"] for f in files if not f["rows"]]
    add("MD-rows", files and not bad, "порожні або відсутні файли: " + ", ".join(bad) if (bad or not files) else "")
    # MD-readme
    rp = os.path.join(a.dir, "README.md")
    readme = open(rp, encoding="utf-8").read() if os.path.exists(rp) else ""
    low = readme.lower()
    miss = [h for h in HEADERS if not re.search(r"^#{1,4}\s*" + re.escape(h), low, re.M)]
    add("MD-readme", readme and not miss, "немає заголовків: " + ", ".join(miss) if (miss or not readme) else "")
    # MD-td
    errs = []
    for f in files:
        has_td = bool(re.match(r"^td[._]", f["model"])) or any(re.match(r"^td[._]", h) for h in f["header"])
        if has_td and not f["td"]:
            errs.append(f["name"] + " має td_* поза td/")
        if f["td"] and f["name"] not in readme:
            errs.append(f["name"] + " не згадано в README")
    add("MD-td", not errs, "; ".join(errs))
    # MD-pii
    hits = []
    for f in files:
        txt = open(f["path"], encoding="utf-8").read()
        for rx, kind in PII:
            if re.search(rx, txt):
                hits.append(f"{f['name']}: {kind}")
        for col in ("vat", "company_registry"):
            if col in f["header"]:
                i = f["header"].index(col)
                if any(len(r) > i and r[i].strip() for r in f["rows"]):
                    hits.append(f"{f['name']}: непорожнє {col}")
    add("MD-pii", not hits, "; ".join(hits))
    # MD-ref / MD-order (лише стандартні файли; xmlid не з td_md. вважаються стандартними модулями)
    owner = {}
    for f in files:
        if f["header"] and f["header"][0] == "id":
            for r in f["rows"]:
                if r:
                    owner[r[0]] = f
    dangling, late = [], []
    for f in files:
        for ci, h in enumerate(f["header"]):
            if not h.endswith("/id"):
                continue
            for r in f["rows"]:
                for v in (r[ci].split(",") if len(r) > ci and r[ci] else []):
                    v = v.strip()
                    if not v.startswith("td_md."):
                        continue
                    o = owner.get(v)
                    if o is None:
                        dangling.append(f"{f['name']}: {v}")
                    elif o is not f and (o["td"], o["nn"]) > (f["td"], f["nn"]) and not f["nn"].endswith("b"):
                        late.append(f"{f['name']} -> {o['name']}")
    add("MD-ref", not dangling, "; ".join(sorted(set(dangling))[:10]))
    add("MD-order", not late, "залежність імпортується пізніше: " + "; ".join(sorted(set(late))[:10]) if late else "")
    # MD-cols / MD-req
    if a.fields:
        fm = json.load(open(a.fields, encoding="utf-8"))
        ce, re_ = [], []
        for f in files:
            if f["td"]:
                continue
            spec = fm.get(f["model"])
            if spec is None:
                ce.append(f"{f['name']}: немає моделі в дампі")
                continue
            names = [h.split("/")[0] for h in f["header"]]
            for h, n in zip(f["header"], names):
                if n != "id" and n not in spec:
                    ce.append(f"{f['name']}: колонки {h} немає в моделі")
            for n, s in spec.items():
                if s.get("required") and not s.get("default") and n not in names:
                    re_.append(f"{f['name']}: немає обов'язкової {n}")
            for i, n in enumerate(names):
                sel = (spec.get(n) or {}).get("selection")
                if sel and "/" not in f["header"][i]:
                    for r in f["rows"]:
                        if len(r) > i and r[i] and r[i] not in sel:
                            ce.append(f"{f['name']}: {n}={r[i]} недопустиме")
                if (spec.get(n) or {}).get("required") and not (spec.get(n) or {}).get("default") and any(len(r) <= i or not r[i].strip() for r in f["rows"]):
                    re_.append(f"{f['name']}: порожнє обов'язкове {n}")
        add("MD-cols", not ce, "; ".join(ce[:10]))
        add("MD-req", not re_, "; ".join(re_[:10]))
    else:
        for i in ("MD-cols", "MD-req"):
            res.append({"id": i, "status": "SKIPPED", "msg": "немає --fields (дамп odoo_get_fields)"})
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)

if __name__ == "__main__":
    main()
