"""Документи: план (PDF вектором) і специфікація стелажів (PDF/XLSX) з даних ядра (F15, API-19); реєстр RENDERERS.

Ядро (`core/constructor/plan_doc.js`, `spec.js`) рахує вміст, сервер лише малює:

* `plan_pdf` — payload `{title, page: {w, h}, ops: [...]}`; `ops` — примітиви в мм (початок — лівий верх, y вниз):
  `poly`, `rect`, `line`, `text` (`anchor`, `rot` — проти годинникової стрілки, градуси), `clipBegin` / `clipEnd`.
  Той самий список малює SVG ядра. Шрифт — NotoSans зі вбудованою кирилицею (як в етикетках).
* `spec_pdf` — payload `{format: 'pdf' | 'xlsx', title, tables: [{name, columns, rows}]}`; без `tables` — `{site_id}`:
  сервер рахує специфікацію за чернеткою площадки (`services/rack_spec.py`, права читання — як у решти API).
* Читання — група «Перегляд» (`td_factory3d.group_td_user`), без запису в БД. `table_xlsx` (імпорт/експорт таблиць) —
  слайс S4.
"""

import io
import math

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from odoo.exceptions import AccessError, ValidationError
from odoo.tools import file_path

from . import rack_spec
from .registry import RENDERERS

FONT_FILE = 'web/static/fonts/sign/NotoSans-Reg.ttf'
FONT_NAME = 'TdDocsNotoSans'
MAX_OPS = 200000
MAX_ROWS = 100000
MAX_TABLES = 10
MAX_COLUMNS = 30
OP_TYPES = ('poly', 'rect', 'line', 'text', 'clipBegin', 'clipEnd')
GROUP = 'td_factory3d.group_td_user'


def _check_access(env, what):
    if not env.user.has_group(GROUP):
        raise AccessError("%s доступні користувачам конструктора (група «Перегляд»)." % what)


def _font():
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, file_path(FONT_FILE)))
    return FONT_NAME


def _num(value, label, lo=-1e6, hi=1e6):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not lo <= value <= hi
    ):
        raise ValidationError("%s: некоректне число." % label)
    return float(value)


def _color(value, default=None):
    if not value:
        return default
    try:
        return colors.HexColor(value)
    except (ValueError, TypeError, AttributeError):
        raise ValidationError("Колір «%s» некоректний." % value) from None


# --- план ----------------------------------------------------------------------------------------------------------


def parse_plan(payload):
    page = payload.get('page')
    if not isinstance(page, dict):
        raise ValidationError("План: потрібен розмір аркуша (page).")
    width, height = _num(page.get('w'), "Ширина аркуша", 50, 2000), _num(page.get('h'), "Висота аркуша", 50, 2000)
    ops = payload.get('ops')
    if not isinstance(ops, list) or not ops:
        raise ValidationError("План: немає що малювати (ops).")
    if len(ops) > MAX_OPS:
        raise ValidationError("План: понад %d примітивів." % MAX_OPS)
    depth = 0
    for index, op in enumerate(ops, 1):
        if not isinstance(op, dict) or op.get('t') not in OP_TYPES:
            raise ValidationError("План: примітив %d невідомого виду." % index)
        if op['t'] == 'clipBegin':
            depth += 1
        elif op['t'] == 'clipEnd':
            depth -= 1
            if depth < 0:
                raise ValidationError("План: clipEnd без clipBegin (примітив %d)." % index)
    if depth:
        raise ValidationError("План: clipBegin без clipEnd.")
    return width, height, ops


def _dash(canv, op):
    dash = op.get('dash')
    if dash:
        canv.setDash([_num(v, "Штрих", 0, 100) * mm for v in dash])


