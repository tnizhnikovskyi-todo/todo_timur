"""R-11: тренд за 1/24 год із `td.reading` (середнє у відрізку, порожній відрізок → null)."""

from datetime import timedelta

from .signals import iso, now

SERIES = {"pel": "chp/gen/p_kw", "qth": "chp/ht/q_total", "gas": "chp/gas/flow"}
STEP_S = {1: 30, 24: 300}


def build(env, range_h):
    step = STEP_S[range_h]
    n = range_h * 3600 // step
    end = now(env).replace(microsecond=0)
    t0 = end - timedelta(hours=range_h)
    series = {}
    sigs = {s.code: s.id for s in env["td.signal"].sudo().search([("code", "in", list(SERIES.values()))])}
    for key, code in SERIES.items():
        points = [None] * n
        sid = sigs.get(code)
        if sid:
            env.cr.execute(
                """
                SELECT floor(extract(epoch FROM (ts - %s)) / %s)::int AS b, avg(value)
                  FROM td_reading
                 WHERE signal_id = %s AND ts >= %s AND ts < %s AND quality <> 'bad' AND value IS NOT NULL
                 GROUP BY b
                """,
                (t0, step, sid, t0, end),
            )
            for b, avg in env.cr.fetchall():
                if 0 <= b < n:
                    points[b] = round(avg, 1)
        series[key] = points
    return {"range_h": range_h, "step_s": step, "t0": iso(t0), "series": series}
