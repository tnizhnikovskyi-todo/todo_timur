"""Етикетки: PDF і PNG зі специфікації ядра (F05, API-19 `labels_pdf`; MERGE.md §3.5).

Ядро (`core/constructor/labels.js`) вибирає комірки, будує вміст і сітку аркуша; сервер лише малює:
Code128 / QR, код великим, додаткові рядки, стрілка ярусу, шрифт зі вбудованою кирилицею (NotoSans з `web`;
«лише латиниця» — Helvetica). Геометрія етикетки — та сама, що в `labelSvg` ядра (мм), тож перегляд у редакторі
збігається з PDF. Code128 кодується тим самим алгоритмом, що в `barcode.js` (золоті фікстури
`static/tests/fixtures/s3_barcode_golden.json`); QR — бібліотека `qrcode` у режимі byte.

Реєструє рендерер `labels_pdf` у `RENDERERS` (payload: `format: pdf | png`). Без ORM, крім читання `labels_max`."""

import io
import math
import zipfile

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from odoo.exceptions import AccessError, ValidationError
from odoo.tools import file_path

from .registry import RENDERERS

# --- Code128 (дзеркало core/constructor/barcode.js) ---------------------------------------------------------------
C128 = (
    "212222 222122 222221 121223 121322 131222 122213 122312 132212 221213 221312 231212 112232 "
    "122132 122231 113222 123122 123221 223211 221132 221231 213212 223112 312131 311222 321122 "
    "321221 312212 322112 322211 212123 212321 232121 111323 131123 131321 112313 132113 132311 "
    "211313 231113 231311 112133 112331 132131 113123 113321 133121 313121 211331 231131 213113 "
    "213311 213131 311123 311321 331121 312113 312311 332111 314111 221411 431111 111224 111422 "
    "121124 121421 141122 141221 112214 112412 122114 122411 142112 142211 241211 221114 413111 "
    "241112 134111 111242 121142 121241 114212 124112 124211 411212 421112 421211 212141 214121 "
    "412121 111143 111341 131141 114113 114311 411113 411311 113141 114131 311141 411131 211412 "
    "211214 211232 2331112"
).split()
START_B, START_C, CODE_B, CODE_C, STOP = 104, 105, 100, 99, 106


def is_printable_ascii(text):
    return all(32 <= ord(ch) <= 126 for ch in text)


def _digit_run(text, i):
    n = 0
    while i + n < len(text) and '0' <= text[i + n] <= '9':
        n += 1
    return n


def code128_values(text):
    """Значення Code128 (старт, дані, контрольна сума, стоп): цифрові серії ≥ 4 — набір C (як у barcode.js)."""
    if not text:
        raise ValidationError("Code128: порожній рядок.")
    if not is_printable_ascii(text):
        raise ValidationError("Code128: лише друкований ASCII (для інших символів — QR).")
    out = []
    run0 = _digit_run(text, 0)
    if run0 >= 4 or (run0 == len(text) and run0 >= 2):
        out.append(START_C)
        current = 'C'
    else:
        out.append(START_B)
        current = 'B'
    i = 0
    while i < len(text):
        run = _digit_run(text, i)
        if current == 'B':
            if run >= 6 or (run >= 4 and i + run == len(text)):
                if run % 2:
                    out.append(ord(text[i]) - 32)
                    i += 1
                out.append(CODE_C)
                current = 'C'
                continue
            out.append(ord(text[i]) - 32)
            i += 1
        elif run >= 2:
            out.append(int(text[i : i + 2]))
            i += 2
        else:
            out.append(CODE_B)
            current = 'B'
    checksum = out[0] + sum(v * k for k, v in enumerate(out[1:], 1))
    out += [checksum % 103, STOP]
    return out


def code128_modules(text):
    """Модулі Code128 рядком «1» (смуга) / «0» (пробіл) без тихих зон."""
    bits = []
    for value in code128_values(text):
        bar = True
        for ch in C128[value]:
            bits.append(('1' if bar else '0') * int(ch))
            bar = not bar
    return ''.join(bits)


def qr_rows(text, ecc='M', mask=None):
    """Матриця QR (byte, без тихої зони): список рядків «0»/«1»; `mask` — для золотих фікстур."""
    import qrcode
    from qrcode import util

    levels = {
        'L': qrcode.constants.ERROR_CORRECT_L,
        'M': qrcode.constants.ERROR_CORRECT_M,
        'Q': qrcode.constants.ERROR_CORRECT_Q,
        'H': qrcode.constants.ERROR_CORRECT_H,
    }
    code = qrcode.QRCode(error_correction=levels[ecc], border=0, mask_pattern=mask)
    code.add_data(util.QRData(text.encode('utf-8'), mode=util.MODE_8BIT_BYTE), optimize=0)
    code.make()
    return [''.join('1' if cell else '0' for cell in row) for row in code.get_matrix()]


