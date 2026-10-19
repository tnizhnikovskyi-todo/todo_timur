"""Заглушки API-11…API-24 (W0-B): відповідь `not_implemented` за правилами API-01…10 (§7 SPEC).

Слайс, що реалізує маршрут, замінює виклик `not_implemented()` у СВОЄМУ файлі контролера."""

NOT_IMPLEMENTED = 'not_implemented'


def not_implemented(api):
    """`{ok: false, code, message}` (HTTP 200), як очікувана помилка; `api` — номер із §3.5 MERGE.md, напр. «API-11»."""
    return {'ok': False, 'code': NOT_IMPLEMENTED, 'message': "Функцію ще не реалізовано (%s)." % api}
