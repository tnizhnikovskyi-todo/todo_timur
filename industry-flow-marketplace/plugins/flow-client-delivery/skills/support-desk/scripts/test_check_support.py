#!/usr/bin/env python3
"""Юніт-тести check_support.py: усі статуси шаблону проходять SD-enums; шаблон без прикладів не дає хибних FAIL;
SD-route-table, SD-d02, SD-14days, SD-protected. Запуск: python3 -I scripts/test_check_support.py"""
import json, re, subprocess, sys, tempfile, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SK = HERE.parent
ROUTES = SK.parent.parent / "references" / "triage-routes.md"
STATUSES = ["в роботі (B-13)", "виправлено на тесті", "застосовано в прод (B-12)", "Закрито з підтвердженням клієнта",
            "передано в беклог (D-02)", "передано в D-02", "очікує Підтримку", "потрібен AC — Підтримка"]


def run(path, *extra):
    out = subprocess.run([sys.executable, "-I", str(HERE / "check_support.py"), str(path), *extra],
                         capture_output=True, text=True, check=True).stdout
    return {r["id"]: r for r in json.loads(out)}


def template():
    t = (SK / "references" / "hypercare-template.md").read_text(encoding="utf-8")
    return re.search(r"```markdown\n(.*?)```", t, re.S).group(1)


def with_rows(rows, d02=""):
    t = template()
    t = re.sub(r"(\|---\|(?:---\|){11}\n)", lambda m: m.group(1) + "\n".join(rows) + "\n", t, count=1)
    return t.replace("## Запити в D-02\n", "## Запити в D-02\n" + d02, 1) if d02 else t


def row(i, typ, sev, route, status, ac="", thr=None):
    return f"| INC-{i:03d} | gmail:t{thr or i} | 2026-10-03 09:12 | опис | {sev} | {typ} | {ac} | {route} | {status} | | | |"


class T(unittest.TestCase):
    def check(self, text, *extra):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "hypercare.md"
            p.write_text(text, encoding="utf-8")
            return run(p, *extra)

    def test_empty_template_clean(self):
        r = self.check(template(), "--routes", str(ROUTES))
        for k in ("SD-columns", "SD-enums", "SD-route", "SD-route-table", "SD-dup", "SD-pii"):
            self.assertEqual(r[k]["status"], "PASS", r[k])

    def test_all_statuses_pass_enums(self):
        rows = [row(i + 1, "консультація", "низька", "Підтримка", s) for i, s in enumerate(STATUSES)]
        self.assertEqual(self.check(with_rows(rows))["SD-enums"]["status"], "PASS")

    def test_route_table(self):
        good = [row(1, "баг конфіг", "висока", "B-13 (B-04)", "в роботі (B-04)", "AC-07")]
        bad = [row(1, "баг конфіг", "висока", "B-07", "в роботі (B-07)", "AC-07")]
        self.assertEqual(self.check(with_rows(good), "--routes", str(ROUTES))["SD-route-table"]["status"], "PASS")
        self.assertEqual(self.check(with_rows(bad), "--routes", str(ROUTES))["SD-route-table"]["status"], "FAIL")

    def test_medium_package_defect_needs_no_d02(self):
        rows = [row(1, "дефект пакета", "середня", "рішення Підтримки", "очікує Підтримку")]
        self.assertEqual(self.check(with_rows(rows))["SD-d02"]["status"], "PASS")
        rows = [row(1, "нова вимога", "низька", "D-02", "передано в беклог (D-02)")]
        self.assertEqual(self.check(with_rows(rows))["SD-d02"]["status"], "FAIL")

    def test_14days(self):
        t = template().replace("| Дата go-live | РРРР-ММ-ДД", "| Дата go-live | 2026-09-01") \
            .replace("| Дата останнього критичного інциденту | РРРР-ММ-ДД або «немає»", "| Дата останнього критичного інциденту | 2026-09-20")
        t = re.sub(r"(Дата завершення hypercare \| )[^\n]*", r"\g<1>2026-10-02", t)
        self.assertEqual(self.check(t, "--mode", "hypercare-close")["SD-14days"]["status"], "FAIL")
        t = t.replace("| 2026-10-02", "| 2026-10-04")
        self.assertEqual(self.check(t, "--mode", "hypercare-close")["SD-14days"]["status"], "PASS")

    def test_pii(self):
        r = self.check(template() + "\nписав test@example.com, +380 67 123 45 67\n")
        self.assertEqual(r["SD-pii"]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main(verbosity=1)