def draw_plan(canv, height, ops):
    """Малює примітиви на полотні reportlab (початок координат — лівий низ; `y_pdf = (height − y) · мм`)."""
    font = _font()

    def pt(x, y):
        return _num(x, "x") * mm, (height - _num(y, "y")) * mm

    for op in ops:
        kind = op['t']
        if kind in ('poly', 'rect', 'line'):
            canv.saveState()
            stroke_color = _color(op.get('stroke'))
            fill_color = _color(op.get('fill')) if kind != 'line' else None
            canv.setLineWidth(max(0.0, _num(op.get('lw') or 0, "Товщина", 0, 20)) * mm)
            if stroke_color is not None:
                canv.setStrokeColor(stroke_color)
            if fill_color is not None:
                canv.setFillColor(fill_color)
            _dash(canv, op)
            if kind == 'line':
                x1, y1 = pt(op['x1'], op['y1'])
                x2, y2 = pt(op['x2'], op['y2'])
                canv.line(x1, y1, x2, y2)
            elif kind == 'rect':
                x, y = pt(op['x'], op['y'] + op['h'])
                canv.rect(
                    x,
                    y,
                    _num(op['w'], "w", 0, 5000) * mm,
                    _num(op['h'], "h", 0, 5000) * mm,
                    stroke=int(stroke_color is not None),
                    fill=int(fill_color is not None),
                )
            else:
                points = op.get('pts') or []
                if len(points) >= 2:
                    path = canv.beginPath()
                    path.moveTo(*pt(*points[0]))
                    for point in points[1:]:
                        path.lineTo(*pt(*point))
                    path.close()
                    canv.drawPath(path, stroke=int(stroke_color is not None), fill=int(fill_color is not None))
            canv.restoreState()
        elif kind == 'text':
            canv.saveState()
            x, y = pt(op['x'], op['y'])
            canv.translate(x, y)
            if op.get('rot'):
                canv.rotate(_num(op['rot'], "Кут", -360, 360))
            canv.setFillColor(_color(op.get('color'), colors.black))
            canv.setFont(font, _num(op.get('size') or 3, "Розмір", 0.5, 100) * mm)
            text = str(op.get('s', ''))[:200]
            anchor = op.get('anchor')
            if anchor == 'middle':
                canv.drawCentredString(0, 0, text)
            elif anchor == 'end':
                canv.drawRightString(0, 0, text)
            else:
                canv.drawString(0, 0, text)
            canv.restoreState()
        elif kind == 'clipBegin':
            canv.saveState()
            path = canv.beginPath()
            x, y = pt(op['x'], op['y'] + op['h'])
            path.rect(x, y, _num(op['w'], "w", 0, 5000) * mm, _num(op['h'], "h", 0, 5000) * mm)
            canv.clipPath(path, stroke=0, fill=0)
        else:  # clipEnd
            canv.restoreState()


@RENDERERS.register('plan_pdf', sequence=30)
def render_plan_pdf(env, payload):
    """API-19 `plan_pdf`: примітиви плану → PDF (аркуш A4/A3, вектор)."""
    _check_access(env, "Документи")
    width, height, ops = parse_plan(payload)
    buf = io.BytesIO()
    canv = canvas.Canvas(buf, pagesize=(width * mm, height * mm), pageCompression=1)
    canv.setTitle(str(payload.get('title') or "План складу")[:120])
    draw_plan(canv, height, ops)
    canv.showPage()
    canv.save()
    return 'plan.pdf', 'application/pdf', buf.getvalue()


# --- специфікація ----------------------------------------------------------------------------------------------------


def parse_tables(payload, env):
    """Таблиці з payload (від ядра) або — за `site_id` — розраховані сервером за чернеткою площадки."""
    tables = payload.get('tables')
    if tables is None:
        site = env['td.site'].browse(int(payload.get('site_id') or 0)).exists()
        if not site:
            raise ValidationError("Специфікація: передайте tables або site_id існуючої площадки.")
        from . import state as state_mod  # noqa: PLC0415 — state імпортує ORM-залежні модулі

        spec = rack_spec.build_spec(rack_spec.spec_slots(state_mod.checks_state(site)))
        return rack_spec.tables(spec)
    if not isinstance(tables, list) or not tables or len(tables) > MAX_TABLES:
        raise ValidationError("Специфікація: tables — від 1 до %d таблиць." % MAX_TABLES)
    out = []
    for index, table in enumerate(tables, 1):
        if not isinstance(table, dict):
            raise ValidationError("Таблиця %d: очікується об'єкт." % index)
        columns, rows = table.get('columns'), table.get('rows')
        if not isinstance(columns, list) or not columns or len(columns) > MAX_COLUMNS:
            raise ValidationError("Таблиця %d: columns — від 1 до %d назв." % (index, MAX_COLUMNS))
        if not isinstance(rows, list) or len(rows) > MAX_ROWS:
            raise ValidationError("Таблиця %d: rows — не більше %d рядків." % (index, MAX_ROWS))
        clean_rows = []
        for row in rows:
            if not isinstance(row, list) or len(row) != len(columns):
                raise ValidationError("Таблиця %d: рядок має %d клітинок." % (index, len(columns)))
            clean_rows.append(
                [
                    v
                    if v is None or (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v))
                    else str(v)[:300]
                    for v in row
                ]
            )
        out.append(
            {
                'name': str(table.get('name') or "Таблиця %d" % index)[:60],
                'columns': [str(c)[:80] for c in columns],
                'rows': clean_rows,
            }
        )
    return out


