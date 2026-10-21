"""R-31 п. 6: демо-історія порталу — завдання подачі, карти розкрою й показання стосів для демо-бази.

На демо-базі (R-27) без стенда немає ні завдань порталу, ні карт розкрою, тож ланцюжок лист → завдання → карта → МО
у 3D порожній. Цей крок будує його з даних демо: кожне завдання розкрою (SAW-1…3, NEST-1) МО в роботі дає завдання
подачі плит зі стосів, з яких зарезервовано сировину МО (по завданню на стос і партію), і карту розкрою зі станом
`released` та відходами 6…15 % (детерміновано за назвою МО). Завдання йдуть по черзі — портал один. Останнє завдання
МО в роботі лишається активним на момент «зараз» (демо-годинник), завдання МО «готове» — у черзі.
Не чіпає базу, де вже є завдання порталу, і не працює поза демо-базою. Ідемпотентний.
"""

import zlib
from datetime import timedelta

from odoo import fields

from .portal import CYCLE_S

PERIOD_MIN_S, PERIOD_SPAN_S = 70, 40  # секунд між листами завдання: 70…109 (за назвою МО)
GAP_S = 20  # пауза порталу між завданнями
LEAD_S = 5 * 60  # завдання порталу починається за 5 хв до початку операції розкрою
MIN_THICKNESS = 8  # основна плита: ≥ 8 мм (R-16 п. 1)
CUT_STATES = ("done", "progress", "ready")
WASTE_MIN, WASTE_SPAN = 6.0, 9.0  # відходи карти: 6,0…14,9 %


def is_demo(env):
    """Демо-база — є простої або записи журналу часу з позначкою `demo` (як для `hooks.demo_rates`)."""
    return bool(
        env["td.downtime"].search_count([("reason_source", "=", "demo")], limit=1)
        or env["mrp.workcenter.productivity"].search_count([("td_source", "=", "demo")], limit=1)
    )


def _seed(text):
    return zlib.crc32(text.encode())


def _groups(wo):
    """`[(стос, партія, товар, листів)]` — сировина МО, зарезервована зі стосів `PLT-*` (за рядками руху)."""
    groups = {}
    for move in wo.production_id.move_raw_ids:
        if move.state == "cancel" or (move.product_id.td_thickness_mm or 0) < MIN_THICKNESS:
            continue
        for line in move.move_line_ids:
            loc = line.location_id
            if loc.td_loc_kind == "stack" and (loc.td_code or "").startswith("PLT-") and line.quantity >= 1:
                key = (loc, line.lot_id, move.product_id)
                groups[key] = groups.get(key, 0) + int(round(line.quantity))
    return [(*key, n) for key, n in groups.items()]


def _demo_now(env, wos):
    """Момент «зараз»: демо-годинник переглядача, інакше через 14 хв після останнього початку розкрою."""
    now = env["td.bottleneck"]._td_demo_clock()
    if now:
        return now
    starts = [w.date_start for w in wos if w.date_start]
    return (max(starts) + timedelta(minutes=14)) if starts else fields.Datetime.now()


def _map_for(env, wo, product, sheets):
    """Карта розкрою МО (одна на МО): стан `released`, відходи за назвою МО; без розмірів листа карти немає."""
    tmpl = product.product_tmpl_id
    if not (tmpl.td_sheet_length_mm and tmpl.td_sheet_width_mm and tmpl.td_thickness_mm):
        return env["td.cut.map"]
    mo = wo.production_id
    waste = round(WASTE_MIN + (_seed(mo.name) % int(WASTE_SPAN * 10)) / 10.0, 1)
    return env["td.cut.map"].create(
        {
            "production_id": mo.id,
            "workorder_id": wo.id,
            "material_product_id": product.id,
            "sheet_length_mm": tmpl.td_sheet_length_mm,
            "sheet_width_mm": tmpl.td_sheet_width_mm,
            "thickness_mm": tmpl.td_thickness_mm,
            "qty": mo.product_qty,
            "state": "released",
            "plan_sheets": sheets,
            "plan_waste_pct": waste,
            "released_at": wo.date_start or False,
        }
    )