# --- примітиви етикетки (мм, початок — лівий верхній кут; дзеркало labelSvg) -------------------------------------
BAR_QUIET = 10  # модулів тихої зони з кожного боку Code128
QR_QUIET = 4


def kind_for(code, kind):
    return 'qr' if kind == 'qr' or not is_printable_ascii(code) else 'code128'


def label_primitives(label, kind, w, h):
    """Примітиви: ('rect', x, y, w, h) · ('text', x, y_baseline, size, bold, align, text, max_w) · ('poly', pts)."""
    code = label['code']
    lines = label.get('lines') or []
    m = min(2.2, w * 0.04, h * 0.06)
    line_h = min(3.6, h * 0.1)
    prim = []
    if kind_for(code, kind) == 'qr':
        rows = qr_rows(code)
        side = min(h - 2 * m, w * 0.46)
        mod = side / (len(rows) + 2 * QR_QUIET)
        y0 = (h - side) / 2
        for r, row in enumerate(rows):
            c = 0
            while c < len(row):
                if row[c] == '1':
                    e = c
                    while e < len(row) and row[e] == '1':
                        e += 1
                    prim.append(('rect', m + (QR_QUIET + c) * mod, y0 + (QR_QUIET + r) * mod, (e - c) * mod, mod))
                    c = e
                else:
                    c += 1
        tx = m + side + m * 0.8
        tw = w - tx - m
        fs = min(h * 0.24, tw / (len(code) * 0.56))
        prim.append(('text', tx, h / 2 - (line_h * 0.2 if lines else 0) + fs * 0.35, fs, True, 'left', code, tw))
        for i, text in enumerate(lines):
            prim.append(
                ('text', tx, h / 2 + fs * 0.35 + line_h * (i + 1) * 0.95, line_h * 0.8, False, 'left', text, tw)
            )
    else:
        top = m + len(lines) * line_h
        for i, text in enumerate(lines):
            prim.append(('text', m, m + line_h * (i + 0.8), line_h * 0.8, False, 'left', text, w - 2 * m))
        fs = min(h * 0.26, (w - 2 * m) / (len(code) * 0.6))
        bh = max(4.0, h - top - fs * 1.25 - m)
        modules = code128_modules(code)
        mod = (w - 2 * m) / (len(modules) + 2 * BAR_QUIET)
        i = 0
        while i < len(modules):
            if modules[i] == '1':
                j = i
                while j < len(modules) and modules[j] == '1':
                    j += 1
                prim.append(('rect', m + (BAR_QUIET + i) * mod, top, (j - i) * mod, bh))
                i = j
            else:
                i += 1
        prim.append(('text', w / 2, top + bh + fs * 0.95, fs, True, 'center', code, w - 2 * m))
    arrow = label.get('arrow')
    if arrow in ('up', 'down'):
        s = min(h * 0.28, w * 0.14)
        x, y = w - s - m, m
        if arrow == 'up':
            pts = [
                (x + s / 2, y),
                (x + s, y + s * 0.6),
                (x + s * 0.7, y + s * 0.6),
                (x + s * 0.7, y + s),
                (x + s * 0.3, y + s),
                (x + s * 0.3, y + s * 0.6),
                (x, y + s * 0.6),
            ]
        else:
            pts = [
                (x + s / 2, y + s),
                (x, y + s * 0.4),
                (x + s * 0.3, y + s * 0.4),
                (x + s * 0.3, y),
                (x + s * 0.7, y),
                (x + s * 0.7, y + s * 0.4),
                (x + s, y + s * 0.4),
            ]
        prim.append(('poly', pts))
    return prim


# --- перевірка вхідних даних --------------------------------------------------------------------------------------
MAX_LINES = 4
MAX_TEXT = 80
MAX_PNG_PAGES = 12  # аркуш PNG 300 dpi ≈ 26 МБ у пам'яті: більші замовлення — лише PDF


def _num(value, name, lo, hi):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError("Етикетки: поле «%s» має бути числом." % name) from None
    if not math.isfinite(number) or not lo <= number <= hi:
        raise ValidationError("Етикетки: поле «%s» поза межами %s…%s." % (name, lo, hi))
    return number