def _cell_text(value):
    if value is None:
        return ''
    if isinstance(value, float):
        return '%.2f' % value
    return str(value)


def spec_xlsx(title, tables):
    import xlsxwriter  # noqa: PLC0415

    buf = io.BytesIO()
    book = xlsxwriter.Workbook(buf, {'in_memory': True})
    head = book.add_format({'bold': True, 'bg_color': '#dfe6ec', 'border': 1, 'text_wrap': True, 'valign': 'top'})
    bold = book.add_format({'bold': True, 'font_size': 13})
    cell = book.add_format({'border': 1})
    dec = book.add_format({'border': 1, 'num_format': '0.00'})
    integer = book.add_format({'border': 1, 'num_format': '0'})
    used = set()
    for table in tables:
        name = ''.join('_' if ch in '[]:*?/\\' else ch for ch in table['name'])[:31] or 'Лист'
        base, n = name, 1
        while name.lower() in used:
            n += 1
            name = '%s %d' % (base[:28], n)
        used.add(name.lower())
        sheet = book.add_worksheet(name)
        sheet.write(0, 0, title or table['name'], bold)
        widths = [len(str(c)) for c in table['columns']]
        for col, label in enumerate(table['columns']):
            sheet.write(1, col, label, head)
        for r, row in enumerate(table['rows'], 2):
            for col, value in enumerate(row):
                if value is None:
                    sheet.write_blank(r, col, None, cell)
                elif isinstance(value, bool) or not isinstance(value, (int, float)):
                    sheet.write_string(r, col, str(value), cell)
                else:
                    sheet.write_number(
                        r, col, value, integer if float(value).is_integer() and isinstance(value, int) else dec
                    )
                widths[col] = max(widths[col], len(_cell_text(value)))
        for col, width in enumerate(widths):
            sheet.set_column(col, col, min(60, width + 2))
        sheet.freeze_panes(2, 0)
        if table['rows']:
            sheet.autofilter(1, 0, len(table['rows']) + 1, len(table['columns']) - 1)
    book.close()
    return buf.getvalue()


def spec_pdf(title, tables):
    font = _font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=title or "Специфікація",
    )
    h1 = ParagraphStyle('h1', fontName=font, fontSize=14, leading=18)
    h2 = ParagraphStyle('h2', fontName=font, fontSize=11, leading=14, spaceBefore=8)
    story = [Paragraph(_escape(title or "Специфікація стелажів"), h1), Spacer(1, 4 * mm)]
    avail = landscape(A4)[0] - 24 * mm
    for table in tables:
        story.append(Paragraph(_escape(table['name']), h2))
        data = [table['columns']] + [[_cell_text(v) for v in row] for row in table['rows']]
        widths = [max(stringWidth(row[i], font, 8) for row in data) + 8 for i in range(len(table['columns']))]
        if sum(widths) > avail:
            scale = avail / sum(widths)
            widths = [w * scale for w in widths]
        numeric = [
            bool(table['rows']) and all(row[i] is None or isinstance(row[i], (int, float)) for row in table['rows'])
            for i in range(len(table['columns']))
        ]
        style = [
            ('FONT', (0, 0), (-1, -1), font, 8),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dfe6ec')),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#7b8794')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ] + [('ALIGN', (i, 1), (i, -1), 'RIGHT') for i, num in enumerate(numeric) if num]
        story.append(Table(data, colWidths=widths, repeatRows=1, style=TableStyle(style)))
    doc.build(story)
    return buf.getvalue()


def _escape(text):
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


@RENDERERS.register('spec_pdf', sequence=31)
def render_spec(env, payload):
    """API-19 `spec_pdf`: специфікація стелажів → PDF (`format: pdf`) або XLSX (`format: xlsx`)."""
    _check_access(env, "Документи")
    fmt = payload.get('format') or 'pdf'
    if fmt not in ('pdf', 'xlsx'):
        raise ValidationError("Специфікація: format — pdf або xlsx.")
    title = str(payload.get('title') or "Специфікація стелажів")[:200]
    tables = parse_tables(payload, env)
    if fmt == 'xlsx':
        return (
            'spec.xlsx',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            spec_xlsx(title, tables),
        )
    return 'spec.pdf', 'application/pdf', spec_pdf(title, tables)
