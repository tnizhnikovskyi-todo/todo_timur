#!/usr/bin/env python3
"""Автоперевірки A-17c без бази: KB-ai, KB-module, KB-ids, KB-route, KB-privacy.
Агент перевіряє сам (скрипт не робить): KB-facts (твердження про поведінку модулів звірено з кодом/SPEC на SHA, не вигадано),
KB-risks (ризики й обмеження = рядки AI-DECISIONS), KB-faq (FAQ узято з A-16b).
Запуск: python3 -I check_kb.py --dir package/support --addons package/addons
Формати: сторінка kb/KB-NNN-<slug>.md починається з «# KB-NNN <назва>» і має рядки «kind: module|diagnostics|faq|limits|architecture»
та для module — «module: td_x». Сценарій діагностики — «### DG-NN <назва>» з рядками Симптом:, Перевірка:, Виправлення:, Маршрут:.
Вихід: JSON [{id,status,msg}]. Код повернення 1, якщо є FAIL."""
import argparse, json, os, re, sys

ROUTES = ["B-13 (B-04)", "B-13 (B-05)", "B-06", "B-07", "D-02", "A-19", "C-07", "support-desk"]
AI_HEADERS = ["джерела", "межі", "читання проду", "маршрути", "діагностика"]
PII = [(r"(?<![\w:])(\+?380\d{9}|0(?:39|50|63|66|67|68|73|9[1-9])\d{7})(?!\w)|\(0\d{2}\)\s?\d{3}", "телефон"),
       (r"ЄДРПОУ\D{0,5}\d{8}\b", "ЄДРПОУ"), (r"[\w.+-]+@[\w-]+\.[\w.-]+", "email"), (r"\bUA\d{27}\b", "IBAN"),
       (r"\b[А-ЯІЇЄҐ][а-яіїєґ']+\s+[А-ЯІЇЄҐ][а-яіїєґ']+\s+[А-ЯІЇЄҐ][а-яіїєґ']+(ович|евич|ївна|івна|ична)\b", "ПІБ"),
       (r"clients/(?!<)[\w-]+", "шлях клієнта")]
PAGE = re.compile(r"^KB-(\d{3,})-.+\.md$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--addons", required=True)
    a = ap.parse_args()
    res = []

    def add(i, status, msg=""):
        res.append({"id": i, "status": status, "msg": msg})

    root = a.dir
    kb = os.path.join(root, "kb")
    pages = sorted(n for n in os.listdir(kb) if n.endswith(".md")) if os.path.isdir(kb) else []
    texts = {n: open(os.path.join(kb, n), encoding="utf-8").read() for n in pages}
    ai_p = os.path.join(root, "AI-INSTRUCTIONS.md")
    ai = open(ai_p, encoding="utf-8").read() if os.path.exists(ai_p) else ""
    idx_p = os.path.join(root, "INDEX.md")
    index = open(idx_p, encoding="utf-8").read() if os.path.exists(idx_p) else ""

    # KB-ai
    low = ai.lower()
    miss = [h for h in AI_HEADERS if not re.search(r"^#{1,4}\s*" + re.escape(h), low, re.M)]
    if ai and "prod-ro-" not in ai:
        miss.append("згадка prod-ro-<клієнт>")
    if ai and not re.search(r"лише\s+читання|тільки\s+читання", low):
        miss.append("«лише читання проду»")
    add("KB-ai", "FAIL" if (miss or not ai or not index) else "PASS",
        ("немає: " + ", ".join(miss + (["INDEX.md"] if not index else []))) if (miss or not ai or not index) else "")

    # KB-ids
    msg, ids = [], {}
    for n in pages:
        m = PAGE.match(n)
        if not m:
            msg.append(f"{n}: ім'я не KB-NNN-<slug>.md")
            continue
        num = m.group(1)
        if num in ids:
            msg.append(f"дубль KB-{num}: {ids[num]} і {n}")
        ids[num] = n
        h1 = re.search(r"^#\s+KB-(\d+)", texts[n], re.M)
        if not h1 or h1.group(1) != num:
            msg.append(f"{n}: заголовок не «# KB-{num} …»")
        if not re.search(r"^kind:\s*(module|diagnostics|faq|limits|architecture)\s*$", texts[n], re.M):
            msg.append(f"{n}: немає рядка kind:")
        if index and f"KB-{num}" not in index:
            msg.append(f"KB-{num} немає в INDEX.md")
    if not pages:
        msg.append("немає сторінок kb/")
    add("KB-ids", "FAIL" if msg else "PASS", "; ".join(msg[:10]))

    # KB-module
    mods = sorted(d for d in os.listdir(a.addons) if d.startswith("td_") and os.path.isfile(os.path.join(a.addons, d, "__manifest__.py"))) if os.path.isdir(a.addons) else []
    covered = set()
    for t in texts.values():
        m = re.search(r"^module:\s*(td_\w+)\s*$", t, re.M)
        if m and re.search(r"^kind:\s*module\s*$", t, re.M):
            covered.add(m.group(1))
    nomod = [m for m in mods if m not in covered]
    ghost = sorted(covered - set(mods))
    msg = []
    if not mods:
        msg.append(f"у {a.addons} немає модулів td_*")
    if nomod:
        msg.append("немає сторінки: " + ", ".join(nomod))
    if ghost:
        msg.append("сторінка без модуля: " + ", ".join(ghost))
    add("KB-module", "FAIL" if msg else "PASS", "; ".join(msg))

    # KB-route
    msg, total = [], 0
    for n, t in texts.items():
        if not re.search(r"^kind:\s*diagnostics\s*$", t, re.M):
            continue
        parts = re.split(r"^(?=###\s+DG-\d+)", t, flags=re.M)
        for p in parts:
            h = re.match(r"###\s+(DG-\d+)", p)
            if not h:
                continue
            total += 1
            for fld in ("Симптом", "Перевірка", "Виправлення", "Маршрут"):
                if not re.search(r"^\s*[-*]?\s*\**" + fld + r"\**:", p, re.M):
                    msg.append(f"{n} {h.group(1)}: немає «{fld}:»")
            mr = re.search(r"^\s*[-*]?\s*\**Маршрут\**:\**\s*(.+)$", p, re.M)
            if mr and not any(mr.group(1).strip().startswith(r) for r in ROUTES):
                msg.append(f"{n} {h.group(1)}: маршрут «{mr.group(1).strip()[:30]}» не з {ROUTES}")
    if total == 0:
        msg.append("немає сценаріїв діагностики DG-NN у kb/ з kind: diagnostics")
    add("KB-route", "FAIL" if msg else "PASS", "; ".join(msg[:10]))

    # KB-privacy
    hits = []
    scan = [("AI-INSTRUCTIONS.md", ai), ("INDEX.md", index)] + list(texts.items())
    for name, t in scan:
        for rx, kind in PII:
            if re.search(rx, t):
                hits.append(f"{name}: {kind}")
    add("KB-privacy", "FAIL" if hits else "PASS", "; ".join(hits[:8]))

    for i, why in (("KB-facts", "поведінка/параметри модулів звірено з кодом і SPEC на SHA, нічого не вигадано — агент/рецензент"),
                   ("KB-risks", "обмеження й ризики = рядки research/AI-DECISIONS.md (посилання AI-NN) — агент"),
                   ("KB-faq", "FAQ узято з A-16b (user-guide), без розбіжностей — агент")):
        add(i, "MANUAL", why)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
