#!/usr/bin/env python3
"""Автоперевірка research/REUSE.md (RU-*). stdlib. Вивід JSON [{id,status,msg}]; код 1 при FAIL.
Використання: check_reuse.py <research/REUSE.md> [--inventory research/reuse-inventory.md]
            check_reuse.py <research/reuse-inventory.md> --mode inventory   (режим inventory A-03c: where = reuse-inventory.md; RU-inv-file, RU-id)
RU-file     — файл є; розділи `## Реєстр`, `## Вплив на години`, `## Відкинуто`.
RU-id       — ID REUSE-NN унікальні, двозначні (id-patterns.md); кожен є в inventory (якщо передано).
RU-verdict  — Рішення ∈ беремо|адаптуємо|ні; Основа `ToDo-готовий` для беремо/адаптуємо.
RU-hours    — для беремо/адаптуємо — обидва числа годин (адаптація, розробка з нуля); для «ні» — «—».
RU-license  — права невідомо/AGPL -> лише «ні» (К-09, картка A-03c).
Порожній результат: у inventory — рядок «кандидатів не знайдено (переглянуто N …)», у REUSE.md `## Реєстр` — «готових модулів немає» (+ «нічого не відкинуто»); без маркера — FAIL.
RU-rejected — кожен REUSE із «ні» згаданий у розділі «Відкинуто» (або там рядок «нічого не відкинуто» за відсутності «ні»)."""
import argparse, json, re, sys
res = []
def add(i, s, m=""): res.append({"id": i, "status": s, "msg": m})
def sect(t, name):
    m = re.search(r"^##\s+" + re.escape(name) + r"\b.*?$(.*?)(?=^##\s|\Z)", t, re.S | re.M)
    return m.group(1) if m else None
def rows(s):
    out = []
    for l in (s or "").splitlines():
        l = l.strip()
        if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l):
            out.append([c.strip() for c in l.strip("|").split("|")])
    return out
def main():
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--inventory"); ap.add_argument("--mode", choices=("decide", "inventory"), default="decide")
    a = ap.parse_args()
    try: t = open(a.file, encoding="utf-8").read()
    except OSError: t = ""
    if a.mode == "inventory":
        ids = re.findall(r"^\|\s*(REUSE-[^|\s]*)\s*\|", t, re.M)
        bad = sorted({i for i in ids if not re.fullmatch(r"REUSE-\d{2}", i)} | {i for i in ids if ids.count(i) > 1})
        empty = (not ids) and bool(re.search(r"кандидатів не знайдено", t, re.I))
        add("RU-inv-file", "PASS" if (ids or empty) else "FAIL", "" if (ids or empty) else "немає файла або рядків REUSE-NN (інвентар); для нуля кандидатів потрібен рядок «кандидатів не знайдено (переглянуто N …)»")
        add("RU-id", "FAIL" if bad else "PASS", "некоректні/дубльовані ID: " + ", ".join(bad) if bad else ("порожній інвентар (маркер)" if empty else ""))
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)
    reg, hrs, rej = sect(t, "Реєстр"), sect(t, "Вплив на години"), sect(t, "Відкинуто")
    miss = [n for n, s in (("Реєстр", reg), ("Вплив на години", hrs), ("Відкинуто", rej)) if s is None]
    add("RU-file", "FAIL" if (not t or miss) else "PASS", "немає файла/розділів: " + ", ".join(miss or ["файл"]) if (not t or miss) else "")
    if reg is None:
        for i in ("RU-id", "RU-verdict", "RU-hours", "RU-license", "RU-rejected"): add(i, "SKIP", "немає розділу «Реєстр»")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    rr = rows(reg); hdr = [c.lower() for c in rr[0]] if rr else []
    body = rr[1:]
    def col(name):
        for n, h in enumerate(hdr):
            if name in h: return n
        return None
    ci, cv, ch1, ch2, cb, cl = col("id"), col("рішення"), col("адапт"), col("з нуля"), col("основа"), col("права")
    bad_id, bad_v, bad_h, bad_l, nos = [], [], [], [], []
    seen = set()
    for r in body:
        rid = r[ci] if ci is not None and ci < len(r) else ""
        if not re.fullmatch(r"REUSE-\d{2}", rid) or rid in seen: bad_id.append(rid or "?")
        seen.add(rid)
        v = r[cv].lower() if cv is not None and cv < len(r) else ""
        if v not in ("беремо", "адаптуємо", "ні"): bad_v.append(rid); continue
        base = r[cb] if cb is not None and cb < len(r) else ""
        h1 = r[ch1] if ch1 is not None and ch1 < len(r) else ""; h2 = r[ch2] if ch2 is not None and ch2 < len(r) else ""
        if v == "ні":
            nos.append(rid)
            if h1 not in ("—", "-", "") or h2 not in ("—", "-", ""): bad_h.append(rid + " (ні з годинами)")
        else:
            if base != "ToDo-готовий": bad_v.append(rid + " (основа)")
            if not (re.fullmatch(r"\d+([.,]\d+)?", h1) and re.fullmatch(r"\d+([.,]\d+)?", h2)): bad_h.append(rid)
            lic = r[cl].lower() if cl is not None and cl < len(r) else ""
            if "невідом" in lic or "agpl" in lic: bad_l.append(rid)
    # один запис RU-id на всю перевірку: усі дефекти ID разом
    id_msgs = []
    empty_reg = (not body) and bool(re.search(r"готових модулів немає", reg or "", re.I))
    if not body and not empty_reg: id_msgs.append("порожній реєстр (для нуля кандидатів потрібен рядок «готових модулів немає»)")
    if bad_id: id_msgs.append("некоректні/дубльовані ID: " + ", ".join(bad_id))
    if a.inventory and body:
        try:
            inv = set(re.findall(r"REUSE-\d{2}", open(a.inventory, encoding="utf-8").read()))
            absent = [i for i in seen if i and i not in inv]
            if absent: id_msgs.append("немає в inventory: " + ", ".join(absent))
        except OSError: id_msgs.append("немає " + a.inventory)
    add("RU-id", "FAIL" if id_msgs else "PASS", "; ".join(id_msgs))
    add("RU-verdict", "FAIL" if bad_v else "PASS", "рішення/основа: " + ", ".join(bad_v) if bad_v else "")
    add("RU-hours", "FAIL" if bad_h else "PASS", "години: " + ", ".join(bad_h) if bad_h else "")
    add("RU-license", "FAIL" if bad_l else "PASS", "права невідомі/AGPL не можуть бути беремо/адаптуємо: " + ", ".join(bad_l) if bad_l else "")
    rj = rej or ""
    lost = [i for i in nos if i not in rj]
    if nos and re.search(r"нічого не відкинуто", rj): add("RU-rejected", "FAIL", "є рішення «ні» (" + ", ".join(nos) + "), а розділ «Відкинуто» каже «нічого не відкинуто»")
    elif nos and lost: add("RU-rejected", "FAIL", "«ні» без запису у «Відкинуто»: " + ", ".join(lost))
    elif not nos and not re.search(r"нічого не відкинуто|REJ-\d{3}", rj): add("RU-rejected", "FAIL", "у «Відкинуто» немає ні реєстру, ні рядка «нічого не відкинуто»")
    else: add("RU-rejected", "PASS")
    print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)
if __name__ == "__main__": main()
