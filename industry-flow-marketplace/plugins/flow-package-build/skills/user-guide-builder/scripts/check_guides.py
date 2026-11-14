#!/usr/bin/env python3
"""Автоперевірки A-16b без бази: UG-files, UG-cover, UG-img, UG-sha, UG-lang, UG-card (+ UG-admin).
Агент перевіряє сам (скрипт не робить): UG-fresh (знімки зроблено на стенді з цим SHA), UG-ui (підписи кроків = підписи в UI),
UG-pii (на знімках немає чужих даних), lint.
Запуск: python3 -I check_guides.py --dir package/docs/user-guide --spec package/SPEC.md [--modules-sha <sha>] [--allow Word,Word]
  --modules-sha: SHA останнього коміту, що змінив package/addons (git log -1 --format=%H -- package/addons); без нього UG-sha = SKIPPED.
Сценарій SPEC = ідентифікатор SC-NN (двозначний мінімум) у SPEC.md (заголовок або рядок таблиці).
Вихід: JSON [{id,status,msg}]. Код повернення 1, якщо є FAIL."""
import argparse, json, os, re, sys

SC = re.compile(r"\bSC-\d{2,}\b")
IMG = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
SHA_LINE = re.compile(r"SHA\s+стенда\W{0,6}([0-9a-f]{7,40})\b", re.I)
LATIN = re.compile(r"\b[A-Za-z][A-Za-z']{2,}\b")
DEFAULT_ALLOW = {"Odoo", "PDF", "CSV", "Excel", "QR", "Wi", "Fi", "Enter", "Esc", "Tab", "Ctrl", "Shift"}
STEP_LINE = re.compile(r"^\s*(\|\s*\d+\s*\||\d+[.)]\s)")
ADMIN_HEADERS = ["параметри", "профілі", "редакції", "перший запуск"]
CARD_MAX_LINES = 45


