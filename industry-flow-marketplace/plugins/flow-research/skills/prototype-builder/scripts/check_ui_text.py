#!/usr/bin/env python3
"""check_ui_text.py <prototype-real/shoot/dom> [--lang uk] [--allow-new] [--allow-words w1,w2] [--allow-empty підпис1,підпис2] [--zero-cols имя1,имя2]
Перевірка DOM-знімків екранів зрізу A-21 (формат пише rec_lib.dumpDom: shoot/dom/<екран>.json з items[{kind,text,label?,required?}]).
UI-english: латинські слова (>=4 літер) у підписах (label/button/header/breadcrumb) у мові показу, окрім дозволених. Для мови, відмінної від uk, — MANUAL (не перевірялось).
UI-new: «Новий/Нове/New» у breadcrumb — лише з --allow-new (prototype.new_record_in_frame: true).
UI-empty: FAIL — порожнє ОБОВ'ЯЗКОВЕ поле (required: true) і нуль «0,0»/«0,00» у клітинці колонки з переліку --zero-cols (технічні імена колонок
          годин/трудомісткості з PLAN.md; без --zero-cols нулі в клітинках лише WARN — «Доставлено 0,00», знижка, податок законні);
          WARN — порожнє необов'язкове поле (чи поле без ознаки required у старому знімку), нуль у колонці поза --zero-cols; kind=flag не перевіряється.
          --allow-empty: підписи або технічні імена полів і колонок, яким порожнє/нульове значення дозволене (діє на field і cell).
Вихід: JSON [{id,status,msg}], код 1 при FAIL."""
import sys, json, re, os, glob

ALLOW = {"demo", "example", "todo", "odoo", "ltd", "kanban", "pdf", "ok"}
LABEL_KINDS = {"label", "button", "header", "breadcrumb"}
EMPTY = {"", "-", "—", "false", "0,0", "0.0", "0,00", "0.00"}
ZERO = re.compile(r"^0[.,]0+( \S+)?$")
NEW = {"новий", "нове", "нова", "new"}
USAGE = "usage: check_ui_text.py <dom-dir> [--lang uk] [--allow-new] [--allow-words a,b] [--allow-empty x,y] [--zero-cols a,b]"


def fail_args(msg):
    print(json.dumps([{"id": "UI-args", "status": "FAIL", "msg": f"{msg}; {USAGE}"}], ensure_ascii=False))
    return 1


def main(argv):
    if not argv or argv[0].startswith("--"):
        return fail_args("не задано каталог DOM-знімків")
    d = argv[0]; lang = "uk"; allow_new = False; allow = set(ALLOW); allow_empty = set(); zero_cols = set()
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--allow-new":
            allow_new = True; i += 1
        elif a in ("--lang", "--allow-words", "--allow-empty", "--zero-cols"):
            if i + 1 >= len(argv) or argv[i + 1].startswith("--"):
                return fail_args(f"{a} без значення")
            v = argv[i + 1]
            if a == "--lang": lang = v
            elif a == "--allow-words": allow |= {w.strip().lower() for w in v.split(",") if w.strip()}
            elif a == "--zero-cols": zero_cols |= {w.strip().lower() for w in v.split(",") if w.strip()}
            else: allow_empty |= {w.strip().lower() for w in v.split(",") if w.strip()}
            i += 2
        else:
            i += 1
    files = sorted(glob.glob(os.path.join(d, "*.json")))
    if not files:
        print(json.dumps([{"id": "UI-english", "status": "FAIL", "msg": f"немає DOM-знімків у {d}"}], ensure_ascii=False)); return 1
    eng, new, bad_empty, warn_empty, broken = [], [], [], [], []
    for f in files:
        try:
            data = json.load(open(f, encoding="utf-8"))
            items = data.get("items", [])
        except Exception as e:
            broken.append(f"{os.path.basename(f)}: невалідний JSON ({e})"); continue
        scr = data.get("screen", os.path.basename(f))
        for it in items:
            kind, text = it.get("kind", ""), (it.get("text") or "").strip()
            low = text.lower(); lab = it.get("label", "")
            if lang == "uk" and kind in LABEL_KINDS:
                for w in re.findall(r"[A-Za-z]{4,}", re.sub(r"\S+@\S+", "", text)):
                    if w.lower() not in allow: eng.append(f"{scr}: «{w}»")
            if kind == "breadcrumb" and low in NEW and not allow_new:
                new.append(f"{scr}: «{text}»")
            if kind == "field" and low in EMPTY and lab.strip().lower() not in allow_empty and it.get("name", "").strip().lower() not in allow_empty:
                msg = f"{scr}: поле «{lab}» = «{text}»"
                (bad_empty if it.get("required") is True else warn_empty).append(msg)
            if kind == "cell" and (ZERO.match(low) or low in {"0,0 h"}) and lab.strip().lower() not in allow_empty:
                msg = f"{scr}: клітинка «{lab}» = «{text}»"
                (bad_empty if lab.strip().lower() in zero_cols else warn_empty).append(msg)

    def res(id_, bad, ok_msg, status="FAIL"):
        return {"id": id_, "status": status if bad else "PASS", "msg": ("; ".join(bad[:12]) + (f" (+{len(bad)-12})" if len(bad) > 12 else "")) if bad else ok_msg}
    if lang == "uk":
        english = res("UI-english", eng, f"англійських підписів немає ({len(files)} екранів)")
    else:
        english = {"id": "UI-english", "status": "MANUAL", "msg": f"мову «{lang}» скрипт не перевіряє (лише uk) — перевірити вручну за скриншотами"}
    out = [english,
           res("UI-new", new, "«Новий» у кадрі немає" + (" (дозволено анкетою)" if allow_new else "")),
           res("UI-empty", bad_empty, "порожніх обов'язкових полів і нулів немає")]
    if not bad_empty and warn_empty:
        out[-1] = res("UI-empty", warn_empty, "", status="WARN")
    elif bad_empty and warn_empty:
        out[-1]["msg"] += f" | WARN (необов'язкові порожні): {len(warn_empty)}"
    if broken:
        out.append(res("UI-dom", broken, "", status="FAIL"))
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 1 if any(r["status"] == "FAIL" for r in out) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
