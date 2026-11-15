#!/usr/bin/env python3
r"""Автоперевірки A-16b без бази: UG-files, UG-cover, UG-img, UG-sha, UG-lang, UG-card, UG-roles (+ UG-admin, UG-cover-dev, UG-cover-admin).
Агент перевіряє сам (скрипт не робить): UG-fresh (знімки зроблено на стенді з цим SHA), UG-ui (підписи кроків = підписи в UI),
UG-pii (на знімках немає чужих даних), lint.
Запуск: python3 -I check_guides.py --dir package/docs/user-guide --spec package/SPEC.md [--spec package/demo/scenarios.md]
        [--spec concept/scenarios.md] [--id-pattern 'SC-\d{2,}'] [--stand-sha <sha>] [--allow Word,Word]
  --spec: джерело сценаріїв, можна кілька в порядку пріоритету (SPEC -> package/demo/scenarios.md -> concept/scenarios.md);
          береться перше, де знайдено ідентифікатори; обране джерело має бути записано в INDEX рядком «Джерело сценаріїв: <шлях>».
  --id-pattern: регулярний вираз ID сценарію (за замовчуванням SC-NN; для SPEC з UC-NN/іншим форматом — свій).
  --stand-sha: SHA_STAND з package/demo/README.md (SHA стенда A-15; == SHA в INDEX.md, scenarios.md, ACCEPTANCE.md); без нього UG-sha = SKIPPED.
          --modules-sha — застарілий псевдонім. Свіжість знімків (код пакета = SHA_CHECKS з package/CHECKS.md) — окремо:
          git diff --quiet <SHA_CHECKS>..HEAD -- package/addons package/config package/master-data ':!package/addons/td_*_elearning/*' ':!package/config/manifest.yaml' ':!package/config/CONFIG.md'
          (SHA_CHECKS з package/CHECKS.md; код 0 = знімки актуальні). manifest.yaml/CONFIG.md виключено: A-17b дописує в них навчання;
          окремо їх diff без рядків website_slides/_elearning має бути порожнім.
        [--addons package/addons] [--answers package/templates/answers.yaml [--answers package/demo/profiles/<профіль>.yaml]] [--config package/config/CONFIG.md]
  --addons: UG-cover-dev (§26а, «розроблене»): кожне меню, дія вікна й звіт (menuitem / ir.actions.act_window / ir.actions.report з XML модулів td_*,
          крім td_*_elearning і td_*_demo; включно зі спільними td_home_menu, td_support, td_knowledge) має назву (українську з i18n/uk.po або вихідну, цілим словом) в тексті посібників
          і рядок у таблиці INDEX «Покриття: розроблене»; без --addons = SKIPPED.
  --answers / --config: UG-cover-admin («налаштування й експлуатація»): кожен блок VP-NN answers.yaml (ідентифікатор або значення param:; поля схеми не перевіряються) і кожен листовий ключ не-VP блоків (повний шлях через крапку або кінцевий ключ) і кожен
          VP-NN з CONFIG.md згадано в admin.md; INDEX має таблицю «Покриття: налаштування й експлуатація»; без обох = SKIPPED.
UG-img: зображення = лише png/jpg/jpeg/webp у img/ (SHOOT-LOG.md не зображення); розділ зі «Статус: готово» має >=1 зображення.
UG-cover: розділ «Статус: заблоковано дефектом» = FAIL (повернення A-14: крок returned, не done).
Вихід: JSON [{id,status,msg}]. Код повернення 1, якщо є FAIL."""
import argparse, json, os, re, sys
import xml.etree.ElementTree as ET

