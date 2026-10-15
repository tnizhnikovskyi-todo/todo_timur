"""Нормалізація державних номерів (SPEC R-08)."""
import re

LOOKALIKE = {
    "А": "A", "В": "B", "Е": "E", "І": "I", "Ї": "I", "К": "K", "М": "M",
    "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T", "Х": "X", "У": "Y",
}
_SEPARATORS = re.compile(r"[\s\-._·]")
_VALID_NORM = re.compile(r"^[A-Z0-9А-ЯІЇЄҐ]{2,12}$")
_INPUT = re.compile(r"^[A-ZА-ЯІЇЄҐ0-9 -]{2,16}$")
_STD = re.compile(r"^([A-ZА-ЯІЇЄҐ]{2})(\d{4})([A-ZА-ЯІЇЄҐ]{2})$")


def normalize_plate(s):
    """'АА 4512 КТ' -> 'AA4512KT'; порожньо -> ''."""
    if not s:
        return ""
    s = _SEPARATORS.sub("", s.upper())
    return "".join(LOOKALIKE.get(c, c) for c in s)


def is_valid_norm(norm):
    return bool(norm and _VALID_NORM.match(norm))


def display_plate(s):
    """'АА4512КТ' -> 'АА 4512 КТ'; нестандартний формат — як є (upper, без пробілів)."""
    if not s:
        return ""
    s = re.sub(r"\s+", "", s.upper())
    m = _STD.match(s)
    return "%s %s %s" % m.groups() if m else s


def is_valid_plate_input(s):
    """Валідація введеного номера: ^[A-ZА-ЯІЇЄ0-9 -]{2,16}$ після upper()."""
    return bool(s and _INPUT.match(s.upper()))
