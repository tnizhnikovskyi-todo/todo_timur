#!/usr/bin/env python3
"""Статичні перевірки .github/workflows/ci.yml (C-03). Stdlib; PyYAML не потрібен (regex за відступами).
Використання: python3 -I check_ci.py ci.yml [--registry clients/REGISTRY.md] [--scenarios package/demo/scenarios.md]
Вивід: рядки "STATUS id [msg]"; msg лише при FAIL/SKIP; exit 1 при будь-якому FAIL. Статуси: PASS FAIL SKIP."""
import re
import sys

TEST_JOBS = {"package-tests", "client-tests", "tours", "config-matrix"}
SUPPORTED = r"odoo_supported\s*==\s*'true'"


def split_jobs(text):
    """Повертає {ім'я: тіло} для job'ів з блока jobs: (ключі з відступом 2 пробіли)."""
    body = text.split("\njobs:", 1)[-1] if "\njobs:" in text else ""
    jobs, cur = {}, None
    for line in body.split("\n"):
        m = re.match(r"^  ([\w-]+):\s*$", line)
        if m:
            cur = m.group(1)
            jobs[cur] = []
        elif cur is not None:
            jobs[cur].append(line)
    return {k: "\n".join(v) for k, v in jobs.items()}


def strip_comments(body):
    """Відкидає повні рядки-коментарі й хвостові ` # ...` (поза лапками — наближено)."""
    out = []
    for line in body.split("\n"):
        if line.lstrip().startswith("#"):
            continue
        out.append(re.sub(r"\s+#.*$", "", line))
    return "\n".join(out)


def job_if(body):
    m = re.search(r"^    if:\s*(.+)$", body, re.M)
    return m.group(1) if m else ""


