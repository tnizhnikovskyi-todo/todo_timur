#!/usr/bin/env python3
"""Збирання контексту входів кроку за SHA з фільтром DATA_POLICY (flow-step-runner, крок 6).

Запуск:
  python3 -I build_context.py --repo <тека> --inputs inputs.json --policy policy.md --out <тека> --budget <токенів>
        [--sections <name>=<regex заголовків>]...   звуження: лишити лише розділи, заголовок яких збігається з regex
        [--toc]                                     лише оглавлення (зміст не пишеться), див. нижче
        [--chars-per-token 4.0]                     дільник для латиниці; для кирилиці береться ~2.2 автоматично
inputs.json: [{"name","from","path","sha"}]. Лише stdlib.
Код виходу: 0 ок; 2 нема SHA/файлу; 3 політика не розібрана; 4 вхід заборонений політикою або клас «знеособлено» без
ознаки знеособленої копії; 5 понад бюджет; 6 `--sections` не знайшов розділу або name не збігається з name входу. У stdout — JSON-маніфест
(шляхи, класи, токени, data_sources); зміст входів не друкується. При коді 0 маніфест пишеться також у <out>/manifest.json;
при коді 5 файли в --out видаляються. Рядок </untrusted> у тексті входу замінюється на екранований.

Припущення (Відкрите питання, узгодити з data-policy-template.md): у розділі «Дозволено передавати в AI» є таблиця
`| шлях-glob | дозволено|знеособлено|заборонено |`; перший збіг рядка згори вниз виграє; немає збігу -> заборонено.
Знеособлена копія (клас «знеособлено»): шлях містить сегмент `anon/` (напр. `clients/<id>/anon/…`) АБО в перших 15 рядках
файлу є маркер `anonymized: true` / `знеособлено: так`. Немає ознаки -> код 4. Фактичне знеособлення перевіряє C-05
(`pii-patterns.md`); скрипт перевіряє лише наявність ознаки, а не якість.

Недовіреність: вхід `from: клієнт`, шлях у `clients/`, назва містить transcript/транскрипт/letters/листи/email/mail/meeting/зустріч,
а також будь-який вхід класу «знеособлено» -> обгортка <untrusted>.
`--toc`: JSON з розділами кожного входу {title, level, tokens}. Для недовірених входів тексти заголовків НЕ друкуються
(лише кількість і токени) — заголовок документа клієнта теж дані клієнта; звужувати їх треба regex, складеним із `done`/шаблону.
"""
import argparse, fnmatch, json, math, os, re, shutil, subprocess, sys

HEAD = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
UNTRUSTED_NAME = re.compile(r"transcript|транскрипт|letters|листи|лист_|email|mail|meeting|зустріч", re.I)
ANON_MARK = re.compile(r"anonymized\s*:\s*true|знеособлено\s*:\s*(так|true)", re.I)

def sh(repo, *a):
    return subprocess.run(["git", "-C", repo, *a], capture_output=True)

def load_policy(path):
    txt = open(path, encoding="utf-8").read()
    m = re.search(r"^#+\s*Дозволено передавати в AI\s*$(.*?)(?=^#+\s|\Z)", txt, re.S | re.M)
    rules = []
    for line in (m.group(1) if m else "").splitlines():
        c = [x.strip().strip("`") for x in line.strip().strip("|").split("|")]
        if len(c) >= 2 and c[1].lower() in ("дозволено", "знеособлено", "заборонено"):
            rules.append((c[0], c[1].lower()))
    return rules

def klass(rules, path):
    for g, k in rules:
        if fnmatch.fnmatch(path, g):
            return k
    return "заборонено"

def tokens(text, latin_cpt):
    """Кирилиця ~2.2 символа на токен, латиниця ~latin_cpt; +10% запасу."""
    if not text:
        return 0
    cyr = sum(1 for ch in text if "Ѐ" <= ch <= "ӿ") / len(text)
    cpt = latin_cpt * (1 - cyr) + 2.2 * cyr
    return math.ceil(len(text) / cpt * 1.1)

def sections(text):
    """[(level, title, start_line, end_line)] за markdown-заголовками; розділ триває до заголовка того ж або вищого рівня."""
    lines = text.splitlines(keepends=True)
    heads = [(i, len(m.group(1)), m.group(2)) for i, l in enumerate(lines) if (m := HEAD.match(l))]
    res = []
    for n, (i, lvl, title) in enumerate(heads):
        end = len(lines)
        for j, l2, _ in heads[n + 1:]:
            if l2 <= lvl:
                end = j
                break
        res.append((lvl, title, i, end))
    return lines, res

def narrow(text, regex):
    lines, secs = sections(text)
    keep = [s for s in secs if re.search(regex, s[1], re.I)]
    picked, last_end = [], -1
    for lvl, title, a, b in keep:       # вкладені розділи не дублюємо
        if a >= last_end:
            picked.append("".join(lines[a:b]))
            last_end = b
    return "\n".join(picked) if picked else None

