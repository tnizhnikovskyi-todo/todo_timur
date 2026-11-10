#!/usr/bin/env python3
"""evals_to_cli.py - evals/evals.json скіла -> файли кейсів для `claude plugin eval`.

Вхід, два формати: (1) пакета {"skill_name", "evals": [{"id", "prompt", "expected_output", "assertions": [str],
  "expected_checks": [str]?, "must_not": [str]?, "requires": [..]|str|null, "needs_write": bool?, "fixtures"/"files"/"input"?}]};
  (2) репо флоу (references/evals-format.md) {"skill", "cases": [{"id", "status", "prompt", "requires", "input",
  "expected": {"checks", "must_not"}}]}: checks -> assertions, must_not -> must_not, status skipped/queued -> пропуск.
Вихід у --out (тимчасова тека поза репо; згенероване в git не йде):
  <out>/<набір>__<id>/prompt.md              frontmatter (max_turns, allowed_tools) + prompt
  <out>/<набір>__<id>/graders/00-expected.md  type: llm, weight: 1 - expected_output
  <out>/<набір>__<id>/graders/NN-check.md     по одному грейдеру на кожну assertion
  <out>/<набір>__<id>/graders/99-must-not.md  один грейдер на весь must_not (якщо є)
  <out>/mocks/                                копія evals/mocks/ поруч із evals.json (якщо є)
  <manifest-dir>/manifest-<набір>.json        згенеровані й пропущені кейси (з причиною); за замовчуванням manifest-dir = out

Обгрунтування формату CLI (2026-11, `claude plugin eval --help` + `claude plugin eval init --bare`): CLI читає
`<eval dir>/**/prompt.md` + `graders/*.md`; prompt.md має YAML-frontmatter `max_turns`, `allowed_tools`; грейдер -
md із frontmatter `type: llm`, `weight`, тіло = критерій. Саме так виглядає вивід `init --bare`. Припущення (у довідці
не описані, перевірити на місці): (1) імена `NN-check.md`/`99-must-not.md` довільні - CLI бере всі `graders/*.md`;
(2) інші значення `type` (напр. `contains`) не генеруються - лише `llm`; (3) `weight` числовий, 1 = звичайний.
Тека кейса `<набір>__<id>` - під фільтр `--case '<набір>__*'`.

Пропуски (кейс не генерується, причина в manifest-<набір>.json і WARN/SKIP у stdout): requires з відомим префіксом
(odoo-mcp, step-run, github, playwright, agents, web, odb-catalog, точне `fixtures`) - незалежно від довжини тексту;
`mock:` без теки mocks/ поруч - «немає заглушки». Вільний текст без відомого префікса (напр. `fixtures/make_repo.sh ...`) -
лише примітка (manifest + stdout), кейс генерується. Кейс з ключами fixtures/files/input (або input.fixtures) генерується
БЕЗ фікстур, але з `fixtures_pending` у manifest і WARN у stdout: не проганяти, доки runner не розклав фікстури.
Кейс без prompt чи без жодної перевірки - пропуск. Перед генерацією видаляються теки `<набір>__*` в out.
Помилка входу (битий JSON, чужа схема) - повідомлення в stderr, exit 2.
needs_write: true -> allowed_tools +Write, Edit (потрібен --allow-tools Write Edit при прогоні; див. run-eval.md).
Не робить: не запускає CLI, не пише в репо, не чіпає odoo-mcp. stdlib only.

Використання:
  evals_to_cli.py <evals.json> --out <tmp-тека> [--set <ім'я набору>]
  evals_to_cli.py --self-test        # 3+ evals.json пакета у тимчасову теку, без помилок
"""
import argparse
import glob
import json
import os
import re
import shutil
import sys
import tempfile

SKIP_RE = re.compile(r"^(odoo-mcp|step-run|github|playwright|agents|web|odb-catalog|fixtures)(?![\w/.-])")
BASE_TOOLS = ["Read", "Glob", "Grep", "Skill"]


def skip_reason(requires):
    """Причина пропуску або None; другий результат - примітки (вільний текст)."""
    if requires is None:
        return None, []
    items = [requires] if isinstance(requires, str) else list(requires)
    hard, notes = [], []
    for it in items:
        s = str(it).strip()
        if SKIP_RE.match(s):
            hard.append(s[:80])
        elif s:
            notes.append(s[:200])
    return ("requires: " + ", ".join(hard)) if hard else None, notes


def fixture_paths(e):
    """Шляхи фікстур з ключів fixtures/files/input (рядки, списки, dict) або []."""
    out = []

    def walk(v):
        if isinstance(v, str):
            if v.strip():
                out.append(v.strip())
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
    for k in ("fixtures", "files", "input"):
        walk(e.get(k))
    return out


