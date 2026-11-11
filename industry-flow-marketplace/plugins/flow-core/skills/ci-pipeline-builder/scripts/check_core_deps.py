#!/usr/bin/env python3
"""Залежності ядра пакета (К-06, К-09): ядро працює на CE і не залежить від EE-модулів та AGPL.
Використання: python3 -I check_core_deps.py --addons package/addons [--licenses <файл "модуль: ліцензія">] [--ee-modules <файл зі списком імен>]
  [--odoo-addons <каталог[,каталог]>]
Вивід: JSON [{"id","status","msg"}]; exit 1 при FAIL. Лише stdlib. Статуси: PASS FAIL WARN SKIP.
Правила:
  - ядро = модулі без суфікса _ee; EE-підсилення = td_*_ee (auto_install), їм залежності від EE дозволені;
  - CORE-agpl: ядро залежить від модуля (у каталозі addons) з license AGPL-*, або саме має AGPL;
  - CORE-ee-dep: ядро залежить від td_*_ee, від модуля з license OEEL-*/OPL-* або від імені зі списку --ee-modules;
  - CORE-license-unknown (WARN): залежність, що лежить у addons (вендорена), без ключа license у manifest і без запису в --licenses.
  - CORE-external (WARN): залежність, якої немає в addons, у --licenses і в --ee-modules (стандартні модулі Odoo, OCA, чужі каталоги) — НЕ оцінена;
  Без --ee-modules CORE-ee-dep без знахідок = WARN «стандартні EE-модулі не перевірено» (не PASS): списку EE-модулів скрипт не вигадує (його дає --ee-modules).
  AGPL-PASS означає лише «у каталозі addons AGPL немає»."""
import ast
import json
import os
import re
import sys


def read_manifest(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read(), mode="eval")
        d = ast.literal_eval(tree)
        return d if isinstance(d, dict) else None
    except (OSError, SyntaxError, ValueError):
        return None


def load_map(path):
    out = {}
    try:
        for line in open(path, encoding="utf-8"):
            m = re.match(r"^\s*([a-z0-9_]+)\s*[:|]\s*([\w.\-]+)", line)
            if m:
                out[m.group(1)] = m.group(2)
    except OSError:
        return None
    return out


def main(argv):
    opt = {}
    i = 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            opt[argv[i]] = argv[i + 1]
            i += 2
        else:
            i += 1
    root = opt.get("--addons")
    if not root or not os.path.isdir(root):
        print(json.dumps([{"id": "CORE-usage", "status": "FAIL", "msg": "--addons <каталог> обов'язковий і має існувати"}], ensure_ascii=False))
        return 2
    licenses = load_map(opt["--licenses"]) if "--licenses" in opt else {}
    ee_names = set(load_map(opt["--ee-modules"]) or {}) if "--ee-modules" in opt else set()
    if "--ee-modules" in opt and not ee_names:
        ee_names = {l.strip() for l in open(opt["--ee-modules"], encoding="utf-8") if re.match(r"^[a-z0-9_]+$", l.strip())}
    std = {}
    for sd in (opt.get("--odoo-addons") or "").split(","):
        sd = sd.strip()
        if sd and os.path.isdir(sd):
            for n in sorted(os.listdir(sd)):
                mf = os.path.join(sd, n, "__manifest__.py")
                if os.path.isfile(mf):
                    std.setdefault(n, read_manifest(mf) or {})
    mods = {}
    for n in sorted(os.listdir(root)):
        mf = os.path.join(root, n, "__manifest__.py")
        if os.path.isfile(mf):
            mods[n] = read_manifest(mf) or {}
    res = []
    agpl, eedep, unk, ext = [], [], [], []

    def lic(name):
        return (licenses or {}).get(name) or (mods.get(name) or std.get(name) or {}).get("license")

    for n, mf in mods.items():
        is_ee = n.endswith("_ee")
        own = lic(n)
        if not is_ee and own and own.upper().startswith("AGPL"):
            agpl.append(f"{n} (власна ліцензія {own})")
        if is_ee:
            continue
        for d in mf.get("depends", []) or []:
            if d.endswith("_ee") or d in ee_names:
                eedep.append(f"{n}->{d}")
                continue
            known = d in mods or d in std or d in (licenses or {})
            if not known:
                ext.append(f"{n}->{d}")
            if known:
                l = lic(d)
                if l is None:
                    unk.append(f"{n}->{d}")
                elif l.upper().startswith("AGPL"):
                    agpl.append(f"{n}->{d} ({l})")
                elif l.upper().startswith(("OEEL", "OPL")):
                    eedep.append(f"{n}->{d} ({l})")
    res.append({"id": "CORE-modules", "status": "PASS" if mods else "FAIL", "msg": f"модулів знайдено: {len(mods)}" if mods else f"у {root} немає модулів з __manifest__.py"})
    res.append({"id": "CORE-agpl", "status": "FAIL" if agpl else "PASS", "msg": "; ".join(agpl) if agpl else "AGPL у каталозі addons немає (зовнішні залежності — див. CORE-external)"})
    if eedep:
        res.append({"id": "CORE-ee-dep", "status": "FAIL", "msg": "ядро залежить від EE: " + "; ".join(eedep)})
    elif "--ee-modules" not in opt:
        res.append({"id": "CORE-ee-dep", "status": "WARN", "msg": "td_*_ee і OEEL/OPL у addons не знайдено, але стандартні EE-модулі не перевірено (немає --ee-modules; без доступу до EE — «не перевірено»)"})
    else:
        res.append({"id": "CORE-ee-dep", "status": "PASS", "msg": "ядро не залежить від EE-модулів зі списку --ee-modules (EE-підсилення - td_*_ee)"})
    res.append({"id": "CORE-external", "status": "WARN" if ext else "PASS", "msg": ("не оцінено (немає в addons/--licenses/--ee-modules/--odoo-addons): " + "; ".join(sorted(set(ext)))) if ext else "усі залежності оцінено"})
    res.append({"id": "CORE-license-unknown", "status": "WARN" if unk else "PASS", "msg": ("ліцензію не визначено (додайте license у manifest або --licenses): " + "; ".join(unk)) if unk else "ліцензії залежностей відомі"})
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 1 if any(r["status"] == "FAIL" for r in res) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
