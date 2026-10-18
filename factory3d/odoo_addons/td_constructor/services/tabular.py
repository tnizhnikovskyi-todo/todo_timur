"""Імпорт і експорт таблиць XLSX/CSV (F11, API-19 `table_xlsx`, API-20 `/parse/table`).

Чисті функції без ORM (їх перевіряють без бази); рендерер `table_xlsx` реєструється внизу файла (`RENDERERS`).

* `parse_table(filename, content, sheet=0)` → `{format, encoding?, delimiter?, sheets?, sheet?, rows, truncated}`: XLSX читає
  `openpyxl` (read-only, `data_only`: значення формул — як їх бачить Excel), CSV — UTF-8 (з BOM чи без) або Windows-1251, роздільник
  кома / крапка з комою / табуляція за першим рядком. Рядки — списки значень (str | int | float | bool), порожня клітинка — `""`;
  формат збігається з тим, що віддає ядро JS (`core/constructor/tabular_core.js`), тож «туди-назад» без втрат.
* `table_xlsx(rows, sheet)` → байти XLSX (`xlsxwriter`): рядки лишаються рядками (нулі на початку), числа — числами.
* Файл більший за `MAX_BYTES` або таблиця більша за `MAX_ROWS` рядків відхиляються: `ValidationError` (код `validation`)."""

import base64
import binascii
import csv
import datetime
import io
import re
import zipfile

from odoo.exceptions import ValidationError

from .registry import RENDERERS

MAX_BYTES = 25 * 1024 * 1024
MAX_ROWS = 200_000
MAX_COLS = 200
SHEET_BAD = re.compile(r'[\\/?*\[\]:]')
DELIMITERS = (',', ';', '\t')
XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def decode_bytes(content):
    """Байти → (текст, кодування): UTF-8 (BOM знімається) або Windows-1251."""
    try:
        return content.decode('utf-8-sig'), 'utf-8'
    except UnicodeDecodeError:
        return content.decode('cp1251', errors='replace'), 'windows-1251'


def detect_delimiter(text):
    """Роздільник за першим рядком (поза лапками): кома, крапка з комою або табуляція; рівність — першою кома (як у JS)."""
    first = re.split(r'\r\n|\n|\r', text, maxsplit=1)[0]
    best, most = ',', -1
    for delim in DELIMITERS:
        count, quoted = 0, False
        for char in first:
            if char == '"':
                quoted = not quoted
            elif char == delim and not quoted:
                count += 1
        if count > most:
            best, most = delim, count
    return best


def _cell(value):
    """Значення клітинки → str | int | float | bool; порожнє — ''."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime.datetime):
        return value.isoformat(sep=' ')
    if isinstance(value, (datetime.date, datetime.time)):
        return value.isoformat()
    return str(value)


def _trim(rows):
    """Хвостові порожні клітинки й рядки зникають; решта вирівнюється за шириною (як `trimRows` у JS)."""
    out = []
    for row in rows:
        row = list(row)
        while row and row[-1] == '':
            row.pop()
        out.append(row)
    while out and not out[-1]:
        out.pop()
    width = max((len(r) for r in out), default=0)
    return [r + [''] * (width - len(r)) for r in out]


def parse_table(filename, content, sheet=0, max_rows=MAX_ROWS):
    """Файл → рядки таблиці (див. docstring модуля). Хибний файл — `ValidationError`."""
    if not isinstance(content, (bytes, bytearray)) or not content:
        raise ValidationError("Файл порожній.")
    if len(content) > MAX_BYTES:
        raise ValidationError("Файл завеликий: до %d МБ." % (MAX_BYTES // 1024 // 1024))
    content = bytes(content)
    if content[:2] == b'PK':
        return _parse_xlsx(content, sheet, max_rows)
    text, encoding = decode_bytes(content)
    delimiter = detect_delimiter(text)
    rows, truncated = [], False
    try:
        for row in csv.reader(io.StringIO(text, newline=''), delimiter=delimiter, quotechar='"'):
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append(row[:MAX_COLS])
    except csv.Error as exc:
        raise ValidationError("Файл CSV не розібрано: %s" % exc) from exc
    return {'format': 'csv', 'encoding': encoding, 'delimiter': delimiter, 'rows': _trim(rows), 'truncated': truncated}


def _parse_xlsx(content, sheet, max_rows):
    import openpyxl

    try:
        book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except (zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise ValidationError("Файл не схожий на XLSX: %s" % exc) from exc
    try:
        names = list(book.sheetnames)
        if isinstance(sheet, int) or (isinstance(sheet, str) and sheet.isdigit()):
            if not 0 <= int(sheet) < len(names):
                raise ValidationError("Аркуша №%s немає в книзі." % sheet)
            name = names[int(sheet)]
        elif sheet in names:
            name = sheet
        else:
            raise ValidationError("Аркуша «%s» немає в книзі." % sheet)
        rows, truncated = [], False
        for raw in book[name].iter_rows(values_only=True):
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([_cell(v) for v in raw[:MAX_COLS]])
    finally:
        book.close()
    return {'format': 'xlsx', 'sheets': names, 'sheet': name, 'rows': _trim(rows), 'truncated': truncated}


def table_xlsx(rows, sheet='Локації'):
    """Рядки (списки str | число | bool | None) → байти XLSX."""
    import xlsxwriter

    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValidationError("rows: список рядків (до %d)." % MAX_ROWS)
    title = SHEET_BAD.sub(' ', str(sheet or 'Лист1'))[:31] or 'Лист1'
    buffer = io.BytesIO()
    book = xlsxwriter.Workbook(buffer, {'in_memory': True, 'strings_to_numbers': False, 'strings_to_formulas': False})
    book.set_properties({'created': datetime.datetime(2024, 1, 1)})  # детермінований файл
    ws = book.add_worksheet(title)
    for r, row in enumerate(rows):
        if not isinstance(row, (list, tuple)) or len(row) > MAX_COLS:
            raise ValidationError("rows[%d]: список клітинок (до %d)." % (r, MAX_COLS))
        for c, value in enumerate(row):
            if value is None or value == '':
                continue
            if isinstance(value, bool):
                ws.write_boolean(r, c, value)
            elif isinstance(value, (int, float)):
                ws.write_number(r, c, value)
            else:
                ws.write_string(r, c, str(value))
    book.close()
    return buffer.getvalue()


def decode_payload(content):
    """base64 з тіла запиту → байти; хибний base64 — `ValidationError`."""
    if not isinstance(content, str) or not content:
        raise ValidationError("content: очікується base64 вмісту файла.")
    try:
        return base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationError("content: хибний base64.") from exc


def render_table_xlsx(_env, payload):
    """API-19 `table_xlsx`: `{rows, sheet?, filename?}` → (ім'я файла, mimetype, байти)."""
    filename = re.sub(r'[^\w.-]+', '_', str(payload.get('filename') or 'table')).strip('._') or 'table'
    if not filename.lower().endswith('.xlsx'):
        filename += '.xlsx'
    return filename, XLSX_MIME, table_xlsx(payload.get('rows'), payload.get('sheet') or 'Локації')


RENDERERS.register('table_xlsx', render_table_xlsx)