def parse_payload(payload, labels_max):
    """Нормалізує й перевіряє тіло запиту; помилки — ValidationError."""
    if not isinstance(payload, dict):
        raise ValidationError("Етикетки: тіло запиту має бути об'єктом.")
    page = payload.get('page') or {}
    grid = payload.get('grid') or {}
    fmt = payload.get('format') or 'pdf'
    if fmt not in ('pdf', 'png'):
        raise ValidationError("Етикетки: format — pdf або png.")
    font = payload.get('font') or 'cyr'
    if font not in ('cyr', 'latin'):
        raise ValidationError("Етикетки: font — cyr або latin.")
    kind = payload.get('kind') or 'code128'
    if kind not in ('code128', 'qr'):
        raise ValidationError("Етикетки: kind — code128 або qr.")
    labels = payload.get('labels')
    if not isinstance(labels, list) or not labels:
        raise ValidationError("Етикетки: немає що друкувати.")
    if len(labels) > labels_max:
        raise ValidationError("Етикеток забагато: %s (ліміт %s)." % (len(labels), labels_max))
    parsed = []
    for item in labels:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get('code'), str)
            or not item['code']
            or len(item['code']) > 64
        ):
            raise ValidationError("Етикетки: кожна етикетка має мати код (рядок до 64 символів).")
        lines = item.get('lines') or []
        if (
            not isinstance(lines, list)
            or len(lines) > MAX_LINES
            or any(not isinstance(t, str) or len(t) > MAX_TEXT for t in lines)
        ):
            raise ValidationError("Етикетки: рядків — до %s, до %s символів кожен." % (MAX_LINES, MAX_TEXT))
        arrow = item.get('arrow')
        if arrow not in (None, 'up', 'down'):
            raise ValidationError("Етикетки: стрілка — up або down.")
        parsed.append({'code': item['code'], 'lines': lines, 'arrow': arrow})
    spec = {
        'format': fmt,
        'font': font,
        'kind': kind,
        'page_w': _num(page.get('w'), 'page.w', 20, 1000),
        'page_h': _num(page.get('h'), 'page.h', 20, 1000),
        'cols': int(_num(grid.get('cols'), 'grid.cols', 1, 100)),
        'rows': int(_num(grid.get('rows'), 'grid.rows', 1, 100)),
        'x0': _num(grid.get('x0'), 'grid.x0', 0, 1000),
        'y0': _num(grid.get('y0'), 'grid.y0', 0, 1000),
        'w': _num(grid.get('w'), 'grid.w', 5, 1000),
        'h': _num(grid.get('h'), 'grid.h', 5, 1000),
        'gx': _num(grid.get('gx', 0), 'grid.gx', 0, 100),
        'gy': _num(grid.get('gy', 0), 'grid.gy', 0, 100),
        'skip': int(_num(payload.get('skip', 0), 'skip', 0, 100000)),
        'labels': parsed,
    }
    return spec


def paginate(spec):
    """[[(label, x, y)]] по аркушах; `skip` зсуває початок першого аркуша (як paginate у ядрі)."""
    per_page = spec['cols'] * spec['rows']
    slot = spec['skip'] % per_page
    pages = {}
    for label in spec['labels']:
        page, k = divmod(slot, per_page)
        x = spec['x0'] + (k % spec['cols']) * (spec['w'] + spec['gx'])
        y = spec['y0'] + (k // spec['cols']) * (spec['h'] + spec['gy'])
        pages.setdefault(page, []).append((label, x, y))
        slot += 1
    return [pages.get(i, []) for i in range(max(pages) + 1)]


# --- PDF (reportlab) ---------------------------------------------------------------------------------------------
PT = 72 / 25.4
FONT_FILE = 'web/static/fonts/sign/NotoSans-Reg.ttf'
FONT_NAME = 'F3DNotoSans'


def _font_path():
    return file_path(FONT_FILE)


def _pdf_font(canvas_font):
    """Реєструє шрифт з кирилицею (один раз); «latin» → Helvetica."""
    if canvas_font == 'latin':
        return 'Helvetica'
    if FONT_NAME not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT_NAME, _font_path()))
    return FONT_NAME


def _fit(font_name, text, size_mm, max_w_mm):
    """Розмір шрифту (мм), щоб текст вмістився в ширину."""
    width = stringWidth(text, font_name, size_mm * PT) / PT
    return size_mm if width <= max_w_mm or width == 0 else size_mm * max_w_mm / width