def main():
    p = argparse.ArgumentParser()
    for k in ("repo", "inputs", "policy", "out"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--budget", type=int, required=True)
    p.add_argument("--sections", action="append", default=[], metavar="NAME=REGEX")
    p.add_argument("--toc", action="store_true")
    p.add_argument("--chars-per-token", type=float, default=4.0)
    a = p.parse_args()
    narrowing = dict(s.split("=", 1) for s in a.sections)
    rules = load_policy(a.policy)
    if not rules:
        print(json.dumps({"error": "DATA_POLICY: таблицю фільтра не розібрано"}), file=sys.stderr); return 3
    os.makedirs(a.out, exist_ok=True)
    items, total, toc = [], 0, []
    inputs = json.load(open(a.inputs, encoding="utf-8"))
    known = {i.get("name") for i in inputs if isinstance(i, dict)}
    for n in narrowing:
        if n not in known:  # ім'я з --sections має збігатися з name входу, інакше звуження мовчки не спрацює
            print(json.dumps({"error": "--sections: немає входу з таким name", "input": n}, ensure_ascii=False), file=sys.stderr); return 6
    for i in inputs:
        if not isinstance(i, dict) or not i.get("name") or not i.get("path"):
            print(json.dumps({"error": "запис входу без обов'язкових ключів name/path", "input": str(i)[:200]}), file=sys.stderr); return 2
        sha, path = i.get("sha"), i["path"]
        if not sha or sh(a.repo, "cat-file", "-e", sha).returncode:
            print(json.dumps({"error": "немає SHA або коміт відсутній", "input": i["name"]}), file=sys.stderr); return 2
        r = sh(a.repo, "show", f"{sha}:{path}")
        if r.returncode:
            print(json.dumps({"error": "файл відсутній на SHA", "input": i["name"]}), file=sys.stderr); return 2
        k = klass(rules, path)
        if k == "заборонено":
            print(json.dumps({"error": "вхід заборонений політикою", "input": i["name"]}), file=sys.stderr); return 4
        text = r.stdout.decode("utf-8", "replace")
        if k == "знеособлено":
            head = "\n".join(text.splitlines()[:15])
            if not ("/anon/" in "/" + path or ANON_MARK.search(head)):
                print(json.dumps({"error": "клас «знеособлено» без ознаки знеособленої копії (anon/ або маркер у шапці)",
                                  "input": i["name"]}), file=sys.stderr); return 4
        client = (i.get("from") in ("клієнт", "client") or path.startswith("clients/")
                  or bool(UNTRUSTED_NAME.search(path)) or k == "знеособлено")
        if a.toc:
            _, secs = sections(text)
            lines = text.splitlines(keepends=True)
            toc.append({"name": i["name"], "untrusted": client, "class": k, "sections_count": len(secs),
                        "tokens": tokens(text, a.chars_per_token),
                        "sections": None if client else [{"title": t, "level": l,
                                    "tokens": tokens("".join(lines[s:e]), a.chars_per_token)} for l, t, s, e in secs]})
            continue
        if i["name"] in narrowing:
            text = narrow(text, narrowing[i["name"]])
            if text is None:
                print(json.dumps({"error": "--sections: жодного розділу не знайдено", "input": i["name"]}), file=sys.stderr); return 6
        if client:
            text = re.sub(r"</untrusted\s*>", "&lt;/untrusted&gt;", text, flags=re.I)  # не дати закрити обгортку зсередини
            text = f'<untrusted source="repo:{path}@{sha}">\n{text}\n</untrusted>\n'
        dst = os.path.join(a.out, re.sub(r"[^\w.-]", "_", f"{i['name']}@{sha[:8]}"))
        open(dst, "w", encoding="utf-8").write(text)
        tok = tokens(text, a.chars_per_token)
        total += tok
        items.append({"name": i["name"], "file": dst, "class": k, "untrusted": client, "tokens": tok,
                      "narrowed": i["name"] in narrowing, "data_source": f"repo:{path}@{sha}"})
    if a.toc:
        print(json.dumps({"toc": toc}, ensure_ascii=False, indent=1)); return 0
    out = {"total_tokens": total, "budget": a.budget, "items": items}
    if total > a.budget:  # код 5: файли не лишати; маніфест — лише в stdout
        for f in os.listdir(a.out):
            fp = os.path.join(a.out, f)
            shutil.rmtree(fp) if os.path.isdir(fp) else os.remove(fp)
        print(json.dumps(out, ensure_ascii=False, indent=1)); return 5
    with open(os.path.join(a.out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps(out, ensure_ascii=False, indent=1)); return 0

sys.exit(main())