def demo_gantry(env):
    """Створити демо-історію порталу (див. модуль). Повертає `{"gantry_jobs": N, "cut_maps": M}`."""
    env = env(su=True)
    res = {"gantry_jobs": 0, "cut_maps": 0}
    Job = env["td.gantry.job"].with_context(active_test=False, tracking_disable=True)
    if not is_demo(env) or Job.search_count([], limit=1):
        return res
    targets = env["td.gantry.stack"].GANTRY_TARGETS
    wos = env["mrp.workorder"].search(
        [
            ("workcenter_id.td_code", "in", list(targets)),
            ("state", "in", CUT_STATES),
            ("production_id.state", "not in", ("cancel", "draft", "done")),
        ],
        order="date_start, id",
    )
    if not wos:
        return res
    now = _demo_now(env, wos)
    plan = []
    for wo in wos:
        if wo.state != "ready" and not wo.date_start:
            continue
        for loc, lot, product, n in _groups(wo):
            plan.append((wo, loc, lot, product, n))
    # завдання по черзі: портал один; початок — за 5 хв до операції, але не раніше кінця попереднього
    progress = [i for i, p in enumerate(plan) if p[0].state == "progress"]
    active = max(progress, key=lambda i: (plan[i][0].date_start, plan[i][0].id)) if progress else None
    cursor = None
    maps = {}
    taken = {}  # код стосу → час останнього листа, поданого з нього
    for i, (wo, loc, lot, product, n) in enumerate(plan):
        mo = wo.production_id
        period = PERIOD_MIN_S + _seed(mo.name) % PERIOD_SPAN_S
        stack = env["td.gantry.stack"].search([("location_id", "=", loc.id)], limit=1)
        if not stack:
            continue
        vals = {
            "type": "feed",
            "origin": "odoo",
            "stack_id": stack.id,
            "target_workcenter_id": wo.workcenter_id.id,
            "sheets": n,
            "product_id": product.id,
            "lot_id": lot.id or False,
            "external_ref": mo.name,
            "production_id": mo.id,
            "workorder_id": wo.id,
            "ws_id": "wj-%05d" % (412 + res["gantry_jobs"]),
        }
        if wo.state == "ready":
            vals.update(state="queued", done=0)
        else:
            if i == active:  # у роботі на «зараз»: останній покладений лист — 25 с тому, наступний ще попереду
                state, done_n = "active", n - 1
                start = now - timedelta(seconds=25 + done_n * period)
            else:
                state, done_n = "done", n
                start = max(
                    wo.date_start - timedelta(seconds=LEAD_S), (cursor or wo.date_start) + timedelta(seconds=GAP_S)
                )
            last = start + timedelta(seconds=period * done_n)
            log = [
                {
                    "id": 100 * (res["gantry_jobs"] + 1) + k,
                    "ts": (start + timedelta(seconds=period * (k + 1))).isoformat(),
                    "stack": stack.code,
                    "lot": lot.name or "",
                }
                for k in range(done_n)
            ]
            vals.update(
                state=state,
                done=done_n,
                started=start,
                ws_created=start - timedelta(seconds=30),
                sheet_log=log,
                finished=last if state == "done" else False,
            )
            if state == "done":
                cursor = last
            if done_n:
                taken[stack.code] = max(taken.get(stack.code, last), last)
        job = Job.create(vals)
        res["gantry_jobs"] += 1
        if mo.id not in maps:
            cmap = _map_for(env, wo, product, sum(p[4] for p in plan if p[0].production_id == mo))
            maps[mo.id] = cmap
            res["cut_maps"] += bool(cmap)
            if cmap:
                cmap.gantry_job_id = job
        if maps[mo.id]:
            job.cut_map_id = maps[mo.id]
    _seed_stacks(env, taken, now)
    return res


def _seed_stacks(env, taken, now):
    """Показання порталу для стосів із залишком: `ws_qty` = Odoo − подане в МО, що ще не закрито (R-15 п. 2)."""
    Stack = env["td.gantry.stack"].with_context(active_test=False, tracking_disable=True)
    real_now = fields.Datetime.now()
    for stack in Stack.search([]):
        stack._td_refresh()
        if stack.odoo_qty <= 0:
            continue
        product = stack.odoo_product_id
        stack.write(
            {
                "ws_qty": max(int(stack.expected_qty), 0),
                "ws_product": product.default_code or False,
                "ws_lot": stack.odoo_lot_id.name or False,
                "ws_updated": taken.get(stack.code) or (now - timedelta(seconds=3 * CYCLE_S * 60)),
                "ws_seen": real_now,
            }
        )
        stack._td_refresh()