def strip_noise(line):
    line = IMG.sub(" ", line)
    line = re.sub(r"`[^`]*`", " ", line)
    line = re.sub(r"https?://\S+", " ", line)
    line = re.sub(r"\]\([^)]*\)", "]", line)
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--modules-sha")
    ap.add_argument("--allow", default="")
    a = ap.parse_args()
    allow = DEFAULT_ALLOW | {w.strip() for w in a.allow.split(",") if w.strip()}
    res = []

    def add(i, status, msg=""):
        res.append({"id": i, "status": status, "msg": msg})

    root = a.dir
    idx_p = os.path.join(root, "INDEX.md")
    index = open(idx_p, encoding="utf-8").read() if os.path.exists(idx_p) else ""
    role_files = sorted(n for n in os.listdir(root) if n.endswith(".md") and n != "INDEX.md") if os.path.isdir(root) else []
    cards_dir = os.path.join(root, "cards")
    card_files = sorted(os.listdir(cards_dir)) if os.path.isdir(cards_dir) else []
    card_files = [n for n in card_files if n.endswith(".md")]

    # UG-files
    miss = []
    if not index:
        miss.append("INDEX.md")
    if "admin.md" not in role_files:
        miss.append("admin.md")
    roles = [n[:-3] for n in role_files if n != "admin.md"]
    if not roles:
        miss.append("<роль>.md")
    for r in roles:
        if r + ".md" not in card_files:
            miss.append(f"cards/{r}.md")
    add("UG-files", "FAIL" if miss else "PASS", "немає: " + ", ".join(miss) if miss else "")

    # UG-cover
    spec_txt = open(a.spec, encoding="utf-8").read() if os.path.exists(a.spec) else ""
    spec_ids = sorted(set(SC.findall(spec_txt)))
    heads = {}
    for n in role_files:
        for line in open(os.path.join(root, n), encoding="utf-8").read().splitlines():
            if re.match(r"^#{2,4}\s", line):
                for s in SC.findall(line):
                    heads.setdefault(s, n)
    if not spec_ids:
        add("UG-cover", "FAIL", "у SPEC немає сценаріїв SC-NN: нічого покривати (звірити вхід)")
    else:
        nocover = [s for s in spec_ids if s not in heads]
        noindex = [s for s in spec_ids if s in heads and not re.search(re.escape(s) + r".*\|?.*" + re.escape(heads[s]), index)]
        bad = [f"{s}: немає розділу" for s in nocover] + [f"{s}: немає рядка в INDEX" for s in noindex]
        add("UG-cover", "FAIL" if bad else "PASS", "; ".join(bad[:12]))

    # UG-img
    md_files = [(os.path.join(root, n), n) for n in role_files] + [(os.path.join(cards_dir, n), "cards/" + n) for n in card_files]
    if index:
        md_files.append((idx_p, "INDEX.md"))
    referenced, broken = set(), []
    for p, label in md_files:
        for ref in IMG.findall(open(p, encoding="utf-8").read()):
            if re.match(r"https?://", ref):
                continue
            full = os.path.normpath(os.path.join(os.path.dirname(p), ref))
            referenced.add(full)
            if not os.path.isfile(full):
                broken.append(f"{label}: {ref}")
    img_root = os.path.join(root, "img")
    on_disk = set()
    for dp, _, fs in os.walk(img_root):
        for f in fs:
            on_disk.add(os.path.normpath(os.path.join(dp, f)))
    orphans = sorted(os.path.relpath(f, root) for f in on_disk - referenced)
    msg = []
    if broken:
        msg.append("немає файлу: " + ", ".join(broken[:8]))
    if orphans:
        msg.append("сироти: " + ", ".join(orphans[:8]))
    add("UG-img", "FAIL" if msg else "PASS", "; ".join(msg))

    # UG-sha
    m = SHA_LINE.search(index)
    if not m:
        add("UG-sha", "FAIL", "в INDEX.md немає рядка «SHA стенда: <sha>»")
    elif not a.modules_sha:
        add("UG-sha", "SKIPPED", "немає --modules-sha: звірку з SHA модулів виконати вручну")
    else:
        s, t = m.group(1).lower(), a.modules_sha.lower()
        ok = s.startswith(t) or t.startswith(s)
        add("UG-sha", "PASS" if ok else "FAIL", "" if ok else f"INDEX {s[:12]} != модулі {t[:12]}")

    # UG-lang (кроки ролей і карток; admin.md — з іменами параметрів, не перевіряється)
    hits = []
    for p, label in md_files:
        if label in ("admin.md", "INDEX.md"):
            continue
        for i, line in enumerate(open(p, encoding="utf-8").read().splitlines(), 1):
            if not STEP_LINE.match(line):
                continue
            words = [w for w in LATIN.findall(strip_noise(line)) if w not in allow and w.lower() not in {x.lower() for x in allow}]
            if words:
                hits.append(f"{label}:{i}: {', '.join(sorted(set(words))[:4])}")
    add("UG-lang", "FAIL" if hits else "PASS", "; ".join(hits[:8]))

    # UG-card
    big = []
    for n in card_files:
        lines = [l for l in open(os.path.join(cards_dir, n), encoding="utf-8").read().splitlines() if l.strip()]
        if len(lines) > CARD_MAX_LINES:
            big.append(f"cards/{n}: {len(lines)} рядків > {CARD_MAX_LINES}")
    add("UG-card", "FAIL" if big else "PASS", "; ".join(big))

    # UG-admin
    ap_ = os.path.join(root, "admin.md")
    adm = open(ap_, encoding="utf-8").read().lower() if os.path.exists(ap_) else ""
    miss = [h for h in ADMIN_HEADERS if not re.search(r"^#{1,4}\s*" + re.escape(h), adm, re.M)]
    add("UG-admin", "FAIL" if (miss or not adm) else "PASS", "немає розділів: " + ", ".join(miss) if (miss or not adm) else "")

    for i, why in (("UG-fresh", "знімки на стенді з SHA INDEX — перевіряє агент (журнал зйомки)"),
                   ("UG-ui", "підписи кроків = підписи в UI — агент/рецензент"),
                   ("UG-pii", "на знімках немає чужих даних — агент/рецензент")):
        add(i, "MANUAL", why)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
