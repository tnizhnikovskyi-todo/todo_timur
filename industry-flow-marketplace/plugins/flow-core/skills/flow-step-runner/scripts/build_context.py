#!/usr/bin/env python3
"""Збирання контексту входів кроку за SHA з фільтром DATA_POLICY (flow-step-runner, крок 6).

Запуск: python3 -I build_context.py --repo <тека> --inputs inputs.json --policy policy.md --out <тека> --budget <токенів>
inputs.json: [{"name","from","path","sha"}]. Лише stdlib. Код виходу: 0 ок; 2 нема SHA/файлу; 3 політика не розібрана;
4 є заборонений вхід; 5 понад бюджет. У stdout — JSON-маніфест (шляхи, класи, токени, data_sources), зміст не друкується.
Припущення (Відкрите питання, узгодити з data-policy-template.md): у розділі «Дозволено передавати в AI» є таблиця
`| шлях-glob | дозволено|знеособлено|заборонено |`; перший збіг рядка з гори вниз виграє; немає збігу -> заборонено.
"""
import argparse, fnmatch, json, os, re, subprocess, sys

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

def main():
    p = argparse.ArgumentParser()
    for k in ("repo", "inputs", "policy", "out"):
        p.add_argument("--" + k, required=True)
    p.add_argument("--budget", type=int, required=True)
    a = p.parse_args()
    rules = load_policy(a.policy)
    if not rules:
        print(json.dumps({"error": "DATA_POLICY: таблицю фільтра не розібрано"}), file=sys.stderr); return 3
    os.makedirs(a.out, exist_ok=True)
    items, total = [], 0
    for i in json.load(open(a.inputs, encoding="utf-8")):
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
        client = i.get("from") == "клієнт" or path.startswith("clients/") or "transcript" in path.lower()
        if client:
            text = f'<untrusted source="repo:{path}@{sha}">\n{text}\n</untrusted>\n'
        dst = os.path.join(a.out, re.sub(r"[^\w.-]", "_", f"{i['name']}@{sha[:8]}"))
        open(dst, "w", encoding="utf-8").write(text)
        tok = len(text) // 4
        total += tok
        items.append({"name": i["name"], "file": dst, "class": k, "untrusted": client, "tokens": tok,
                      "data_source": f"repo:{path}@{sha}"})
    out = {"total_tokens": total, "budget": a.budget, "items": items}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 5 if total > a.budget else 0

sys.exit(main())
