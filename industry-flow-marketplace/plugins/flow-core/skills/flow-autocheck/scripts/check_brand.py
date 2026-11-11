#!/usr/bin/env python3
"""Автоперевірка фірмового стилю ToDo (BR-*). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_brand.py <файли або теки…> --brand <BRAND.md>
Токени беруться з BRAND.md: hex-кольори (#RRGGBB) у рядку «Кольори», назва шрифту після «Шрифт:», логотип — `todo-logo.png`/`todo-mark.png`.
Теки shoot/, screens/, screens-mobile/, video/rec/, dom/ (DOM-дампи Odoo, знімки, кадри) пропускаються (+ --exclude <назва>).
Бренд у відео скрипт не бачить — кадри заставки й титрів дивиться рецензент.
Застосовується до .html/.htm/.css/.svg (інші файли — SKIP: відео й PDF перевіряє рецензент за чек-листом video-materials.md).
BR-colors — у файлі є акцентний і темний кольори бренду (перші два hex з BRAND.md), без урахування регістру.
BR-font   — є «Open Sans» (назва зі BRAND.md) у font-family / @font-face / посиланні Google Fonts.
BR-logo   — є логотип: `data:image/png;base64,` (сторінка-Artifact) або посилання на todo-logo/todo-mark (svg/css)."""
import argparse, json, os, re, sys

APPLY = {".html", ".htm", ".css", ".svg"}
res = []


def add(i, status, msg=""):
    res.append({"id": i, "status": status, "msg": msg})


def tokens(brand_md):
    t = open(brand_md, encoding="utf-8").read()
    line = next((l for l in t.splitlines() if re.search(r"(?i)кольор", l) and "#" in l), "")
    colors = []
    for c in re.findall(r"#[0-9A-Fa-f]{6}\b", line):
        if c.upper() not in colors:
            colors.append(c.upper())
    m = re.search(r"(?im)шрифт[^:\n]*:\s*([A-Z][A-Za-z ]+?)(?:\s*[\(—,.;\n]|\s+\()", t + "\n")
    font = m.group(1).strip() if m else "Open Sans"
    logos = re.findall(r"`(todo-(?:logo|mark)\.png)`", t) or ["todo-logo.png"]
    return colors, font, logos


EXCL = {"shoot", "screens", "screens-mobile", "rec", "dom"}  # DOM-дампи Odoo, знімки й кадри відео — не матеріали бренду


def collect(paths, excl=EXCL):
    out = []
    for p in paths:
        if os.path.isdir(p):
            for r, ds, fs in os.walk(p):
                ds[:] = sorted(d for d in ds if d not in excl)
                out += [os.path.join(r, f) for f in sorted(fs)]
        elif os.path.exists(p):
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("paths", nargs="+"); ap.add_argument("--brand", required=True)
    ap.add_argument("--exclude", action="append", default=[], help="додаткова назва теки, яку пропустити")
    a = ap.parse_args()
    try:
        colors, font, logos = tokens(a.brand)
    except OSError:
        for i in ("BR-colors", "BR-font", "BR-logo"):
            add(i, "FAIL", f"Немає {a.brand}: передай BRAND.md (flow-research/references/brand-todo/BRAND.md)")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    if len(colors) < 2:
        for i in ("BR-colors", "BR-font", "BR-logo"):
            add(i, "FAIL", "У BRAND.md не знайдено двох hex-кольорів бренду (рядок «Кольори»)")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    files = [f for f in collect(a.paths, EXCL | set(a.exclude)) if os.path.splitext(f)[1].lower() in APPLY]
    if not files:
        for i in ("BR-colors", "BR-font", "BR-logo"):
            add(i, "SKIP", "немає .html/.css/.svg для перевірки (відео, PDF — за чек-листом рецензента)")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(0)
    bc, bf, bl = [], [], []
    for f in files:
        t = open(f, encoding="utf-8", errors="replace").read()
        up = t.upper()
        miss = [c for c in colors[:2] if c not in up]
        if miss:
            bc.append(f"{os.path.basename(f)}: немає {', '.join(miss)}")
        if font.lower() not in t.lower():
            bf.append(f"{os.path.basename(f)}: немає «{font}»")
        ext = os.path.splitext(f)[1].lower()
        has_logo = "data:image/png;base64," in t or "data:image/svg+xml" in t or any(l.split(".")[0] in t for l in logos)
        if ext in (".html", ".htm", ".svg") and not has_logo:
            bl.append(f"{os.path.basename(f)}: немає логотипа ToDo")
    add("BR-colors", "FAIL" if bc else "PASS", ("Додай токени бренду (:root): " + "; ".join(bc[:8])) if bc else "")
    add("BR-font", "FAIL" if bf else "PASS", ("Підключи шрифт бренду (Google Fonts або локальний): " + "; ".join(bf[:8])) if bf else "")
    add("BR-logo", "FAIL" if bl else "PASS", ("Встав логотип ToDo як data:-URI (brand-todo/todo-logo.png): " + "; ".join(bl[:8])) if bl else "")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