def render_pdf(spec):
    font = _pdf_font(spec['font'])
    buf = io.BytesIO()
    page_h = spec['page_h']
    pdf = canvas.Canvas(buf, pagesize=(spec['page_w'] * PT, page_h * PT))
    pdf.setTitle("Етикетки")
    for index, entries in enumerate(paginate(spec)):
        if index:
            pdf.showPage()
        for label, x, y in entries:
            for prim in label_primitives(label, spec['kind'], spec['w'], spec['h']):
                if prim[0] == 'rect':
                    _, rx, ry, rw, rh = prim
                    pdf.rect((x + rx) * PT, (page_h - y - ry - rh) * PT, rw * PT, rh * PT, stroke=0, fill=1)
                elif prim[0] == 'poly':
                    path = pdf.beginPath()
                    for k, (px, py) in enumerate(prim[1]):
                        (path.moveTo if k == 0 else path.lineTo)((x + px) * PT, (page_h - y - py) * PT)
                    path.close()
                    pdf.drawPath(path, stroke=0, fill=1)
                else:
                    _, tx, ty, size, bold, align, text, max_w = prim
                    size = _fit(font, text, size, max_w)
                    obj = pdf.beginText()
                    obj.setFont(font, size * PT)
                    obj.setTextRenderMode(2 if bold else 0)  # синтетичний напівжирний: шрифт «Reg» без Bold
                    if bold:
                        pdf.setLineWidth(size * PT * 0.025)
                    width = stringWidth(text, font, size * PT) / PT
                    start = tx - width / 2 if align == 'center' else tx
                    obj.setTextOrigin((x + start) * PT, (page_h - y - ty) * PT)
                    obj.textOut(text)
                    pdf.drawText(obj)
    pdf.save()
    return buf.getvalue()


# --- PNG (Pillow): аркуш 300 dpi; кілька аркушів — ZIP -----------------------------------------------------------
def render_png(spec, dpi=300):
    from PIL import Image, ImageDraw, ImageFont

    k = dpi / 25.4
    pages = paginate(spec)
    if len(pages) > MAX_PNG_PAGES:
        raise ValidationError(
            "PNG: до %s аркушів (зараз %s); для більшого обсягу оберіть PDF." % (MAX_PNG_PAGES, len(pages))
        )
    files = []
    for index, entries in enumerate(pages, 1):
        img = Image.new('RGB', (round(spec['page_w'] * k), round(spec['page_h'] * k)), 'white')
        draw = ImageDraw.Draw(img)
        for label, x, y in entries:
            for prim in label_primitives(label, spec['kind'], spec['w'], spec['h']):
                if prim[0] == 'rect':
                    _, rx, ry, rw, rh = prim
                    draw.rectangle(
                        [
                            round((x + rx) * k),
                            round((y + ry) * k),
                            max(round((x + rx + rw) * k) - 1, round((x + rx) * k)),
                            max(round((y + ry + rh) * k) - 1, round((y + ry) * k)),
                        ],
                        fill='black',
                    )
                elif prim[0] == 'poly':
                    draw.polygon([((x + px) * k, (y + py) * k) for px, py in prim[1]], fill='black')
                else:
                    _, tx, ty, size, bold, align, text, max_w = prim
                    fnt = ImageFont.truetype(_font_path(), max(6, round(size * k)))
                    width = draw.textlength(text, font=fnt) / k
                    if width > max_w > 0:
                        fnt = ImageFont.truetype(_font_path(), max(6, round(size * k * max_w / width)))
                        width = draw.textlength(text, font=fnt) / k
                    start = tx - width / 2 if align == 'center' else tx
                    draw.text(
                        ((x + start) * k, (y + ty) * k),
                        text,
                        font=fnt,
                        fill='black',
                        anchor='ls',
                        stroke_width=1 if bold else 0,
                        stroke_fill='black',
                    )
        out = io.BytesIO()
        img.save(out, format='PNG', dpi=(dpi, dpi))
        files.append(('labels_%d.png' % index, out.getvalue()))
    if len(files) == 1:
        return files[0]
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, data in files:
            archive.writestr(name, data)
    return 'labels_png.zip', zbuf.getvalue()


def _labels_max(env):
    try:
        return int(env['ir.config_parameter'].sudo().get_param('td.constructor.labels_max', 5000))
    except (TypeError, ValueError):
        return 5000


@RENDERERS.register('labels_pdf', sequence=10)
def render_labels(env, payload):
    """API-19 `labels_pdf`: специфікація етикеток → PDF (або PNG при `format: png`). Читання — група «Перегляд»."""
    if not env.user.has_group('td_factory3d.group_td_user'):
        raise AccessError("Етикетки доступні користувачам конструктора (група «Перегляд»).")
    spec = parse_payload(payload, _labels_max(env))
    if spec['format'] == 'png':
        name, data = render_png(spec)
        return name, ('application/zip' if name.endswith('.zip') else 'image/png'), data
    return 'labels.pdf', 'application/pdf', render_pdf(spec)
