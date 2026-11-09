#!/usr/bin/env python3
"""Статичні перевірки .github/workflows/ci.yml (C-03). Stdlib; PyYAML не потрібен (regex).
Використання: python3 -I check_ci.py ci.yml [--registry clients/REGISTRY.md] [--scenarios package/demo/scenarios.md]
Вивід: рядки "STATUS id msg"; exit 1 при будь-якому FAIL. Статуси: PASS FAIL SKIP."""
import re
import sys


def main(argv):
    if not argv:
        print("FAIL usage ci.yml path required")
        return 2
    text = open(argv[0], encoding="utf-8").read()
    opt = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2)}
    res = []

    def add(i, ok, msg=""):
        res.append(("PASS" if ok else "FAIL", i, msg))

    ph = re.findall(r"\{\{(?! )[A-Z][^}]*\}\}", text)
    add("placeholders", not ph, f"нерозв'язані плейсхолдери: {sorted(set(ph))[:5]}" if ph else "")

    need = ["package/addons/**", "package/config/**", "clients/*/addons/**", ".github/workflows/ci.yml"]
    miss = [p for p in need if p not in text]
    add("triggers", not miss and "workflow_dispatch" in text and "upgrade/**" in text and "main" in text,
        f"бракує: {miss}" if miss else "")

    di = [k for k in ("package_tag", "client", "odoo_version", "sha") if not re.search(rf"inputs\.{k}\b", text.split("jobs:", 1)[-1])
          or not re.search(rf"^\s+{k}:", text, re.M)]
    add("dispatch-inputs", not di, f"input не оголошено або не використано: {di}" if di else "")

    add("addons-path", not re.search(r"td_\*", text) and "package/addons" in text,
        "addons-path має бути весь package/addons, не glob td_*")

    add("client-tag", "REGISTRY" in text and not re.search(r"ref:\s*\$\{\{\s*github\.sha", text.split("client-tests:", 1)[-1][:2500]),
        "тег клієнта з REGISTRY.md, не github.sha пакета")

    add("odoo-version", bool(re.search(r"-odoo", text)) and "odoo_supported" in text,
        "немає розв'язання суфікса -odoo<N> або перевірки підтримки")

    ci_block = text.split("\n  ci:", 1)[-1].split("\n  report-odoo:", 1)[0] if "\n  ci:" in text else ""
    add("ci-contract", bool(ci_block) and "if: always()" in ci_block and "needs" in ci_block
        and "statuses: write" in ci_block and "run-name" in text and "SHA" in text.upper(),
        "потрібен job ci з if: always(), needs, statuses: write і run-name з SHA")

    add("verdict-rules", "continue-on-error: true" not in text and "VERDICT" not in text.replace("{{VERDICT_STEP}}", ""),
        "continue-on-error у тестових job'ах заборонено")

    sc = opt.get("--scenarios")
    if sc:
        try:
            tours = set(re.findall(r"Odoo tour:\s*([\w.\-]+)", open(sc, encoding="utf-8").read()))
            add("tours-list", all(t in text for t in tours), f"тури сценаріїв відсутні в job: {[t for t in tours if t not in text]}")
        except OSError:
            res.append(("SKIP", "tours-list", "scenarios.md недоступний"))
    else:
        res.append(("SKIP", "tours-list", "N/A: A-16 ще немає"))

    bad = []
    if "pull_request_target" in text: bad.append("pull_request_target")
    if re.search(r"odoo19-lint", text): bad.append("odoo19-lint")
    if re.search(r"run:[^\n]*\$\{\{\s*(github\.event|inputs\.|github\.head_ref)", text): bad.append("event-поле в run:")
    if re.search(r"echo[^\n]*secrets\.|printenv|\benv\s*$", text, re.M): bad.append("секрети/env у виводі")
    for m in re.finditer(r"(?:^|[\s\-])uses:\s*([^\s#]+)", text, re.M):
        u = m.group(1)
        if not u.startswith("{{") and not re.search(r"@[0-9a-f]{40}$", u):
            bad.append(f"action без SHA-піна: {u}")
    add("security", not bad, "; ".join(bad))

    for st, i, msg in res:
        print(f"{st} {i} {msg}".rstrip())
    return 1 if any(s == "FAIL" for s, _, _ in res) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
