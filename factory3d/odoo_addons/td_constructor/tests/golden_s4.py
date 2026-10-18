"""Золоті файли слайса S4 (F11 XLSX): Python ↔ JS.

    python3 factory3d/odoo_addons/td_constructor/tests/golden_s4.py --write   # перегенерувати fixtures/s4_python.xlsx

`static/tests/fixtures/s4_python.xlsx` пише ЦЕЙ файл (xlsxwriter: спільні рядки, числа, булеві, два аркуші); `node tools/test_core_s4.mjs`
перевіряє, що ядро його читає. Зворотний бік — `s4_roundtrip.xlsx` пише ядро (`node tools/test_core_s4.mjs --write-fixture`), а
`test_s4_tabular.py` читає його сервісом `services/tabular.py` (openpyxl)."""

import datetime
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'static' / 'tests' / 'fixtures'
NAME = 's4_python.xlsx'
FIRST = [
    ['Full Location Name', 'Location Type', 'Barcode', 'Parent Location', 'Quantity'],
    ['WH/Stock/A-01-01-1', 'Internal Location', 'A-01-01-1', 'WH/Stock', 12.5],
    ['WH/Stock/Зона «Б»', 'Internal Location', '007', 'WH/Stock', ''],
    ['WH/Stock/Ящик', 'View', '', 'WH/Stock', True],
]
SECOND = [['x', 'y'], ['Юнікод «так»', 5]]


def build():
    import xlsxwriter

    buffer = io.BytesIO()
    book = xlsxwriter.Workbook(buffer, {'in_memory': True, 'strings_to_numbers': False})
    book.set_properties({'created': datetime.datetime(2024, 1, 1)})
    for title, rows in (('Локації', FIRST), ('Другий', SECOND)):
        ws = book.add_worksheet(title)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                if value == '':
                    continue
                if isinstance(value, bool):
                    ws.write_boolean(r, c, value)
                elif isinstance(value, (int, float)):
                    ws.write_number(r, c, value)
                else:
                    ws.write_string(r, c, value)
    book.close()
    return buffer.getvalue()


if __name__ == '__main__':
    if '--write' in sys.argv:
        (FIXTURES / NAME).write_bytes(build())
        print('written', FIXTURES / NAME)
    else:
        print('usage: golden_s4.py --write')
