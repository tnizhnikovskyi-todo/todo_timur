"""Детектор `pv_export` — «Експорт СЕС дешевше закупівлі» (R-20, вкладка «Електрика»; W3-B).

Сигнатура (R-14): `detect(env, rule, now) -> list[dict]`. Слоти вводів, де віддача в мережу `kwh_export × 4 ≥
min_export_kw`; різниця ціни закупівлі й ціни віддачі тарифу.
"""

from . import common

TITLE = "Експорт СЕС дешевше закупівлі"
SQL = """
SELECT ts_start, SUM(kwh_export), SUM(kwh_export * COALESCE(price, 0))
  FROM td_energy_interval
 WHERE role = 'incomer' AND quality <> 'missing' AND ts_start >= %s AND ts_start < %s
 GROUP BY ts_start ORDER BY ts_start
"""


def detect(env, rule, now):
    params = common.rule_params(rule)
    win = common.Window(env, rule, now)
    env.cr.execute(SQL, (win.lo, win.hi))
    rows = env.cr.fetchall()
    if win.sparse(ts for ts, _e, _w in rows):
        return []
    export = [(e or 0.0, w or 0.0) for _ts, e, w in rows if (e or 0.0) * 4.0 >= params["min_export_kw"]]
    total = sum(e for e, _w in export)
    if total <= 0:
        return []
    buy = common.weighted(sum(w for _e, w in export), total)
    tariff = env["td.energy.tariff"].sudo()._td_tariff_at(now)
    export_price = tariff.export_price if tariff else 0.0
    diff = buy - export_price
    if diff <= 0:
        return []
    qty = total * win.k_month * params["capture"]
    text = (
        "СЕС віддала в мережу %s кВт·год за %s діб по %s ₴/кВт·год, а закупівля коштує %s ₴/кВт·год. "
        "Краще спожити власну енергію."
    ) % (common.fmt_int(total), win.length, common.fmt_dec(export_price, 2), common.fmt_dec(buy, 2))
    evidence = {
        "export_kwh": round(total, 2), "buy_price": round(buy, 4), "export_price": round(export_price, 4),
        "slots": len(export),
    }  # fmt: skip
    return [common.finding("pv_export:*", TITLE, text, qty * diff, qty, evidence)]
