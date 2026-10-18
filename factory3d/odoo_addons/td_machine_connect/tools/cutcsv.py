"""Чисті функції розкрою (без `env`): CSV для оптимізатора, план API-32, CSV деталей, вміщення (R-19, Додатки D, E)."""

import csv
import io
import re

CSV_HEADER = (
    "PartId",
    "Description",
    "Material",
    "Length",
    "Width",
    "Quantity",
    "Grain",
    "EdgeTop",
    "EdgeBottom",
    "EdgeLeft",
    "EdgeRight",
    "Program",
)
CSV_HEADER_LINE = ";".join(CSV_HEADER) + "\r\n"
FORMULA_PREFIX = "=+-@"
MAX_DESCRIPTION = 64

PART_CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,16}$")
EDGE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")
PROGRAM_RE = re.compile(r"^[A-Za-z0-9_\-\.]{1,64}$")
MAX_LENGTH = 5600
MAX_WIDTH = 2200
ROLES = ("main", "back", "product")
PARTS_COLUMNS = (
    "part_code",
    "name",
    "length_mm",
    "width_mm",
    "qty",
    "material_role",
    "material",
    "grain",
    "edge_top",
    "edge_bottom",
    "edge_left",
    "edge_right",
    "program",
    "note",
)
PARTS_REQUIRED = ("part_code", "name", "length_mm", "width_mm", "qty")


def fits(length, width, sheet_length, sheet_width, grain="0"):
    """R-19 п. 4: текстура `0` — з поворотом; `1`/`2` — лише як є."""
    if grain in ("1", "2", 1, 2):
        return length <= sheet_length and width <= sheet_width
    return (length <= sheet_length and width <= sheet_width) or (length <= sheet_width and width <= sheet_length)


def clean_description(name):
    """`;` -> `,`, переноси -> пробіл, без початкових `=+-@`, ≤ 64 символи (R-19 п. 5)."""
    text = (name or "").replace(";", ",").replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    text = text.lstrip(FORMULA_PREFIX).strip()
    return text[:MAX_DESCRIPTION]


def build_parts_csv(lines, material):
    """UTF-8 (рядок), CRLF, `;`. `lines` — dict-и з ключами `part_code`, `name`, `length_mm`, `width_mm`, `qty`,
    `grain`, `edge_*`, `program`; `material` — `default_code` плити."""
    out = io.StringIO(newline="")
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n", quoting=csv.QUOTE_NONE, escapechar="\\")
    writer.writerow(CSV_HEADER)
    for ln in lines:
        writer.writerow(
            [
                ln["part_code"],
                clean_description(ln.get("name")),
                material,
                ln["length_mm"],
                ln["width_mm"],
                ln["qty"],
                ln.get("grain") or "0",
                ln.get("edge_top") or "",
                ln.get("edge_bottom") or "",
                ln.get("edge_left") or "",
                ln.get("edge_right") or "",
                ln.get("program") or "",
            ]
        )
    return out.getvalue()


# --- план оптимізатора (Додаток D) ---------------------------------------------------------------------
def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def parse_plan(data):
    """Перевіряє план API-32; повертає очищений dict. Помилка -> `ValueError("<шлях>: <проблема>")`."""
    if not isinstance(data, dict):
        raise ValueError("plan: очікується об'єкт")
    total = data.get("total_sheets")
    if not _is_int(total) or total < 1:
        raise ValueError("total_sheets: очікується ціле ≥ 1")
    waste = data.get("waste_pct")
    if not _is_num(waste) or not 0 <= waste <= 100:
        raise ValueError("waste_pct: очікується число 0…100")
    sheets = data.get("sheets")
    if not isinstance(sheets, list) or not 1 <= len(sheets) <= 500:
        raise ValueError("sheets: очікується список 1…500")
    clean_sheets = []
    for i, sheet in enumerate(sheets):
        path = "sheets[%d]" % i
        if not isinstance(sheet, dict):
            raise ValueError("%s: очікується об'єкт" % path)
        if not _is_int(sheet.get("no")) or sheet["no"] < 1:
            raise ValueError("%s.no: очікується ціле ≥ 1" % path)
        product = sheet.get("product")
        if not isinstance(product, str) or len(product) > 32:
            raise ValueError("%s.product: очікується рядок ≤ 32" % path)
        parts = sheet.get("parts")
        if not isinstance(parts, list):
            raise ValueError("%s.parts: очікується список" % path)
        clean_parts = []
        for j, part in enumerate(parts):
            ppath = "%s.parts[%d]" % (path, j)
            if not isinstance(part, dict):
                raise ValueError("%s: очікується об'єкт" % ppath)
            if not isinstance(part.get("id"), str) or not part["id"]:
                raise ValueError("%s.id: очікується код деталі" % ppath)
            for key in ("x", "y", "w", "h"):
                if not _is_int(part.get(key)) or part[key] < 0:
                    raise ValueError("%s.%s: очікується ціле ≥ 0" % (ppath, key))
            if part.get("rot") not in (0, 90) or isinstance(part.get("rot"), bool):
                raise ValueError("%s.rot: очікується 0 або 90" % ppath)
            clean_parts.append({k: part[k] for k in ("id", "x", "y", "w", "h", "rot")})
        clean = {"no": sheet["no"], "product": product, "parts": clean_parts}
        if _is_num(sheet.get("waste_pct")):
            clean["waste_pct"] = sheet["waste_pct"]
        if isinstance(sheet.get("cuts"), list):
            clean["cuts"] = sheet["cuts"]
        clean_sheets.append(clean)
    plan = {"total_sheets": total, "waste_pct": float(waste), "sheets": clean_sheets}
    for key in ("cut_length_m", "est_min"):
        if data.get(key) is not None:
            if not _is_num(data[key]) or data[key] < 0:
                raise ValueError("%s: очікується число ≥ 0" % key)
            plan[key] = float(data[key])
    return plan