SC = re.compile(r"\bSC-\d{2,}\b")  # перевизначається --id-pattern
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
SRC_LINE = re.compile(r"Джерело сценаріїв:\s*(\S+)")
IMG = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
SHA_LINE = re.compile(r"SHA\s+стенда\W{0,6}([0-9a-f]{7,40})\b", re.I)
LATIN = re.compile(r"\b[A-Za-z][A-Za-z']{2,}\b")
DEFAULT_ALLOW = {"Odoo", "ToDo", "PDF", "CSV", "Excel", "QR", "CRM", "SMS", "URL", "ID", "BAS", "Email", "Wi", "Fi", "Enter", "Esc", "Tab", "Ctrl", "Shift"}
STEP_LINE = re.compile(r"^\s*(\|\s*\d+\s*\||\d+[.)]\s)")
ADMIN_HEADERS = ["параметри", "профілі", "редакції", "перший запуск"]
ADMIN_OPS = ["майстер-дані", "обмін", "пошта", "оновлення", "резервні копії", "звернення в підтримку", "база знань"]
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
    ap.add_argument("--spec", required=True, action="append")
    ap.add_argument("--id-pattern", default=r"SC-\d{2,}")
    ap.add_argument("--stand-sha", "--modules-sha", dest="modules_sha")
    ap.add_argument("--allow", default="")
    ap.add_argument("--addons")
    ap.add_argument("--answers", action="append", default=[])
    ap.add_argument("--config")
    a = ap.parse_args()
    global SC
    SC = re.compile(r"\b(?:" + a.id_pattern + r")\b")
    allow = DEFAULT_ALLOW | {w.strip() for w in a.allow.split(",") if w.strip()}
    try:  # «Дозволені латинські назви: BAS, CAD» з INDEX.md
        for ln in open(os.path.join(a.dir, "INDEX.md"), encoding="utf-8"):
            m_ = re.match(r"\s*Дозволені латинські назви:\s*(.+)", ln)
            if m_:
                allow = set(allow) | {p for w in re.split(r"[,;]", m_.group(1)) if w.strip() for p in [w.strip()] + re.split(r"[-\u2011]", w.strip()) if p}
    except OSError:
        pass
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
    spec_ids, spec_used = [], None
    for sp in a.spec:
        txt = open(sp, encoding="utf-8").read() if os.path.exists(sp) else ""
        ids = sorted(set(SC.findall(txt)))
        if ids:
            spec_ids, spec_used = ids, sp
            break
    heads, status = {}, {}
    for n in role_files:
        for part in re.split(r"(?m)^(?=#{2,4}\s)", open(os.path.join(root, n), encoding="utf-8").read()):
            hm = re.match(r"#{2,4}\s.*", part)
            if not hm:
                continue
            for sc in SC.findall(hm.group(0)):
                heads.setdefault(sc, n)
                st = re.search(r"Статус:\s*(.+)", part)
                status[(n, sc)] = (st.group(1).strip().lower() if st else "готово", IMG.findall(part))
    if not spec_ids:
        add("UG-cover", "FAIL", "у джерелах сценаріїв (" + ", ".join(a.spec) + f") немає ID за шаблоном {a.id_pattern}: нічого покривати (звірити вхід, задати --id-pattern)")
    else:
        nocover = [x for x in spec_ids if x not in heads]
        noindex = [x for x in spec_ids if x in heads and not re.search(re.escape(x) + r".*\|?.*" + re.escape(heads[x]), index)]
        blocked = [x for x in spec_ids if x in heads and "заблоковано" in status.get((heads[x], x), ("", []))[0]]
        bad = [f"{x}: немає розділу" for x in nocover] + [f"{x}: немає рядка в INDEX" for x in noindex] \
            + [f"{x}: заблоковано дефектом — повернення A-14 (returned, не done)" for x in blocked]
        sm = SRC_LINE.search(index)
        if not sm:
            bad.append("в INDEX немає рядка «Джерело сценаріїв: <шлях>»")
        elif spec_used and not spec_used.replace("\\", "/").endswith(sm.group(1).lstrip("./")):
            bad.append(f"INDEX називає джерело {sm.group(1)}, а перше з ID — {spec_used}")
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
            if not f.lower().endswith(IMG_EXT):
                continue  # SHOOT-LOG.md та інші не-зображення не є «сиротами»
            on_disk.add(os.path.normpath(os.path.join(dp, f)))
    orphans = sorted(os.path.relpath(f, root) for f in on_disk - referenced)
    msg = []
    if broken:
        msg.append("немає файлу: " + ", ".join(broken[:8]))
    if orphans:
        msg.append("сироти: " + ", ".join(orphans[:8]))
    noshot = sorted(f"{n}#{sc}" for (n, sc), (st, imgs) in status.items() if "заблоковано" not in st and not imgs)
    if noshot:
        msg.append("розділ готовий, але без знімка: " + ", ".join(noshot[:8]))
    add("UG-img", "FAIL" if msg else "PASS", "; ".join(msg))

    # UG-sha
    m = SHA_LINE.search(index)
    if not m:
        add("UG-sha", "FAIL", "в INDEX.md немає рядка «SHA стенда: <sha>»")
    elif not a.modules_sha:
        add("UG-sha", "SKIPPED", "немає --stand-sha: звірку з SHA_STAND (demo/README.md) виконати вручну")
    else:
        s, t = m.group(1).lower(), a.modules_sha.lower()
        ok = s.startswith(t) or t.startswith(s)
        add("UG-sha", "PASS" if ok else "FAIL", "" if ok else f"INDEX {s[:12]} != SHA_STAND {t[:12]}")

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

    # UG-roles: таблиця «## Ролі» з файлами <роль>.md (її читає check_elearning.py EL-courses)
    rl, inside = [], False
    for ln in index.splitlines():
        if re.match(r"^##\s", ln):
            inside = bool(re.match(r"^##\s*Ролі", ln))
            continue
        if inside and ln.strip().startswith("|"):
            for cell in ln.strip().strip("|").split("|"):
                m_ = re.fullmatch(r"\s*([\w-]+)\.md\s*", cell)
                if m_ and not cell.strip().startswith("cards/"):
                    rl.append(m_.group(1))
                    break
    bad_r = [r for r in rl if r + ".md" not in role_files]
    miss_r = [r for r in roles + (["admin"] if "admin.md" in role_files else []) if r not in rl]  # admin.md теж має рядок у «Ролі» (index-template.md; elearning-builder Крок 2 рахує курси за таблицею)
    if not rl:
        add("UG-roles", "FAIL", "в INDEX.md немає таблиці «## Ролі» з файлами <роль>.md")
    else:
        m2 = (["файли ролей не існують: " + ", ".join(bad_r)] if bad_r else []) + (["ролі без рядка в таблиці: " + ", ".join(miss_r)] if miss_r else [])
        add("UG-roles", "FAIL" if m2 else "PASS", "; ".join(m2))

    # UG-admin
    ap_ = os.path.join(root, "admin.md")
    adm = open(ap_, encoding="utf-8").read().lower() if os.path.exists(ap_) else ""
    miss = [h for h in ADMIN_HEADERS if not re.search(r"^#{1,4}\s*" + re.escape(h), adm, re.M)]
    add("UG-admin", "FAIL" if (miss or not adm) else "PASS", "немає розділів: " + ", ".join(miss) if (miss or not adm) else "")

    if adm:
        miss_ops = [h for h in ADMIN_OPS if not re.search(r"^#{1,4}\s*" + re.escape(h), adm, re.M)]
        add("UG-admin-ops", "WARN" if miss_ops else "PASS", "немає розділів експлуатації: " + ", ".join(miss_ops) if miss_ops else "")

    # UG-cover-dev / UG-cover-admin (§26а)
    all_txt = {n: open(os.path.join(root, n), encoding="utf-8").read().lower() for n in role_files}
    body = "\n".join(all_txt.values())
    if not a.addons:
        add("UG-cover-dev", "SKIPPED", "немає --addons: покриття розробленого (меню, дії, звіти td_*) перевірити вручну")
    else:
        items = {}
        po = {}  # модуль -> {msgid: msgstr} з i18n/uk.po (назви в XML англійські, посібник — «як у UI», українською); колізії msgid між модулями не змішуються
        for dp, dirs, fs in os.walk(a.addons):
            dirs.sort()
            fs.sort()
            if os.path.basename(dp) == "i18n" and "uk.po" in fs:
                cur, key = {}, None
                pm = po.setdefault(os.path.relpath(dp, a.addons).split(os.sep)[0], {})
                for ln in open(os.path.join(dp, "uk.po"), encoding="utf-8", errors="replace"):
                    ln = ln.strip()
                    m_ = re.match(r'^(msgid|msgstr)\s+"(.*)"$', ln)
                    if m_:
                        key = m_.group(1)
                        if key == "msgid" and "msgstr" in cur:
                            if cur.get("msgid") and cur["msgstr"]:
                                pm[cur["msgid"]] = cur["msgstr"]
                            cur = {}
                        cur[key] = m_.group(2)
                    elif ln.startswith('"') and key:
                        cur[key] = cur.get(key, "") + ln.strip('"')
                if cur.get("msgid") and cur.get("msgstr"):
                    pm[cur["msgid"]] = cur["msgstr"]
        for dp, dirs, fs in os.walk(a.addons):
            dirs.sort()
            fs.sort()
            rel = os.path.relpath(dp, a.addons).split(os.sep)  # лише компоненти ПІСЛЯ кореня --addons: шлях до addons (demo-x, tests) не фільтрується
            mod = rel[0]
            if not mod.startswith("td_") or re.search(r"_(elearning|demo)$", mod) or "tests" in rel[1:] or "demo" in rel[1:]:
                continue
            for f in fs:
                if not f.endswith(".xml"):
                    continue
                try:
                    tree = ET.parse(os.path.join(dp, f))
                except (ET.ParseError, OSError):
                    continue
                for el in tree.iter():
                    nm = None
                    if el.tag == "menuitem" and el.get("name"):
                        nm = el.get("name")
                    elif el.tag == "record" and el.get("model") in ("ir.ui.menu", "ir.actions.act_window", "ir.actions.report"):
                        for fl in el.findall("field"):
                            if fl.get("name") == "name" and (fl.text or "").strip():
                                nm = fl.text.strip()
                    if nm and not nm.startswith("%"):
                        items.setdefault(nm, mod)
        def trs(n, m):  # переклади msgid: спершу модуля-власника меню, потім решта модулів (запасний варіант)
            own = po.get(m, {}).get(n)
            rest = [po[k][n] for k in sorted(po) if k != m and n in po[k]]
            return ([own] if own else []) + [t for t in rest if t != own]
        def named(n, m):  # ціле слово/фраза: вихідна назва або будь-який переклад із uk.po
            for v in [n] + trs(n, m):
                if v and re.search(r"(?<!\w)" + re.escape(v.lower()) + r"(?!\w)", body):
                    return True
            return False
        def shown(n, m):
            t = (trs(n, m) or [None])[0]
            return f"{m}: «{n}»" + (f" → «{t}»" if t and t != n else "")
        miss = sorted(shown(n, m) for n, m in items.items() if not named(n, m))
        noidx = [] if re.search(r"(?mi)^##\s*Покриття:\s*розроблене", index) else ["в INDEX немає таблиці «## Покриття: розроблене»"]
        if not items and any(d.startswith("td_") for d in os.listdir(a.addons)):
            noidx.append("не зібрано жодного меню/дії td_* в --addons (перевір шлях)")
        msg = noidx + ([f"немає в посібниках ({len(miss)}; «msgid → переклад uk.po» — вжити переклад): {', '.join(miss)}"] if miss else [])
        add("UG-cover-dev", "FAIL" if msg else "PASS", "; ".join(msg))
        if miss:
            res[-1]["items"] = miss
    if not a.answers and not a.config:
        add("UG-cover-admin", "SKIPPED", "немає --answers/--config: покриття параметрів і налаштувань в admin.md перевірити вручну")
    else:
        adm_txt = all_txt.get("admin.md", "")
        miss = []
        for ap2 in a.answers:
            stack, vp, vp_param = [], None, None

            def flush():
                if vp and vp.lower() not in adm_txt and not (vp_param and vp_param.lower() in adm_txt):
                    miss.append(vp + (f" ({vp_param})" if vp_param else ""))
            lines2 = open(ap2, encoding="utf-8").read().splitlines() if os.path.exists(ap2) else []
            schema_blocks, cur_b = set(), None  # верхні блоки з полем param:/type: у схемі (edition, contract_mode) — не блоки значень
            for ln in lines2:
                mb = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*$", ln)
                if mb:
                    cur_b = mb.group(1)
                elif cur_b and re.match(r"^\s+(param|type)\s*:", ln):
                    schema_blocks.add(cur_b)
            for ln in lines2:
                m_ = re.match(r"^(\s*)([A-Za-z_][\w-]*)\s*:\s*(.*)$", ln)
                if not m_:
                    continue
                ind = len(m_.group(1))
                if ind == 0 and re.fullmatch(r"VP-\d+", m_.group(2)):  # блок схеми VP-NN: лише ідентифікатор або param:, без полів схеми
                    flush()
                    vp, vp_param = m_.group(2), None
                    stack = []
                    continue
                if ind == 0 and m_.group(3).strip() == "" and m_.group(2) in schema_blocks:  # службовий блок схеми (edition:, contract_mode:): як VP, достатньо назви або param:
                    flush()
                    vp, vp_param = m_.group(2), None
                    stack = []
                    continue
                if ind == 0:
                    flush()
                    vp, vp_param = None, None
                if vp and ind > 0:
                    if m_.group(2) == "param":
                        vp_param = m_.group(3).strip().strip("'\"")
                    continue
                while stack and stack[-1][0] >= ind:
                    stack.pop()
                stack.append((ind, m_.group(2)))
                if m_.group(3).strip() not in ("", "|", ">"):  # лише листові ключі не-VP блоків
                    full = ".".join(k for _, k in stack)
                    if full.lower() not in adm_txt and m_.group(2).lower() not in adm_txt:
                        miss.append(full)
            flush()
        if a.config and os.path.exists(a.config):
            for vp in sorted(set(re.findall(r"\bVP-\d+\b", open(a.config, encoding="utf-8").read()))):
                if vp.lower() not in adm_txt:
                    miss.append(vp)
        msg = ([] if re.search(r"(?mi)^##\s*Покриття:\s*налаштування", index) else ["в INDEX немає таблиці «## Покриття: налаштування й експлуатація»"]) \
            + ([f"немає в admin.md ({len(set(miss))}): {', '.join(sorted(set(miss)))}"] if miss else [])
        add("UG-cover-admin", "FAIL" if msg else "PASS", "; ".join(msg))
        if miss:
            res[-1]["items"] = sorted(set(miss))

    for i, why in (("UG-fresh", "знімки на стенді з SHA INDEX — перевіряє агент (журнал зйомки)"),
                   ("UG-ui", "підписи кроків = підписи в UI — агент/рецензент"),
                   ("UG-pii", "на знімках немає чужих даних — агент/рецензент")):
        add(i, "MANUAL", why)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