def normalize(data, src):
    """-> (назва набору | None, список кейсів у внутрішньому форматі)."""
    if not isinstance(data, dict):
        raise ValueError(f"{src}: очікується JSON-об'єкт")
    if isinstance(data.get("evals"), list):
        return data.get("skill_name"), data["evals"]
    if isinstance(data.get("cases"), list):
        cases = []
        for c in data["cases"]:
            if not isinstance(c, dict):
                continue
            x = dict(c)
            ex = c.get("expected") if isinstance(c.get("expected"), dict) else {}
            x["assertions"] = list(ex.get("checks") or [])
            x["must_not"] = list(ex.get("must_not") or [])
            if c.get("status") in ("skipped", "queued"):
                x["_skip"] = f"status: {c['status']}"
            cases.append(x)
        return data.get("skill"), cases
    raise ValueError(f"{src}: немає масиву evals або cases (чужа схема)")


def slug(s):
    s = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(s)).strip("-")
    return s or "case"


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text.rstrip("\n") + "\n")


def grader(path, text):
    write(path, "---\ntype: llm\nweight: 1\n---\n\n" + text.strip())


def convert(src, out, set_name=None, manifest_dir=None):
    with open(src, encoding="utf-8") as f:
        data = json.load(f)
    skill, cases = normalize(data, src)
    name = slug(set_name or skill or os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(src)))))
    man = {"set": name, "source": os.path.abspath(src), "generated": [], "skipped": []}
    for old in glob.glob(os.path.join(glob.escape(out), glob.escape(name) + "__*")):
        shutil.rmtree(old, ignore_errors=True)
    mocks = os.path.join(os.path.dirname(os.path.abspath(src)), "mocks")
    seen = set()
    for e in cases:
        if not isinstance(e, dict):
            continue
        cid = str(e.get("id", ""))
        if not cid or cid in seen:
            man["skipped"].append({"id": cid, "reason": "порожній або дублікат id"})
            continue
        seen.add(cid)
        reason, notes = skip_reason(e.get("requires"))
        reason = reason or e.get("_skip")
        if not reason and "mock:" in json.dumps(e.get("requires"), ensure_ascii=False) and not os.path.isdir(mocks):
            reason = "немає заглушки (теки mocks/ поруч з evals.json нема)"
        prompt = e.get("prompt")
        checks = [a for a in (list(e.get("assertions") or []) + list(e.get("expected_checks") or []))
                  if isinstance(a, str) and a.strip()]
        expected = e.get("expected_output")
        if not reason and not (isinstance(prompt, str) and prompt.strip()):
            reason = "немає prompt"
        if not reason and not (checks or (isinstance(expected, str) and expected.strip())):
            reason = "немає assertions/expected_output"
        if reason:
            man["skipped"].append({"id": cid, "reason": reason})
            continue
        d = os.path.join(out, f"{name}__{slug(cid)}")
        tools = BASE_TOOLS + (["Write", "Edit"] if e.get("needs_write") else [])
        write(os.path.join(d, "prompt.md"),
              f"---\nmax_turns: 10\nallowed_tools: [{', '.join(tools)}]\n---\n\n{prompt.strip()}")
        n = 0
        if isinstance(expected, str) and expected.strip():
            grader(os.path.join(d, "graders", "00-expected.md"), expected)
        for c in checks:
            n += 1
            grader(os.path.join(d, "graders", f"{n:02d}-check.md"), c)
        mn = [m for m in (e.get("must_not") or []) if isinstance(m, str) and m.strip()]
        if mn:
            grader(os.path.join(d, "graders", "99-must-not.md"),
                   "Відповідь НЕ повинна містити жодного з пунктів:\n" + "\n".join(f"- {m}" for m in mn))
        rec = {"id": cid, "dir": os.path.basename(d), "graders": n + bool(expected) + bool(mn)}
        if e.get("needs_write"):
            rec["needs_write"] = True
        fx = fixture_paths(e)
        if fx:
            rec["fixtures_pending"] = fx
        if notes:
            rec["notes"] = notes
        man["generated"].append(rec)
    if os.path.isdir(mocks):
        shutil.copytree(mocks, os.path.join(out, "mocks"), dirs_exist_ok=True)
    write(os.path.join(manifest_dir or out, f"manifest-{name}.json"), json.dumps(man, ensure_ascii=False, indent=2))
    return man