def main(argv):
    if not argv:
        print("FAIL usage ci.yml path required")
        return 2
    try:
        text = open(argv[0], encoding="utf-8").read()
    except OSError as e:
        print(f"FAIL usage не вдалося прочитати {argv[0]}: {e.strerror}")
        return 2
    opt = {argv[i]: argv[i + 1] for i in range(1, len(argv) - 1, 2)}
    res = []

    def add(i, ok, msg=""):
        res.append(("PASS" if ok else "FAIL", i, "" if ok else msg))

    jobs = split_jobs(text)
    head = text.split("\njobs:", 1)[0]

    ph = re.findall(r"\{\{(?! )[A-Z][^}]*\}\}", text)
    add("placeholders", not ph, f"нерозв'язані плейсхолдери: {sorted(set(ph))[:5]}")

    on_block = re.search(r"^on:\s*\n((?:[ \t]+.*\n|\s*\n)+)", head + "\n", re.M)
    on_text = on_block.group(1) if on_block else ""
    has_paths = bool(re.search(r"^\s+paths(-ignore)?:", on_text, re.M))
    add("triggers", all(x in head for x in ("workflow_dispatch", "upgrade/**", "main", "pull_request", "push")) and not has_paths,
        "потрібні push (main, upgrade/**), pull_request, workflow_dispatch" + ("; фільтри paths заборонені (required check зависне, обсяг визначає resolve)" if has_paths else ""))

    res_body = jobs.get("resolve", "")
    miss_dir = [p for p in ("package/addons", "package/config", "clients/", ".github/workflows/ci.yml") if p not in res_body]
    add("resolve-zones", not miss_dir and "resolve" in jobs, f"resolve не покриває зони: {miss_dir}")

    di = [k for k in ("package_tag", "client", "odoo_version", "sha", "edition")
          if not re.search(rf"inputs\.{k}\b", text.split("\njobs:", 1)[-1]) or not re.search(rf"^\s+{k}:", head, re.M)]
    add("dispatch-inputs", not di, f"input не оголошено або не використано: {di}")

    add("addons-path", not re.search(r"td_\*", text) and "package/addons" in text,
        "addons-path має бути весь package/addons, не glob td_*")

    ct = jobs.get("client-tests", "")
    ok_tag = "REGISTRY" in text and not re.search(r"ref:\s*\"?\$\{\{\s*github\.sha", ct)
    msg = "тег клієнта з REGISTRY.md, не github.sha пакета"
    reg = opt.get("--registry")
    if ok_tag and reg:
        try:
            rtext = open(reg, encoding="utf-8").read()
            if re.search(r"кандидат|candidate", rtext, re.I) and not re.search(r"кандидат|candidate", head + jobs.get("resolve", ""), re.I):
                ok_tag, msg = False, "REGISTRY.md має тег-кандидат, а resolve не віддає йому пріоритет"
        except OSError:
            res.append(("SKIP", "client-tag", "registry недоступний; пріоритет кандидата не звірено"))
            reg = None
    if reg or not ok_tag or "--registry" not in opt:
        add("client-tag", ok_tag, msg)

    tests = {n: b for n, b in jobs.items() if n in TEST_JOBS or ("tools/odoo/" in b and n != "core-deps")}
    ungated = [n for n, b in tests.items() if not re.search(SUPPORTED, job_if(b))]
    add("odoo-version", bool(re.search(r"-odoo", text)) and "odoo_supported" in text and not ungated,
        "немає розв'язання суфікса -odoo<N>/odoo_supported" + (f"; тестові job'и без гейта odoo_supported == 'true': {ungated}" if ungated else ""))

    bad_needs = []
    for n, b in jobs.items():
        m = re.search(r"^    needs:\s*(.+)$", b, re.M)
        if m:
            for dep in re.findall(r"[\w-]+", m.group(1).strip("[]")):
                if dep not in jobs:
                    bad_needs.append(f"{n}->{dep}")
    add("needs-exist", not bad_needs, f"needs на неіснуючі job'и: {bad_needs}")

    pt = jobs.get("package-tests", "")
    ebad = []
    if pt:
        if not re.search(r"matrix:\s*\n\s+edition:", pt):
            ebad.append("package-tests без matrix.edition (CE і EE)")
        if "ODOO_EDITION" not in pt:
            ebad.append("package-tests не передає ODOO_EDITION у скрипт C-00")
        if "ee-unavailable" not in pt:
            ebad.append("немає обробки EE без доступу (WARN ee-unavailable)")
        if re.search(r"ee-unavailable[^\n]*PASS", strip_comments(pt)):
            ebad.append("ee-unavailable не може бути PASS")
    if '"ce"' not in jobs.get("resolve", "") or "editions" not in jobs.get("resolve", ""):
        ebad.append("resolve не віддає editions із ce")
    ci_code = strip_comments(jobs.get("ci", ""))
    if pt and not re.search(r"^\s+ee_verdict:", strip_comments(pt.split("steps:", 1)[0]), re.M):
        ebad.append("package-tests не віддає outputs.ee_verdict (вердикт EE не доходить до ci)")
    if not re.search(r"needs\.package-tests\.outputs\.ee_verdict|download-artifact", ci_code) or "ee-unavailable" not in ci_code:
        ebad.append("ci читає вердикт EE лише в коментарі: потрібні needs.package-tests.outputs.ee_verdict (або download-artifact) і виконуваний рядок з ee-unavailable")
    if pt and not re.search(r"^\s+ce_verdict:", strip_comments(pt.split("steps:", 1)[0]), re.M):
        ebad.append("package-tests не віддає outputs.ce_verdict (опис статусу ci не знає результат CE)")
    if not re.search(r"needs\.package-tests\.outputs\.ce_verdict", ci_code) or "не запускалась" not in ci_code or "ran:" not in ci_code:
        ebad.append("ci формує опис редакцій не з фактів: потрібні ce_verdict, гілки ran:PASS/ran:FAIL/ee-unavailable і «не запускалась» (edition=ce/ee) у виконуваному коді")
    if re.search(r"EE_DESC=[\"']CE PASS", ci_code):
        ebad.append("EE_DESC жорстко містить «CE PASS»")
    add("editions", not ebad, "; ".join(ebad))

    cd = jobs.get("core-deps", "")
    cbad = []
    if not cd or "check_core_deps" not in cd:
        cbad.append("немає job core-deps із check_core_deps.py (AGPL/EE у ядрі)")
    if "core-deps" not in (re.search(r"^    needs:\s*(.+)$", jobs.get("ci", ""), re.M) or [None, ""])[1]:
        cbad.append("core-deps відсутній у needs job ci")
    ci_exec = strip_comments(jobs.get("ci", ""))
    if "CE_ONLY_DESC" not in ci_exec or "лише CE" not in ci_exec:
        cbad.append("ci не додає до опису статусу виконуваний рядок 'client-tests/tours: лише CE'")
    if "CORE_DEPS_NOTE" not in ci_exec or "core_deps_note" not in strip_comments(cd):
        cbad.append("ci не додає до опису 'core-deps: ... не оцінено' при CORE-external")
    if jobs.get("tours") and not re.search(r"ODOO_EDITION:\s*\"?ce\"?", strip_comments(jobs.get("tours", ""))):
        cbad.append("job tours без явного ODOO_EDITION: ce")
    add("core-deps", not cbad, "; ".join(cbad))

    ci_block = jobs.get("ci", "")
    add("ci-contract", bool(ci_block) and "if: always()" in ci_block and "statuses: write" in ci_block
        and ("needs.*.result" in ci_block or "toJSON(needs)" in ci_block) and "run-name" in head and "SHA" in head.upper()
        and re.search(r"if:[^\n]*inputs\.sha\s*!=\s*''", ci_block) is not None and "cancel-in-progress: true" not in head,
        "job ci: if: always(), needs.*.result/toJSON(needs), statuses: write, commit status лише при inputs.sha != '', run-name з SHA; cancel-in-progress: true заборонено")

    vbad = []
    for n in ("package-tests", "client-tests"):
        if n in jobs:
            b = jobs[n]
            if not (re.search(r"skipped", b) and re.search(r"exit\s+(1|\"?\$)|sys\.exit", b)
                    and re.search(r"(==|-eq|<=|-le)\s*0|not\s+\w*tests|tests\w*\s*(==|=)\s*0", b)):
                vbad.append(n)
    tb = jobs.get("tours", "")
    if tb and not re.search(r"exit\s+(1|\"?\$)|sys\.exit", tb):
        vbad.append("tours (тур без результату має давати exit≠0)")
    if "continue-on-error: true" in text:
        vbad.append("continue-on-error: true")
    add("verdict-rules", not vbad,
        f"вердикт без skipped>0 / 0 тестів / exit≠0 або continue-on-error: {vbad}")

    sc = opt.get("--scenarios")
    if sc:
        try:
            tours = set(re.findall(r"Odoo tour:\s*([\w.\-]+)", open(sc, encoding="utf-8").read()))
            miss = [t for t in tours if t not in text]
            add("tours-list", not miss, f"тури сценаріїв відсутні в job: {miss}")
        except OSError:
            res.append(("SKIP", "tours-list", "scenarios.md недоступний"))
    else:
        res.append(("SKIP", "tours-list", "N/A: A-16 ще немає"))

    bad = []
    if "pull_request_target" in text: bad.append("pull_request_target")
    if re.search(r"odoo19-lint", text): bad.append("odoo19-lint")
    in_run, run_ind = False, 0
    for line in text.split("\n"):
        ind = len(line) - len(line.lstrip())
        m = re.match(r"^\s*(?:-\s+)?run:\s*(.*)$", line)
        if m:
            in_run, run_ind = (m.group(1).strip() in ("|", ">", "|-", ">-")), ind
            body = m.group(1)
        elif in_run and (not line.strip() or ind > run_ind):
            body = line
        else:
            in_run, body = False, ""
        if re.search(r"\$\{\{\s*(github\.event|inputs\.|github\.head_ref)", body):
            bad.append("event-поле в run:")
            break
    if re.search(r"echo[^\n]*secrets\.|printenv|\benv\s*$", text, re.M): bad.append("секрети/env у виводі")
    ro = jobs.get("report-odoo")
    if ro is not None:
        cond = job_if(ro)
        if "pull_request" in cond.replace("!= 'pull_request'", "") or not re.search(r"event_name\s*==\s*'(push|workflow_dispatch)'", cond):
            bad.append("report-odoo має йти лише на push/workflow_dispatch, не на pull_request")
        if "secrets.ODOO_FLOW" in ro and "environment:" not in ro:
            bad.append("report-odoo без захищеного Environment")
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
