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
0.4.1: UG-access (--role-groups plan.md|JSON, --odoo-src: groups меню/кнопок з кроків ролі ⊆ групи ролі), UG-shots (shoot-plan.json + SHOOT-LOG: кадр ролі під логіном ролі, не admin, не прямий URL дії),
  UG-messages (reference/messages.md: усі raise UserError/ValidationError/AccessError з td_* дослівно з uk.po), UG-std-label (назви в шляхах «A → B» лише з uk.po вихідників --odoo-src або td_*),
  UG-cover-buttons (смарт-кнопки й кнопки заголовка td_*), UG-cover-admin поштучно (розділи admin.md з командами, get_param, меню лише для групи).
UG-cover: розділ «Статус: заблоковано дефектом» = FAIL (повернення A-14: крок returned, не done).
Вихід: JSON [{id,status,msg}]. Код повернення 1, якщо є FAIL."""
import argparse, ast, json, os, re, sys
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


# ---------- 0.4.1: спільні помічники (UG-access, UG-shots, UG-messages, UG-std-label, UG-cover-admin) ----------
EXC = {"UserError", "ValidationError", "AccessError"}
STD_DEFAULT_MODULES = ["base", "web", "mail", "base_setup", "base_import", "account", "sale", "stock", "mrp", "purchase", "crm", "project", "product", "uom", "contacts", "hr"]
# Вигадані переклади стандартного меню (LESSONS §28а): без --odoo-src це FAIL, із ним — спершу пошук у uk.po
SUSPECT_LABELS = {
    "технічні": "у меню розробника вживається підпис із uk.po модуля base (перевірити msgid Technical)",
    "системні параметри": "підпис із uk.po base (msgid System Parameters); шлях — у режимі розробника, не «Технічні»",
    "обговорення": "для пошти — «Ел. пошта» (uk.po mail), не «Обговорення»",
}
QUAL = r"блок|галочк\w*|вкладк\w*|кнопк\w*|пол[ея]|розділ|меню|значок|значк\w*|пункт|прапорець|перемикач|сторінк\w*|група|секці\w*"
ACTION_GEAR = re.compile(r"«Дія»[^\n|]{0,60}(імпорт|архів)", re.I)
URL_ACTION = re.compile(r"/odoo/action-|[#?&]action=|/web#")
NEGATION = re.compile(r"не\s+(бачить|бачать|доступн|видно|показу|мож)|недоступн|лише\s+в\s+режим\w*\s+розробника|режим\w*\s+розробника|скасовує\s+керівник|тільки\s+керівник|лише\s+керівник", re.I)
# уточнення про ІНШУ роль чи пояснення назви застосунку: назви в них — не доручення цій ролі
OTHER_ROLE = re.compile(r"\(\s*(?:у|в|для)\s+[^()—–:]{2,40}?\s*[—–:-]\s*[^()]*(?:\([^()]*\)[^()]*)*\)|\(\s*[А-Яа-яІіЇїЄєҐґ'’ ]{3,30}:\s*[^()]*\)|\(\s*стандарт\w*\s+«[^»]*»\s*\)|стандарт\w*\s+«[^»]*»|користувач\w*\s+із\s+групою\s+«[^»]*»|;\s*(?:у|в|для)\s+[^;«»]{2,40}?\s*[—–:]\s*[^;]*", re.I)
ADMIN_LOGIN = re.compile(r"(?i)^(admin|administrator|root|__system__)(@.*)?$")


def step_text(line):
    """Текст доручення кроку: для рядка таблиці — лише клітинка «Дія» (колонку результату/кадру не розбираємо), для нумерованого списку — увесь рядок."""
    if line.lstrip().startswith("|"):
        cells = line.strip().strip("|").split("|")
        return cells[1] if len(cells) > 1 else ""
    return line


def split_fragments(text):
    """Речення/фрагменти за . ; ! ? поза лапками «…»."""
    out, cur, depth = [], "", 0
    for ch in text:
        cur += ch
        if ch == "«":
            depth += 1
        elif ch == "»":
            depth = max(0, depth - 1)
        elif ch in ".;!?" and depth == 0:
            out.append(cur)
            cur = ""
    out.append(cur)
    return [f for f in out if f.strip()]


def step_names(line):
    """Назви «…» кроку, згадані як доручення: фрагменти із запереченням (NEGATION) відкидаються поодинці, а не весь крок."""
    names = []
    for fr in split_fragments(OTHER_ROLE.sub(" ", step_text(line))):
        if NEGATION.search(fr):  # «не бачить», «лише в режимі розробника», «скасовує керівник»: назва згадана як те, чого роль НЕ робить
            continue
        sm = re.search(r"смарт-кнопк\w*", fr, re.I)  # назви після «смарт-кнопки …:» — кнопки, не меню (збіг назви зі стандартним меню — не доручення меню)
        head, tail = (fr[:sm.start()], fr[sm.start():]) if sm else (fr, "")
        names += [(n, False) for n in re.findall(r"«([^»]+)»", head)] + [(n, True) for n in re.findall(r"«([^»]+)»", tail)]
    return names


def unq(s):
    return s.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")


def load_po(path):
    d, cur, key = {}, {}, None
    if not os.path.exists(path):
        return d
    for ln in open(path, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        m = re.match(r'^(msgid|msgstr)\s+"(.*)"$', ln)
        if m:
            if m.group(1) == "msgid" and "msgstr" in cur:
                if cur.get("msgid") and cur["msgstr"]:
                    d[unq(cur["msgid"])] = unq(cur["msgstr"])
                cur = {}
            key = m.group(1)
            cur[key] = m.group(2)
        elif ln.startswith('"') and ln.endswith('"') and key:
            cur[key] = cur.get(key, "") + ln[1:-1]
    if cur.get("msgid") and cur.get("msgstr"):
        d[unq(cur["msgid"])] = unq(cur["msgstr"])
    return d


def td_modules(addons):
    return sorted(m for m in os.listdir(addons) if m.startswith("td_") and not re.search(r"_(elearning|demo)$", m) and os.path.isdir(os.path.join(addons, m)))


def walk_mod(addons, mod, ext):
    for dp, dirs, fs in os.walk(os.path.join(addons, mod)):
        dirs.sort()
        if "tests" in os.path.relpath(dp, os.path.join(addons, mod)).split(os.sep) or "demo" in os.path.relpath(dp, os.path.join(addons, mod)).split(os.sep):
            continue
        for f in sorted(fs):
            if f.endswith(ext):
                yield os.path.join(dp, f)


def qual(mod, ref):
    return ref if "." in ref else f"{mod}.{ref}"


def split_groups(s, mod):
    return [qual(mod, g.strip()) for g in (s or "").split(",") if g.strip() and not g.strip().startswith(("!", "-"))]  # «-grp» у groups= знімає групу, а не вимагає


def parse_security(path, mod, groups):
    """res.groups з XML: id -> {name, implied}"""
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError):
        return
    for rec in tree.iter("record"):
        if rec.get("model") != "res.groups" or not rec.get("id"):
            continue
        g = groups.setdefault(qual(mod, rec.get("id")), {"name": "", "implied": []})
        for fl in rec.findall("field"):
            if fl.get("name") == "name" and (fl.text or "").strip():
                g["name"] = fl.text.strip()
            if fl.get("name") == "implied_ids":
                g["implied"] += [qual(mod, r_) for r_ in re.findall(r"ref\(['\"]([^'\"]+)['\"]\)", fl.get("eval") or "")]
                if fl.get("ref"):
                    g["implied"].append(qual(mod, fl.get("ref")))


_GOP = re.compile(r"Command\.(link|set|unlink|clear)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)|\(\s*(4|6|3|5)\s*(?:,([^()]*(?:\([^()]*\)[^()]*)*))?\)")


def group_ops(ev, mod):
    """eval поля groups_id/group_ids -> [(op, [групи])], op: add (Command.link/(4,id)), set (Command.set/(6,0,[..])), remove (Command.unlink/(3,id)), clear."""
    ops = []
    for m in _GOP.finditer(ev or ""):
        kind = m.group(1) or {"4": "link", "6": "set", "3": "unlink", "5": "clear"}[m.group(3)]
        refs = [qual(mod, r_) for r_ in re.findall(r"ref\(['\"]([^'\"]+)['\"]\)", m.group(2) if m.group(1) else (m.group(4) or ""))]
        ops.append(({"link": "add", "set": "set", "unlink": "remove", "clear": "clear"}[kind], refs))
    if not ops and ev:  # простий список ref(...) без Command — як заміна
        refs = [qual(mod, r_) for r_ in re.findall(r"ref\(['\"]([^'\"]+)['\"]\)", ev)]
        if refs:
            ops.append(("set", refs))
    return ops


def apply_group_ops(cur, ops):
    cur = list(cur)
    for op, gs in ops:
        if op == "add":
            cur += [g for g in gs if g not in cur]
        elif op == "set":
            cur = list(gs)
        elif op == "remove":
            cur = [g for g in cur if g not in gs]
        elif op == "clear":
            cur = []
    return cur


def collect_td_ui(addons):
    """Меню, кнопки й групи модулів td_* з XML: {menus, buttons, groups}."""
    menus, buttons, groups, unresolved, overrides = [], [], {}, [], []
    for mod in td_modules(addons):
        for path in walk_mod(addons, mod, ".xml"):
            parse_security(path, mod, groups)
            try:
                tree = ET.parse(path)
            except (ET.ParseError, OSError):
                continue
            pm = {c: p for p in tree.iter() for c in p}
            for el in tree.iter():
                if el.tag == "menuitem" and el.get("name"):
                    menus.append({"id": qual(mod, el.get("id") or ""), "name": el.get("name"), "parent": qual(mod, el.get("parent")) if el.get("parent") else None,
                                  "groups": split_groups(el.get("groups"), mod), "mod": mod})
                elif el.tag == "record" and el.get("model") == "ir.ui.menu":
                    m = {"id": qual(mod, el.get("id") or ""), "name": None, "parent": None, "groups": [], "mod": mod, "group_ops": None}
                    for fl in el.findall("field"):
                        if fl.get("name") == "name" and (fl.text or "").strip():
                            m["name"] = fl.text.strip()
                        elif fl.get("name") == "parent_id" and fl.get("ref"):
                            m["parent"] = qual(mod, fl.get("ref"))
                        elif fl.get("name") in ("groups_id", "group_ids"):
                            m["group_ops"] = group_ops(fl.get("eval"), mod)
                            m["groups"] = apply_group_ops([], m["group_ops"])
                    if m["name"] and not m["name"].startswith("%"):
                        menus.append(m)
                    elif not m["name"] and m["id"] and m["group_ops"]:  # без name: перевизначення меню (групи стандартного чи чужого меню), у by_name не потрапляє
                        overrides.append(m)
                elif el.tag == "button" and (el.get("string") or el.get("name")):
                    chain, smart, header = [], False, False
                    p_ = pm.get(el)
                    while p_ is not None:
                        if p_.get("name") == "button_box" or "oe_button_box" in (p_.get("class") or ""):
                            smart = True
                        if p_.tag == "header":
                            header = True
                        p_ = pm.get(p_)
                    label = el.get("string")
                    if not label and smart:
                        fl = el.find(".//field[@string]")
                        label = fl.get("string") if fl is not None else None
                        if not label:  # перший НЕпорожній текст серед усіх span (у першому може бути лише <field/>)
                            label = next((t_ for t_ in ("".join(sp.itertext()).strip() for sp in el.iter("span")) if t_), None)
                        if not label:
                            unresolved.append({"mod": mod, "action": el.get("name") or "", "file": os.path.relpath(path, addons)})
                    if label and not label.startswith("%"):
                        buttons.append({"name": label, "groups": split_groups(el.get("groups"), mod), "smart": smart, "header": header, "mod": mod, "action": el.get("name") or ""})
    return {"menus": menus, "buttons": buttons, "groups": groups, "smart_unresolved": unresolved, "menu_overrides": overrides}


def std_modules(a):
    mods = set(STD_DEFAULT_MODULES) | {m for m in a.std_modules.split(",") if m.strip()}
    if a.addons:
        for mod in td_modules(a.addons):
            mp = os.path.join(a.addons, mod, "__manifest__.py")
            try:
                d = ast.literal_eval(open(mp, encoding="utf-8").read())
                mods |= set(d.get("depends", []))
            except (OSError, ValueError, SyntaxError):
                pass
    return sorted(m for m in mods if not m.startswith("td_"))


def std_roots(src):
    return [os.path.join(src, "addons"), os.path.join(src, "odoo", "addons")]


def std_po(a):
    """Усі msgstr uk.po стандартних модулів із --odoo-src (множина підписів у нижньому регістрі) і msgstr -> msgid для підказок."""
    out = {}
    if not a.odoo_src:
        return out
    for m in std_modules(a):
        for r_ in std_roots(a.odoo_src):
            p = os.path.join(r_, m, "i18n", "uk.po")
            if os.path.exists(p):
                for k, v in load_po(p).items():
                    out.setdefault(norm_label(v), v)
                break
    return out


def std_implied(a, groups):
    """Доповнює groups імплікаціями зі security/*.xml стандартних модулів (--odoo-src)."""
    if not a.odoo_src:
        return
    for m in std_modules(a):
        for r_ in std_roots(a.odoo_src):
            sd = os.path.join(r_, m, "security")
            if os.path.isdir(sd):
                for f in sorted(os.listdir(sd)):
                    if f.endswith(".xml"):
                        parse_security(os.path.join(sd, f), m, groups)
                break


def demo_implied(a, groups):
    """Імплікації з демо-шару td_*_demo (напр. base.group_user -> feature-групи): стенд ними користується, UG-access має їх знати."""
    if not a.addons:
        return
    for m in sorted(x for x in os.listdir(a.addons) if re.match(r"td_.*_demo$", x) and os.path.isdir(os.path.join(a.addons, x))):
        for dp, _d, fs in os.walk(os.path.join(a.addons, m)):
            for f in sorted(fs):
                if f.endswith(".xml"):
                    parse_security(os.path.join(dp, f), m, groups)


def mod_installable_ce(a, mod):
    """Модуль td_* ставиться на CE: усі depends є в td_-аддонах чи у вихідниках --odoo-src. EE-мости (depends: helpdesk, quality_control, …) на CE-стенді не встановлені — їхні перевизначення меню не діють."""
    if not a.odoo_src or not a.addons:
        return True
    try:
        deps = ast.literal_eval(open(os.path.join(a.addons, mod, "__manifest__.py"), encoding="utf-8").read()).get("depends", [])
    except (OSError, ValueError, SyntaxError):
        return True
    return all(d.startswith("td_") or any(os.path.isdir(os.path.join(r_, d)) for r_ in std_roots(a.odoo_src)) for d in deps)


def collect_std_menus(a):
    """Меню стандартних модулів із --odoo-src: {id: {id, name, parent, groups, mod}}; для ланцюжка батьків UG-access (LESSONS §28а)."""
    out = {}
    if not a.odoo_src:
        return out
    for m in std_modules(a):
        for r_ in std_roots(a.odoo_src):
            md = os.path.join(r_, m)
            if not os.path.isdir(md):
                continue
            for dp, dirs, fs in os.walk(md):
                dirs[:] = sorted(d for d in dirs if d not in ("tests", "static", "i18n", "demo"))
                for f in sorted(fs):
                    if not f.endswith(".xml"):
                        continue
                    fp = os.path.join(dp, f)
                    try:
                        if "menu" not in open(fp, encoding="utf-8").read():
                            continue
                        tree = ET.parse(fp)
                    except (ET.ParseError, OSError, UnicodeDecodeError):
                        continue
                    for el in tree.iter():
                        if el.tag == "menuitem" and el.get("id"):
                            mid = qual(m, el.get("id"))
                            e = out.setdefault(mid, {"id": mid, "name": None, "parent": None, "groups": [], "mod": m})
                            e["name"] = el.get("name") or e["name"]
                            e["parent"] = qual(m, el.get("parent")) if el.get("parent") else e["parent"]
                            e["groups"] += split_groups(el.get("groups"), m)
                        elif el.tag == "record" and el.get("model") == "ir.ui.menu" and el.get("id"):
                            mid = qual(m, el.get("id"))
                            e = out.setdefault(mid, {"id": mid, "name": None, "parent": None, "groups": [], "mod": m})
                            for fl in el.findall("field"):
                                if fl.get("name") == "name" and (fl.text or "").strip():
                                    e["name"] = fl.text.strip()
                                elif fl.get("name") == "parent_id" and fl.get("ref"):
                                    e["parent"] = qual(m, fl.get("ref"))
                                elif fl.get("name") in ("groups_id", "group_ids"):
                                    e["groups"] = apply_group_ops(e["groups"], group_ops(fl.get("eval"), m))
            break
    return out


def feature_groups(addons):
    """Групи, які вмикає параметр коробки (implied_group у res.config.settings td_*): не ролева вимога, залежать від параметра."""
    out = set()
    for mod in td_modules(addons):
        for fp in walk_mod(addons, mod, ".py"):
            try:
                txt = open(fp, encoding="utf-8").read()
            except OSError:
                continue
            for g in re.findall(r"implied_group\s*=\s*['\"]([\w.]+)['\"]", txt):
                out.add(qual(mod, g))
    return out


def closure(gs, groups):
    seen, stack = set(), list(gs)
    while stack:
        g = stack.pop()
        if g in seen:
            continue
        seen.add(g)
        stack += groups.get(g, {}).get("implied", [])
    return seen


def norm_label(s):
    s = re.sub(r"\s+", " ", s.strip().lower())
    return re.sub(r"[\s….:;,!?]+$", "", s)


INCOMPLETE = re.compile(r"…|\.\.\.|\s\+\s")


def role_groups_map(a, root):
    """-> (роль -> групи, ролі з неповним переліком, джерело). Перше джерело — img/ROLE-GROUPS.json (shoot.mjs читає групи користувача зі стенда);
    далі JSON {роль:[групи]} або plan.md (таблиця: логін у `…@…`, групи у `модуль.group_*`; рядок із «…»/«+» = перелік неповний)."""
    live = os.path.join(root, "img", "ROLE-GROUPS.json")
    if os.path.exists(live):
        try:
            return {k: list(v) for k, v in json.load(open(live, encoding="utf-8")).items()}, set(), "img/ROLE-GROUPS.json (стенд)"
        except ValueError:
            pass
    if not a.role_groups or not os.path.exists(a.role_groups):
        return None, set(), ""
    if a.role_groups.endswith(".json"):
        return {k: list(v) for k, v in json.load(open(a.role_groups, encoding="utf-8")).items()}, set(), os.path.basename(a.role_groups)
    by_login, incompl_login = {}, set()
    for ln in open(a.role_groups, encoding="utf-8"):
        if not ln.strip().startswith("|"):
            continue
        logins = re.findall(r"`([^`@\s]+@[^`\s]+)`", ln)
        gs = [g for g in re.findall(r"`([A-Za-z_0-9]+\.[A-Za-z_0-9]+)`", ln) if "group" in g and "@" not in g]
        for lg in logins:
            by_login.setdefault(lg, set()).update(gs)
            if INCOMPLETE.search(ln):
                incompl_login.add(lg)
    out, inc = {}, set()
    try:
        plan = json.load(open(os.path.join(root, "shoot-plan.json"), encoding="utf-8"))
    except (OSError, ValueError):
        plan = {}
    for r_ in plan.get("roles", []):
        if r_.get("login") in by_login:
            out.setdefault(r_["role"], set()).update(by_login[r_["login"]])
            if r_["login"] in incompl_login:
                inc.add(r_["role"])
    return {k: sorted(v) for k, v in out.items()}, inc, os.path.basename(a.role_groups)


def section(adm, pat):
    """Текст розділів admin.md, заголовок яких збігається з pat, разом із підрозділами."""
    parts = re.split(r"(?m)^(?=#{1,4}\s)", adm)
    out = []
    for i, p in enumerate(parts):
        hm = re.match(r"(#{1,4})\s+(.*)", p)
        if hm and re.search(pat, hm.group(2), re.I):
            lvl, body = len(hm.group(1)), p
            for q in parts[i + 1:]:
                h2 = re.match(r"(#{1,4})\s", q)
                if h2 and len(h2.group(1)) <= lvl:
                    break
                body += q
            out.append(body)
    return "\n".join(out)


def raw_text(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call):
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if name in ("_", "_lt") and node.args:
            return raw_text(node.args[0])
        if name == "format" and isinstance(f, ast.Attribute):  # _("…{}").format(x): дослівний довідник = шаблон
            return raw_text(f.value)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        x, y = raw_text(node.left), raw_text(node.right)
        if x is not None and y is not None:
            return x + y
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):  # _("…%s") % x
        return raw_text(node.left)
    if isinstance(node, ast.JoinedStr):  # f-рядок: константні частини, підстановки -> {}
        return "".join(v.value if isinstance(v, ast.Constant) else "{}" for v in node.values)
    return None


def raw_texts(node):
    """Усі можливі тексти виразу: умовний вираз -> обидві гілки. [] = не визначено."""
    if isinstance(node, ast.IfExp):
        return raw_texts(node.body) + raw_texts(node.orelse)
    t = raw_text(node)
    return [t] if t else []


UNRESOLVED = []  # (файл:рядок) raise td_*, текст якого не визначено: перевірити вручну


def collect_messages(addons):
    """Тексти UserError/ValidationError/AccessError з td_* (без tests/demo/elearning); (файл:рядок, msgid, uk msgstr)."""
    found, helpers, trees = [], set(), []
    del UNRESOLVED[:]
    for mod in td_modules(addons):
        po = load_po(os.path.join(addons, mod, "i18n", "uk.po"))
        for path in walk_mod(addons, mod, ".py"):
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except (SyntaxError, OSError):
                continue
            trees.append((mod, po, path, tree))
            for fn in ast.walk(tree):  # метод-помічник: приймає текст параметром і сам піднімає виняток
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    args = {x.arg for x in fn.args.args}
                    for n in ast.walk(fn):
                        if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call) and getattr(n.exc.func, "id", getattr(n.exc.func, "attr", "")) in EXC and n.exc.args:
                            x = n.exc.args[0]
                            if isinstance(x, ast.Call) and x.args and isinstance(x.args[0], ast.Name) and x.args[0].id in args:
                                helpers.add(fn.name)
                            if isinstance(x, ast.Name) and x.id in args:
                                helpers.add(fn.name)
    for mod, po, path, tree in trees:
        assigns = {}
        for n in ast.walk(tree):
            if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
                s = raw_text(n.value)
                if s:
                    assigns.setdefault(n.targets[0].id, []).append((n.lineno, s))
            msgs, where = [], None
            if isinstance(n, ast.Call) and n.args:
                fnm = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
                if fnm in helpers:
                    msgs, where = raw_texts(n.args[0]), n.lineno
            if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call):
                fnm = n.exc.func.attr if isinstance(n.exc.func, ast.Attribute) else getattr(n.exc.func, "id", "")
                if fnm in EXC and n.exc.args:
                    x = n.exc.args[0]
                    where = n.lineno
                    msgs = raw_texts(x)
                    if not msgs and isinstance(x, ast.Name):
                        prev = [y for y in assigns.get(x.id, []) if y[0] < n.lineno]
                        msgs = [prev[-1][1]] if prev else []
                    if not msgs and not (isinstance(x, ast.Name) and x.id in {a_.arg for f_ in ast.walk(tree) if isinstance(f_, (ast.FunctionDef, ast.AsyncFunctionDef)) and f_.lineno <= n.lineno <= getattr(f_, "end_lineno", 0) for a_ in f_.args.args}):
                        UNRESOLVED.append(f"{os.path.relpath(path, addons)}:{n.lineno}")
            for msg in msgs:
                found.append((f"{os.path.relpath(path, addons)}:{where}", msg, po.get(msg) or ""))
    return found


def get_param_keys(addons):
    keys = {}
    for mod in td_modules(addons):
        for path in walk_mod(addons, mod, ".py"):
            for m in re.finditer(r"get_param\(\s*['\"]([^'\"]+)['\"]", open(path, encoding="utf-8", errors="replace").read()):
                keys.setdefault(m.group(1), mod)
    return keys


def fence_blocks(txt):
    fenced = re.findall(r"```[^\n]*\n(.*?)```", txt, re.S)
    inline = re.findall(r"`([^`\n]+)`", re.sub(r"```[^\n]*\n.*?```", " ", txt, flags=re.S))  # команди й параметри в зворотних лапках (0.4.1)
    return re.sub(r"\\\n\s*", " ", "\n".join(fenced + inline))  # рядки з «\» об'єднано


def admin_must(adm_raw, a, ui, config_dir):
    """Обов'язкові розділи admin.md з виконуваними командами (LESSONS §28/28а). Повертає список пропусків."""
    miss = []
    low = adm_raw.lower()

    def need(name, pat, checks):
        sec = section(adm_raw, pat)
        if not sec:
            miss.append(f"admin/{name}: немає розділу (заголовок ~ «{pat}»)")
            return ""
        sl, code = sec.lower(), fence_blocks(sec).lower()
        for label, rx, in_code in checks:
            hay = code if in_code else sl
            if not re.search(rx, hay):
                miss.append(f"admin/{name}: немає {label}" + (" у блоці коду" if in_code else ""))
        return sec

    sec = need("встановлення", r"встановлен|установк", [
        ("команди odoo-bin -i", r"odoo-bin[^\n]*\s(-i|--init)\b", True), ("addons_path", r"addons[-_]path", False),
        ("--load-language", r"--load-language", True), ("посилання на «Модулі до установки»", r"модулі до установки", False),
        ("межі «конфіг-пакет на базу клієнта застосовує ToDo за B-04»", r"(?s)(?:конфіг-пакет.*todo.*b-04|b-04.*todo.*конфіг-пакет)", False)])
    if sec and config_dir:  # apply.py обмежений test-/demo-/emu- => потрібен рядок AI-NN
        cands_ = [os.path.join(config_dir, "apply.py"), os.path.join(config_dir, "..", "..", "tools", "odoo", "apply.py"), os.path.join("tools", "odoo", "apply.py")]
        ap_ = next((c_ for c_ in cands_ if os.path.exists(c_)), cands_[0])  # скрипт C-00 лежить у tools/odoo/apply.py (0.4.1)
        if os.path.exists(ap_) and re.search(r"(test|demo|emu)-", open(ap_, encoding="utf-8", errors="replace").read()) and not re.search(r"AI-\d+", sec):
            miss.append("admin/встановлення: apply.py обмежений test-/demo-/emu-, потрібен рядок AI-NN про межу «на базу клієнта застосовує ToDo»")
    multi = any(re.search(r"мультикомпан|multi-?company", open(p, encoding="utf-8", errors="replace").read(), re.I) for p in ([a.config] if a.config and os.path.exists(a.config) else [])) \
        or any(re.search(r":\s*['\"]?multi(company)?['\"]?\s*(#.*)?$", open(p, encoding="utf-8", errors="replace").read(), re.M | re.I) for p in a.answers if os.path.exists(p))
    if multi:
        need("мультикомпанія", r"мультикомпан", [("опису компаній", r"компані", False), ("шляху меню або команди", r"→|odoo-bin|```", False)])
    need("безпека", r"безпек", [("паролів", r"парол", False), ("2FA", r"2fa|дво(?:х)?фактор", False), ("list_db", r"list_db", False),
                                ("list_db = False", r"list_db\s*=\s*false", True), ("майстер-пароля", r"майстер-парол|admin_passwd", False), ("ключів інтеграцій", r"ключ", False)])
    sec = need("резервні копії", r"резервн", [("pg_dump", r"pg_dump", True), ("filestore", r"filestore", False), ("відновлення (pg_restore/psql)", r"pg_restore|psql", True),
                                              ("odoo-bin neutralize", r"odoo-bin[^\n]*neutralize", True)])
    if sec:
        t = sec.lower()
        k = t.find("neutralize")
        if k >= 0 and "td_" not in t[k:]:
            miss.append("admin/резервні копії: після neutralize немає ручних кроків td_* (канали обміну, пошта, інтеграції)")
    need("оновлення", r"оновлен", [("-u … --stop-after-init", r"\s-u\s+\S+[^\n]*--stop-after-init|--stop-after-init[^\n]*\s-u\s", True), ("зупинки сервісу", r"systemctl\s+stop|зупин", False)])
    need("пошта", r"пошт", [("web.base.url", r"web\.base\.url", False), ("«Ел. пошта»", r"ел\. пошта", False), ("відправника", r"відправник", False)])
    need("користувачі", r"користувач", [("створення", r"створ", False), ("часового поясу (TZ)", r"\btz\b|часов\w+ пояс", False)])
    if a.addons:
        keys = get_param_keys(a.addons)
        mk = sorted(k for k in keys if k.lower() not in low)
        if mk:
            miss.append("admin/системні параметри (get_param у td_*), немає в admin.md: " + ", ".join(f"{k} ({keys[k]})" for k in mk))
        for m in ui["menus"]:
            # рішення AI (0.4.1): вимога «меню з groups названо в admin.md» — лише для ролевих груп td_*; feature-групи (group_feature_*, вмикаються
            # всім через implied_ids/налаштування) і стандартні групи Odoo (їх описують посібники ролей) не вимагаються; «-група» знімає доступ
            mgroups = [g for g in m["groups"] if g.startswith("td_") and ".group_feature_" not in g]
            if not mgroups:
                continue
            names = {m["name"].lower()}
            tr_ = load_po(os.path.join(a.addons, m["mod"], "i18n", "uk.po")).get(m["name"])
            if tr_:
                names.add(tr_.lower())
            gnames = set()
            for g in mgroups:
                gnames |= {g.lower(), g.split(".")[-1].lower(), (ui["groups"].get(g, {}).get("name") or g).lower()}
                tg = load_po(os.path.join(a.addons, g.split(".")[0], "i18n", "uk.po")).get(ui["groups"].get(g, {}).get("name") or "")
                if tg:
                    gnames.add(tg.lower())
            blocks = [p for p in re.split(r"\n\s*\n|\n(?=\|)", adm_raw.lower()) if any(n in p for n in names)]
            if not any(any(g in p for g in gnames) for p in blocks):
                miss.append(f"admin/меню лише для групи: «{m['name']}» ({m['mod']}) доступне групам {', '.join(mgroups)} — у admin.md немає абзацу чи рядка таблиці з меню і групою")
    return miss



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
    ap.add_argument("--role-groups", help="plan.md стенда (таблиця ролей: логін у `…@…`, групи `модуль.group_*`) або JSON {роль: [групи]}: UG-access")
    ap.add_argument("--odoo-src", help="корінь вихідників Odoo 19.0 (addons/, odoo/addons/base): uk.po і security стандартних модулів для UG-std-label, UG-access")
    ap.add_argument("--std-modules", default="", help="додаткові стандартні модулі для UG-std-label (через кому)")
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
        adm_pth = os.path.join(root, "admin.md")
        if os.path.exists(adm_pth):
            miss += admin_must(open(adm_pth, encoding="utf-8").read(), a, collect_td_ui(a.addons) if a.addons else {"menus": [], "buttons": [], "groups": {}}, os.path.dirname(a.config) if a.config else None)
        msg = ([] if re.search(r"(?mi)^##\s*Покриття:\s*налаштування", index) else ["в INDEX немає таблиці «## Покриття: налаштування й експлуатація»"]) \
            + ([f"немає в admin.md ({len(set(miss))}): {', '.join(sorted(set(miss)))}"] if miss else [])
        add("UG-cover-admin", "FAIL" if msg else "PASS", "; ".join(msg))
        if miss:
            res[-1]["items"] = sorted(set(miss))

    ui_all = collect_td_ui(a.addons) if a.addons else {"menus": [], "buttons": [], "groups": {}}

    # UG-cover-buttons: смарт-кнопки (button_box) і кнопки заголовка форм td_* названо в посібниках (LESSONS §28 п. 3)
    if not a.addons:
        add("UG-cover-buttons", "SKIPPED", "немає --addons: смарт-кнопки й кнопки заголовка перевірити вручну")
    else:
        po_by = {m: load_po(os.path.join(a.addons, m, "i18n", "uk.po")) for m in td_modules(a.addons)}

        def bnamed(b):
            for v in {b["name"], po_by.get(b["mod"], {}).get(b["name"]) or b["name"]}:
                if re.search(r"(?<!\w)" + re.escape(v.lower()) + r"(?!\w)", body):
                    return True
            return False
        sm_miss = sorted({f"{b['mod']}: «{b['name']}»" for b in ui_all["buttons"] if b["smart"] and not bnamed(b)})
        hd_miss = sorted({f"{b['mod']}: «{b['name']}»" for b in ui_all["buttons"] if b["header"] and not b["smart"] and not bnamed(b)})
        unres = sorted({f"{u['file']}, name={u['action']}" for u in ui_all.get("smart_unresolved", [])})
        msg = ([f"смарт-кнопки без опису дії ({len(sm_miss)}): {', '.join(sm_miss)}"] if sm_miss else [])
        add("UG-cover-buttons", "FAIL" if msg else ("WARN" if (hd_miss or unres) else "PASS"),
            "; ".join(msg + ([f"кнопки заголовка форм без згадки ({len(hd_miss)}): {', '.join(hd_miss)}"] if hd_miss else [])
                      + ([f"підпис смарт-кнопки не визначено, покриття не перевірено ({len(unres)}): {'; '.join(unres)}"] if unres else [])))

    # UG-access: groups меню/кнопок, названих у кроках ролі, ⊆ групи ролі (LESSONS §28а). Недоступне = дефект (A-11/A-12), не обхід текстом
    rg, rg_incomplete, rg_src = role_groups_map(a, root)
    if not a.role_groups and rg is None:
        add("UG-access", "SKIPPED", "немає img/ROLE-GROUPS.json (shoot.mjs) і --role-groups (plan.md стенда або JSON): права ролей перевірити вручну")
    elif rg is None:
        add("UG-access", "FAIL", f"--role-groups {a.role_groups} не існує")
    elif not a.addons:
        add("UG-access", "SKIPPED", "немає --addons: groups меню й кнопок не зібрано")
    else:
        groups = dict(ui_all["groups"])
        std_implied(a, groups)
        demo_implied(a, groups)
        po_by = {m: load_po(os.path.join(a.addons, m, "i18n", "uk.po")) for m in td_modules(a.addons)}
        by_name, menu_by_id = {}, {}
        feat_g = feature_groups(a.addons)
        std_menus = collect_std_menus(a)
        for sm in std_menus.values():  # стандартні меню: батьки td_-меню та назви в шляхах «A → B»
            menu_by_id.setdefault(sm["id"], sm)
            if sm["name"]:
                for v in {sm["name"], load_po(os.path.join(a.odoo_src, "addons", sm["mod"], "i18n", "uk.po")).get(sm["name"]) if os.path.exists(os.path.join(a.odoo_src, "addons", sm["mod"], "i18n", "uk.po")) else None} - {None}:
                    by_name.setdefault(v.lower(), []).append(("меню", sm))
        for m in ui_all["menus"]:
            if m["id"] in std_menus:
                if mod_installable_ce(a, m["mod"]):
                    std_menus[m["id"]]["groups"] = apply_group_ops(std_menus[m["id"]]["groups"], m.get("group_ops") or [("add", m["groups"])])
            else:
                menu_by_id[m["id"]] = m
            for v in {m["name"], po_by.get(m["mod"], {}).get(m["name"]) or m["name"]}:
                by_name.setdefault(v.lower(), []).append(("меню", m))
        for o in ui_all.get("menu_overrides", []):  # записи ir.ui.menu без name: link/(4,id) додає, set/(6,0,[..]) замінює, unlink/(3,id) знімає групу
            tgt = std_menus.get(o["id"]) or menu_by_id.get(o["id"])
            if tgt is not None and mod_installable_ce(a, o["mod"]):
                tgt["groups"] = apply_group_ops(tgt["groups"], o["group_ops"])
        for b in ui_all["buttons"]:
            for v in {b["name"], po_by.get(b["mod"], {}).get(b["name"]) or b["name"]}:
                by_name.setdefault(v.lower(), []).append(("кнопка", b))

        def reach(item, kind, rg_):
            chain, cur, seen = [], item, set()
            while cur is not None and id(cur) not in seen:
                seen.add(id(cur))
                chain.append(cur)
                cur = menu_by_id.get(cur.get("parent")) if kind == "меню" else None
            unmet = [g for c in chain if c["groups"] and not (set(c["groups"]) & rg_) for g in c["groups"]]
            return not unmet, [g for c in chain for g in c["groups"]], unmet
        bad, warn_roles, warn_inc, warn_feat = [], [], [], []
        from_stand = not rg_src.endswith(".md")  # plan.md = джерело не зі стенда
        for n in role_files:
            if n == "admin.md":
                continue
            role = n[:-3]
            if role not in rg:
                warn_roles.append(role)
                continue
            # base.group_user (і його implied_ids, зокрема feature-групи демо-шару) мають усі; base.group_no_one — режим розробника, у кроках не доручається
            rg_ = closure(list(rg[role]) + ["base.group_user", "base.group_no_one"], groups)
            for i, line in enumerate(open(os.path.join(root, n), encoding="utf-8").read().splitlines(), 1):
                if not STEP_LINE.match(line):
                    continue
                for nm, btn_only in step_names(line):
                    cands = [c_ for c_ in (by_name.get(nm.strip().lower()) or []) if not btn_only or c_[0] == "кнопка"]
                    if not cands:
                        continue
                    res_ = [(k, it) + reach(it, k, rg_) for k, it in cands]
                    if not any(r_[2] for r_ in res_):
                        k, it, _ok, need_g, unmet_g = res_[0]
                        msg_ = f"{n}:{i} «{nm}» ({k} {it.get('id') or it.get('action')}, {it['mod']}) потребує {', '.join(sorted(set(need_g)))}; групи ролі {role}: {', '.join(sorted(rg[role])) or '—'}"
                        if unmet_g and all(g in feat_g or ".group_feature_" in g for g in unmet_g):
                            warn_feat.append(f"{n}:{i} «{nm}» ({', '.join(sorted(set(unmet_g)))})")
                        elif role in rg_incomplete:  # лише рядки plan.md з «…»/«+»; plan.md без «…» — запасне джерело, але порушення = FAIL (0.4.1)
                            warn_inc.append(msg_)
                        elif msg_ not in bad:
                            bad.append(msg_)
        if bad and not from_stand:  # plan.md — запасне джерело: FAIL має дві можливі причини
            route = f"джерело груп — {rg_src} (запасне, може бути застарілим): причини дві — (1) права справді не видано в коді/конфігу, (2) plan.md не збігається зі стендом; спершу зніміть img/ROLE-GROUPS.json зі стенда (shoot.mjs) і повторіть, на A-11/A-12 повертайте лише коли FAIL підтверджено групами зі стенда"
        else:
            route = "дефект у defects.md і повернення A-11/A-12 (код/права), не обхід текстом"
        msg = ([f"крок доручає ролі те, чого роль не бачить (усього {len(bad)}): " + "; ".join(bad) + " — " + route] if bad else []) \
            + ([f"немає груп для ролей: {', '.join(warn_roles)} (додайте в {os.path.basename(rg_src)})"] if warn_roles else []) \
            + ([f"функції коробки (група вмикається параметром, не роллю; перевірте VP; усього {len(set(warn_feat))}): " + "; ".join(sorted(set(warn_feat)))] if warn_feat else []) \
            + ([f"перелік груп неповний («…»/«+» у plan.md; джерело {rg_src}), можливі пропуски (усього {len(set(warn_inc))}): " + "; ".join(sorted(set(warn_inc))) + " — зніміть групи зі стенда (shoot.mjs → img/ROLE-GROUPS.json)"] if warn_inc or rg_incomplete else []) \
            + ([f"групи взято не зі стенда ({rg_src}): img/ROLE-GROUPS.json відсутній — зніміть його shoot.mjs, інакше перевірка прав запасна"] if not from_stand else [])
        add("UG-access", "FAIL" if bad else ("WARN" if (warn_roles or warn_inc or rg_incomplete or not from_stand) else "PASS"), "; ".join(msg))
        if bad or warn_inc or warn_feat:
            res[-1]["items"] = bad + sorted(set(warn_inc)) + sorted(set(warn_feat))

    # UG-shots: кожен кадр ролі знято, увійшовши під користувачем ролі: не адміністратор, не прямий URL дії (LESSONS §28а)
    plan_p = os.path.join(root, "shoot-plan.json")
    has_png = bool(on_disk)
    if not os.path.exists(plan_p):
        add("UG-shots", "FAIL" if has_png else "SKIPPED", "немає shoot-plan.json: кадри ролей знімає scripts/shoot.mjs під логіном ролі" if has_png else "знімків немає")
    else:
        bad = []
        try:
            plan = json.load(open(plan_p, encoding="utf-8"))
        except ValueError as e:
            plan, bad = {}, [f"shoot-plan.json не JSON: {e}"]
        plan_roles = {r_.get("role"): r_ for r_ in plan.get("roles", [])}
        for role, r_ in plan_roles.items():
            lg = r_.get("login", "")
            if role != "admin" and (not lg or ADMIN_LOGIN.match(lg)):
                bad.append(f"роль {role}: логін «{lg}» — кадри ролі не знімаються адміністратором")
            for s in r_.get("shots", []):
                if role != "admin" and (s.get("url") or "").split("?")[0].rstrip("/") not in ("", "/odoo", "/web"):  # рішення AI (0.4.1): прямі URL дозволені лише кадрам admin
                    bad.append(f"{role} {s.get('sc')}-{s.get('step')}: прямий URL дії {s.get('url')} — навігація кліками меню з /odoo (поле menu)")
        log_p = os.path.join(root, "img", "SHOOT-LOG.md")
        rows = {}
        if os.path.exists(log_p):
            for ln in open(log_p, encoding="utf-8"):
                c = [x.strip() for x in ln.strip().strip("|").split("|")]
                if len(c) >= 4 and re.search(r"img/[^/\s]+/[^/\s]+\.(png|jpe?g|webp)$", c[0], re.I):
                    rows[re.search(r"img/([^/\s]+/[^/\s]+)$", c[0]).group(1)] = c
        for f in sorted(os.path.relpath(x, os.path.join(root, "img")).replace(os.sep, "/") for x in on_disk):
            role = f.split("/")[0]
            c = rows.get(f)
            if not c:
                bad.append(f"{f}: немає рядка в SHOOT-LOG.md (знято не shoot.mjs)")
            elif len(c) < 6:
                bad.append(f"{f}: у SHOOT-LOG.md немає стовпця «Логін» (журнал старого формату; знімати shoot.mjs 0.4.1)")
            elif role != "admin" and ADMIN_LOGIN.match(c[5].strip("`")):
                bad.append(f"{f}: знято під адміністратором ({c[5]})")
            elif plan_roles.get(role, {}).get("login") and c[5].strip("`") != plan_roles[role]["login"]:
                bad.append(f"{f}: у журналі логін {c[5]} не збігається з логіном ролі в shoot-plan.json")
            if plan_roles and role not in plan_roles:
                bad.append(f"{f}: ролі {role} немає в shoot-plan.json")
        nolog = [x for x in bad if "немає стовпця «Логін»" in x]
        rest = [x for x in bad if x not in nolog]
        if nolog:  # журнал старого формату — одним рядком, щоб не витісняв інші порушення
            rest.append(f"SHOOT-LOG.md старого формату (немає стовпця «Логін») у {len(nolog)} кадрів, напр. {nolog[0].split(':')[0]}: знімати shoot.mjs 0.4.1")
        add("UG-shots", "FAIL" if bad else "PASS", (f"усього порушень {len(rest)}: " if rest else "") + "; ".join(rest[:10]) + (f" … (показано 10 з {len(rest)}, повний перелік — items)" if len(rest) > 10 else ""))
        if rest:
            res[-1]["items"] = rest

    # UG-messages: довідник reference/messages.md — усі UserError/ValidationError/AccessError з td_* дослівно (msgstr uk.po); посібники на нього посилаються
    if not a.addons:
        add("UG-messages", "SKIPPED", "немає --addons: довідник повідомлень перевірити вручну")
    else:
        found = collect_messages(a.addons)
        mp = os.path.join(root, "reference", "messages.md")
        mbody = open(mp, encoding="utf-8").read() if os.path.exists(mp) else ""
        bad, warn = [], []
        if found and not mbody:
            bad.append("немає reference/messages.md")
        norm = lambda s: re.sub(r"\s+", " ", s.replace("|", "/").replace("\n", " ")).strip()
        nb = norm(mbody)
        miss_m = sorted({f"{src}: «{uk or m_}»" for src, m_, uk in found if "«" + norm(uk or m_) + "»" not in nb})
        if miss_m:
            bad.append(f"немає в messages.md ({len(miss_m)} з {len(found)}): " + "; ".join(miss_m[:8]))
        for ln in mbody.splitlines():  # рядок довідника: текст | коли | що робити | хто виправляє (| джерело)
            if ln.startswith("|") and "«" in ln:
                c = [x.strip() for x in ln.strip().strip("|").split("|")]
                if len(c) < 4 or any(not x for x in c[:4]):
                    bad.append(f"неповний рядок довідника (текст, коли, що робити, хто виправляє): {ln[:60]}")
                    break
        nolink = [n for n in role_files if "reference/messages.md" not in open(os.path.join(root, n), encoding="utf-8").read()]
        if found and nolink:
            bad.append("немає посилання на reference/messages.md у: " + ", ".join(nolink))
        untr = sorted({f"{src}" for src, m_, uk in found if not uk})
        if untr:
            warn.append(f"повідомлення без перекладу в uk.po ({len(untr)}): дефект перекладу пакета -> defects.md, напр. " + ", ".join(untr[:3]))
        if UNRESOLVED:
            warn.append(f"текст raise не визначено автоматично ({len(UNRESOLVED)}): перевірити вручну, чи є в messages.md: " + ", ".join(UNRESOLVED))
        if not found:
            add("UG-messages", "WARN", "у td_* не знайдено raise UserError/ValidationError/AccessError (перевірити шлях --addons)")
        else:
            add("UG-messages", "FAIL" if bad else ("WARN" if warn else "PASS"), "; ".join(bad + warn))

    # UG-std-label: назви стандартного UI Odoo 19 у шляхах меню — лише з msgstr uk.po вихідників 19.0 (LESSONS §28а)
    stdset = std_po(a) if a.odoo_src else {}
    own = set()
    if a.addons:
        for m_ in td_modules(a.addons):
            for k_, v_ in load_po(os.path.join(a.addons, m_, "i18n", "uk.po")).items():
                own |= {norm_label(k_), norm_label(v_)}
        own |= {norm_label(x["name"]) for x in ui_all["menus"] + ui_all["buttons"]}
    extra = set()
    for ln in index.splitlines():
        m2 = re.match(r"\s*Дозволені назви UI:\s*(.+)", ln)
        if m2:
            extra |= {norm_label(x) for x in re.split(r"[;,]", m2.group(1)) if x.strip()}
    paths = []
    for n in role_files:
        for i, line in enumerate(open(os.path.join(root, n), encoding="utf-8").read().splitlines(), 1):
            if ACTION_GEAR.search(line):
                paths.append((n, i, "«Дія»", "імпорт/архівація в Odoo 19 викликаються значком шестерні (⚙) у списку або формі, не пунктом «Дія»; підпис значка — з uk.po web", None))
            if not re.search(r"→|›|->|&gt;", line):
                continue
            ctx_ = lambda seg: "для пошти підпис — «Ел. пошта» (uk.po mail/base), «Обговорення» — назва застосунку Discuss" if norm_label(seg) == "обговорення" and re.search(r"пошт|лист|smtp", line, re.I) else None
            seen_ = set()
            # (а) «A» → «B»: кожен сегмент у власних лапках; (б) «A → B → C»: уся стежка в одній парі лапок (формат шаблону)
            for seg_line in re.findall(r"«[^»]+»(?:\s*(?:→|›|->|>)\s*«[^»]+»)+", line):
                segs_a = re.findall(r"«([^»]+)»", seg_line)
                if all(re.fullmatch(r"[A-Za-z0-9 ._-]+", x_) for x_ in segs_a):
                    continue
                for seg in segs_a:
                    paths.append((n, i, seg, ctx_(seg), None))
                    seen_.add(seg)
            for q in re.findall(r"«([^»]+)»|`([^`\n]+)`|\*\*([^*\n]+)\*\*", line):
                q = next(x for x in q if x)
                if re.search(r"→|›|->|&gt;", q):
                    segs_q = re.split(r"\s*(?:→|›|->|&gt;|>)\s*", q)
                    if all(re.fullmatch(r"[A-Za-z0-9 ._-]+", x_.strip()) for x_ in segs_q if x_.strip()):
                        continue  # назва напряму/профілю («Odoo → BAS», «A → B»), не шлях меню
                    segs_q = [re.split(r"[(:]\s*", x_)[-1] if k_ == 0 else (re.split(r"\)", x_)[0] if k_ == len(segs_q) - 1 else x_) for k_, x_ in enumerate(segs_q)]
                    for seg in segs_q:
                        if seg.strip() and seg not in seen_:
                            paths.append((n, i, seg.strip(), ctx_(seg), None))
                            seen_.add(seg)
            # (г) гібрид «A» → блок «B» → галочка «C»: сегмент — лише текст у «…» (слова-уточнення відкидаємо), не уривки речення;
            # (в) стежка без лапок «відкрийте Налаштування → Технічні → Системні параметри» — лише для ланцюжка без лапок поза дужками;
            # рядок спершу ділимо на речення/«;», стрілки всередині лапок маскуємо ((б) їх уже розібрав)
            mask_ = lambda m_: re.sub(r"→|›|->|&gt;|>", "\x00", m_.group(0))
            for clause in re.split(r";|\.\s+(?=[А-ЯІЇЄA-Z«])", line):
                cm = re.sub(r"«[^»]*»|`[^`\n]*`|\*\*[^*\n]*\*\*", mask_, clause)
                arrows = [m_ for m_ in re.finditer(r"→|›", cm)]
                if not arrows:
                    continue
                if "«" in cm:
                    chain = re.split(r"\s*(?:→|›)\s*", cm)
                    for k, part in enumerate(chain):
                        if k == 0:
                            mq = re.search(r"(?:%s)?\s*«([^»]+)»\s*$" % QUAL, part, re.I)
                        elif k == len(chain) - 1:
                            mq = re.match(r"\s*(?:%s)?\s*«([^»]+)»" % QUAL, part, re.I)
                        else:
                            mq = re.fullmatch(r"\s*(?:%s)?\s*«([^»]+)»\s*" % QUAL, part, re.I)
                        if mq and mq.group(1) not in seen_:
                            paths.append((n, i, mq.group(1).strip(), ctx_(mq.group(1)), None))
                            seen_.add(mq.group(1))
                    continue
                depth_in = False
                for m_ in arrows:
                    pre = cm[:m_.start()]
                    if pre.count("(") > pre.count(")"):
                        depth_in = True
                bw_ = [(re.findall(r"[\w.-]+", cm[:m_.start()]) or [""])[-1] for m_ in arrows] + [(re.findall(r"[\w.-]+", cm[m_.end():]) or [""])[0] for m_ in arrows]
                if depth_in or all(re.fullmatch(r"[A-Za-z0-9._-]*", w_) for w_ in bw_):
                    continue  # заголовок таблиці-довідника, «A → B» як позначення профілів, пояснення в дужках — не шлях меню
                plain = re.sub(r"[`*\"]", "", cm)
                parts = re.split(r"\s*(?:→|›)\s*", plain)
                if any(x_[:1].islower() for x_ in parts[1:-1]):
                    continue  # перелік порядку дій малими літерами («категорії → контрагенти → …»), назви меню пишуться з великої
                if len(parts) >= 2:
                    head = re.split(r"[:;,(|]\s*", parts[0])[-1].strip()
                    tail = re.split(r"[,;:)|]|\.\s*$|\.\s+(?=[А-ЯІЇЄA-Z])|\s+(?:і|та|потім|далі|щоб)\s", parts[-1])[0].strip()
                    segs = [head] + [x.strip() for x in parts[1:-1]] + [tail]
                    for k, seg in enumerate(segs):
                        if not seg:
                            continue
                        w = seg.split()
                        if k == 0:
                            vars_ = [" ".join(w[-m:]) for m in range(1, min(4, len(w)) + 1)]
                        elif k == len(segs) - 1:
                            vars_ = [" ".join(w[:m]) for m in range(1, min(5, len(w)) + 1)]
                        else:
                            vars_ = [seg]
                        paths.append((n, i, seg, ctx_(seg), vars_))
    bad = []
    for n, i, seg, why, vars_ in paths:
        if why:
            bad.append(f"{n}:{i} {seg} — {why}")
            continue
        s = norm_label(seg)
        vs = [norm_label(v) for v in (vars_ or [seg])]
        if vars_:
            seg = vars_[0]  # у звіті — найкоротший варіант (без дієслова/продовження речення)
            s = norm_label(seg)
        if re.search(r"[<{]", seg) or not s or any(v in extra or v in own or v in stdset for v in vs):
            continue
        if any(v in SUSPECT_LABELS for v in vs) and not a.odoo_src:
            s = next(v for v in vs if v in SUSPECT_LABELS)
        if s in SUSPECT_LABELS and not a.odoo_src:
            bad.append(f"{n}:{i} «{seg}» — вигаданий переклад? {SUSPECT_LABELS[s]}; без --odoo-src підтвердити не можна")
        elif a.odoo_src:
            import difflib
            near = difflib.get_close_matches(s, list(stdset), n=1, cutoff=0.6)
            bad.append(f"{n}:{i} «{seg}» немає в uk.po вихідників 19.0 і td_*" + (f" (схоже: «{stdset[near[0]]}»)" if near else ""))
    if not paths:
        add("UG-std-label", "PASS" if a.odoo_src else "SKIPPED", "шляхів меню «A → B» у посібниках немає")
    elif bad:
        ub_ = sorted(set(bad))
        add("UG-std-label", "FAIL", (f"усього {len(ub_)}: " if ub_ else "") + "; ".join(ub_[:10]) + (f" … (показано 10 з {len(ub_)}, повний перелік — items)" if len(ub_) > 10 else ""))
        if len(ub_) > 10:
            res[-1]["items"] = ub_
    elif not a.odoo_src:
        add("UG-std-label", "WARN", "немає --odoo-src: перевірено лише список підозрілих назв, не повну звірку з uk.po 19.0")
    else:
        add("UG-std-label", "PASS", f"{len({p[2] for p in paths})} назв у шляхах меню знайдено в uk.po 19.0 / td_*")

    for i, why in (("UG-fresh", "знімки на стенді з SHA INDEX — перевіряє агент (журнал зйомки)"),
                   ("UG-ui", "підписи кроків = підписи в UI — агент/рецензент"),
                   ("UG-pii", "на знімках немає чужих даних — агент/рецензент")):
        add(i, "MANUAL", why)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


if __name__ == "__main__":
    main()