def synthetic_test():
    """Синтетичний evals.json з відомим результатом: пропуски за префіксами, must_not, needs_write, фікстури."""
    long_tail = " " + "x" * 120
    evals = [
        {"id": "ok", "prompt": "p", "assertions": ["a1", "a2"], "must_not": ["m1"], "needs_write": True},
        {"id": "empty-prompt", "prompt": " ", "assertions": ["a"]},
        {"id": "no-checks", "prompt": "p"},
        {"id": "exp-checks", "prompt": "p", "expected_checks": ["e1"]},
        {"id": "fx", "prompt": "p", "assertions": ["a"], "fixtures": ["evals/fixtures/x/"]},
        {"id": "fx-script", "prompt": "p", "assertions": ["a"], "requires": ["fixtures/make_repo.sh tmp"]},
        {"id": "fx-exact", "prompt": "p", "assertions": ["a"], "requires": ["fixtures"]},
        {"id": "mock-missing", "prompt": "p", "assertions": ["a"], "requires": ["mock: gmail"]},
        {"id": "free-text", "prompt": "p", "assertions": ["a"], "requires": "тимчасовий git-репо"},
    ] + [{"id": "sk-" + i, "prompt": "p", "assertions": ["a"], "requires": [i + (":" if i.endswith(("agents", "web")) else "") + long_tail]}
         for i in ("odoo-mcp", "step-run", "github", "playwright", "agents", "web", "odb-catalog")]
    tmp = tempfile.mkdtemp(prefix="evals_to_cli_syn_")
    try:
        src = os.path.join(tmp, "s", "evals", "evals.json")
        write(src, json.dumps({"skill_name": "syn", "evals": evals}))
        out = os.path.join(tmp, "out")
        os.makedirs(os.path.join(out, "syn__stale"))
        m = convert(src, out)
        gen = {g["id"]: g for g in m["generated"]}
        skp = {g["id"]: g["reason"] for g in m["skipped"]}
        assert not os.path.exists(os.path.join(out, "syn__stale")), "stale тека не видалена"
        assert set(gen) == {"ok", "exp-checks", "fx", "fx-script", "free-text"}, sorted(gen)
        assert gen["ok"]["graders"] == 3 and gen["ok"]["needs_write"], gen["ok"]
        assert os.path.isfile(os.path.join(out, "syn__ok", "graders", "99-must-not.md"))
        assert "Write" in open(os.path.join(out, "syn__ok", "prompt.md"), encoding="utf-8").read()
        assert gen["exp-checks"]["graders"] == 1
        assert gen["fx"]["fixtures_pending"] == ["evals/fixtures/x/"]
        assert "notes" in gen["free-text"] and "notes" in gen["fx-script"]
        for k in ("empty-prompt", "no-checks", "fx-exact", "mock-missing") + tuple("sk-" + i for i in
                  ("odoo-mcp", "step-run", "github", "playwright", "agents", "web", "odb-catalog")):
            assert k in skp, (k, skp)
        # формат cases[] репо флоу
        cs = {"skill": "syn2", "cases": [
            {"id": "c1", "status": "new-red", "prompt": "p", "expected": {"checks": ["x"], "must_not": ["y"]}},
            {"id": "c2", "status": "queued", "prompt": "p", "expected": {"checks": ["x"]}}]}
        src2 = os.path.join(tmp, "c.json")
        write(src2, json.dumps(cs))
        m2 = convert(src2, out)
        assert m2["set"] == "syn2" and [g["id"] for g in m2["generated"]] == ["c1"] and m2["generated"][0]["graders"] == 2
        assert [g["id"] for g in m2["skipped"]] == ["c2"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SYNTHETIC OK")


def self_test():
    synthetic_test()
    pkg = os.path.abspath(os.path.join(os.path.dirname(__file__), *[".."] * 5))
    files = sorted(glob.glob(os.path.join(pkg, "plugins", "*", "skills", "*", "evals", "evals.json")))
    # різні скіли з різних плагінів; мінімум 3
    picked, plugins = [], set()
    for f in files:
        pl = f.split(os.sep + "skills" + os.sep)[0]
        if pl not in plugins:
            plugins.add(pl)
            picked.append(f)
    for f in files:
        if len(picked) >= 5:
            break
        if f not in picked:
            picked.append(f)
    if len(picked) < 3:
        print("SELF-TEST FAIL: знайдено менше 3 evals.json", file=sys.stderr)
        return 1
    tmp = tempfile.mkdtemp(prefix="evals_to_cli_")
    try:
        total_g = 0
        for f in picked:
            m = convert(f, tmp)
            assert m["generated"] or m["skipped"], f
            for g in m["generated"]:
                d = os.path.join(tmp, g["dir"])
                assert os.path.isfile(os.path.join(d, "prompt.md")), g
                assert glob.glob(os.path.join(d, "graders", "*.md")), g
            total_g += len(m["generated"])
            print(f"OK {m['set']}: generated={len(m['generated'])} skipped={len(m['skipped'])}")
        assert total_g > 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("SELF-TEST OK")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("evals_json", nargs="?")
    ap.add_argument("--out")
    ap.add_argument("--set", dest="set_name")
    ap.add_argument("--manifest-dir", help="куди писати manifest-<набір>.json (за замовчуванням --out)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.evals_json or not a.out:
        ap.error("потрібні evals_json і --out")
    try:
        m = convert(a.evals_json, a.out, a.set_name, a.manifest_dir)
    except (ValueError, OSError) as ex:  # JSONDecodeError - підклас ValueError
        print(f"ПОМИЛКА входу: {ex}", file=sys.stderr)
        return 2
    print(f"{m['set']}: generated={len(m['generated'])} skipped={len(m['skipped'])}")
    for s in m["skipped"]:
        print(f"  SKIP {s['id']}: {s['reason']}")
    for g in m["generated"]:
        if g.get("fixtures_pending"):
            print(f"  WARN {g['id']}: фікстури не розкладено ({', '.join(g['fixtures_pending'])[:150]}) - не проганяти, доки runner їх не розклав")
        for n in g.get("notes", []):
            print(f"  NOTE {g['id']}: {n[:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