def plan_counts(plan):
    """Кількість розміщених деталей за `id`."""
    counts = {}
    for sheet in plan["sheets"]:
        for part in sheet["parts"]:
            counts[part["id"]] = counts.get(part["id"], 0) + 1
    return counts


# --- CSV деталей виробу (Додаток E) --------------------------------------------------------------------
def _to_int(value, field, errors, lineno, lo, hi):
    try:
        number = int(str(value).strip())
    except ValueError:
        errors.append("рядок %d: %s: очікується ціле, отримано «%s»" % (lineno, field, value))
        return None
    if not lo <= number <= hi:
        errors.append("рядок %d: %s: %d поза межами %d…%d" % (lineno, field, number, lo, hi))
        return None
    return number


def parse_parts_csv(text):
    """Розбирає CSV Додатка E. Повертає `(rows, errors)`; `rows` — dict-и за M-09 (+ `material`, `lineno`)."""
    if text.startswith("﻿"):
        text = text[1:]
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=";")
    try:
        header = [h.strip() for h in next(reader)]
    except StopIteration:
        return [], ["рядок 1: заголовок: файл порожній"]
    errors = []
    unknown = [h for h in header if h not in PARTS_COLUMNS]
    if unknown:
        errors.append("рядок 1: заголовок: невідомі колонки %s" % ", ".join(unknown))
    missing = [c for c in PARTS_REQUIRED if c not in header]
    if missing:
        errors.append("рядок 1: заголовок: немає колонок %s" % ", ".join(missing))
    if errors:
        return [], errors
    rows = []
    seen = set()
    for lineno, raw in enumerate(reader, start=2):
        if not any(cell.strip() for cell in raw):
            continue
        rec = {h: (raw[i].strip() if i < len(raw) else "") for i, h in enumerate(header)}
        n_before = len(errors)
        for col in PARTS_REQUIRED:
            if not rec.get(col):
                errors.append("рядок %d: %s: обов'язкове поле" % (lineno, col))
        if len(errors) > n_before:
            continue
        code = rec["part_code"]
        if not PART_CODE_RE.match(code):
            errors.append("рядок %d: part_code: латиниця, цифри, _ і -, ≤ 16" % lineno)
        elif code in seen:
            errors.append("рядок %d: part_code: код %s повторюється у файлі" % (lineno, code))
        seen.add(code)
        if len(rec["name"]) > 64:
            errors.append("рядок %d: name: довше 64 символів" % lineno)
        length = _to_int(rec["length_mm"], "length_mm", errors, lineno, 1, MAX_LENGTH)
        width = _to_int(rec["width_mm"], "width_mm", errors, lineno, 1, MAX_WIDTH)
        try:
            qty = float(rec["qty"].replace(",", "."))
        except ValueError:
            qty = None
            errors.append("рядок %d: qty: очікується число, отримано «%s»" % (lineno, rec["qty"]))
        if qty is not None and qty <= 0:
            errors.append("рядок %d: qty: %s має бути > 0" % (lineno, rec["qty"]))
            qty = None
        role = rec.get("material_role") or "main"
        if role not in ROLES:
            errors.append("рядок %d: material_role: допустимо main, back, product" % lineno)
        if role == "product" and not rec.get("material"):
            errors.append("рядок %d: material: обов'язковий для material_role=product" % lineno)
        grain = rec.get("grain") or "0"
        if grain not in ("0", "1", "2"):
            errors.append("рядок %d: grain: допустимо 0, 1, 2" % lineno)
        for edge in ("edge_top", "edge_bottom", "edge_left", "edge_right"):
            if rec.get(edge) and not EDGE_RE.match(rec[edge]):
                errors.append("рядок %d: %s: недопустимий код крайки «%s»" % (lineno, edge, rec[edge]))
        if rec.get("program") and not PROGRAM_RE.match(rec["program"]):
            errors.append("рядок %d: program: недопустима назва програми" % lineno)
        if ";" in rec["name"]:
            errors.append("рядок %d: name: без «;»" % lineno)
        if len(errors) > n_before:
            continue
        rows.append(
            {
                "lineno": lineno,
                "part_code": code,
                "name": rec["name"],
                "length_mm": length,
                "width_mm": width,
                "qty": qty,
                "material_role": role,
                "material": rec.get("material", ""),
                "grain": grain,
                "edge_top": rec.get("edge_top", ""),
                "edge_bottom": rec.get("edge_bottom", ""),
                "edge_left": rec.get("edge_left", ""),
                "edge_right": rec.get("edge_right", ""),
                "program": rec.get("program", ""),
                "note": rec.get("note", "")[:256],
            }
        )
    return rows, errors
