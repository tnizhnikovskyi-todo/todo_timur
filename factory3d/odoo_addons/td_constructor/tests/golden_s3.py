"""Золоті фікстури слайса S3 (F05 штрихкоди): Python ↔ JS.

    python3 factory3d/odoo_addons/td_constructor/tests/golden_s3.py --write   # перегенерувати fixtures/s3_barcode_golden.json

`static/tests/fixtures/s3_barcode_golden.json` будує ЦЕЙ файл (потрібні лише `qrcode` і `reportlab`); `node tools/test_core_s3.mjs`
звіряє з ним `core/constructor/barcode.js`, а `test_s3_labels` стежить, щоб фікстура збігалася з сервісом `services/labels.py`."""

import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / 'static' / 'tests' / 'fixtures'
NAME = 's3_barcode_golden.json'
TEXTS = ['PLT-01A', 'A', 'WH/Stock/Зона-1/R-01-B03-L2', '1234567890123', 'A-0001234567-B', 'https://example.com/f3d/PLT-01A?x=1', 'x' * 120]
CODE128 = ['PLT-01A', 'FG-R1-B01-L1', '1234567890123', 'A-0001234567-B', 'AB1234', '12', 'R-12345678', '~ ^ {}', 'a b  c']


def _labels():
    try:
        from ..services import labels  # noqa: PLC0415

        return labels
    except ImportError:  # запуск як скрипта: пакет td_constructor без Odoo (сервіс тягне odoo.exceptions → підміняємо)
        odoo = types.ModuleType('odoo')
        exc = types.ModuleType('odoo.exceptions')
        tools = types.ModuleType('odoo.tools')

        class _Err(Exception):
            pass

        exc.AccessError = exc.ValidationError = _Err
        tools.file_path = lambda path: str(Path('/home/user/odoo19/addons') / path)
        odoo.exceptions, odoo.tools = exc, tools
        pkg = types.ModuleType('td_constructor')
        pkg.__path__ = [str(ROOT)]
        sub = types.ModuleType('td_constructor.services')
        sub.__path__ = [str(ROOT / 'services')]
        sys.modules.update({'odoo': odoo, 'odoo.exceptions': exc, 'odoo.tools': tools, 'td_constructor': pkg, 'td_constructor.services': sub})
        from td_constructor.services import labels  # noqa: PLC0415

        return labels


def build():
    labels = _labels()
    qr = [
        {'text': t, 'ecc': ecc, 'mask': mask, 'rows': labels.qr_rows(t, ecc, mask)}
        for t in TEXTS
        for ecc in ('L', 'M', 'Q', 'H')
        for mask in (0, 3, 5, 7)
    ]
    code128 = [{'text': t, 'values': labels.code128_values(t), 'modules': labels.code128_modules(t)} for t in CODE128]
    return {'patterns': labels.C128, 'qr': qr, 'code128': code128}


if __name__ == '__main__':
    data = build()
    text = json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n'
    if '--write' in sys.argv:
        (FIXTURES / NAME).write_text(text, encoding='utf-8')
        print('записано', FIXTURES / NAME, len(text))
    else:
        print(text[:200])
