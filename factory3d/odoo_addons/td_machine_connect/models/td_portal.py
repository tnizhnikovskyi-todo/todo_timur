"""R-31: портальний склад плит у 3D — вузли payload (`equipment.GANTRY-1.portal`, `locations[PLT-*].portal`) і плитка.

Ланцюжок даних для 3D і картки: лист (запис журналу `sheet_log` завдання) → завдання порталу → карта розкрою
(`td.cut.map`, відходи плану) → виробниче замовлення. Читання — від імені системи (`sudo`): це зведення, яке бачить
кожен користувач «3D Завод»; видимість плитки обмежена групою `td_factory3d.group_td_user`.
"""

from odoo import api, models

from ..tools import portal as portal_tools
from ..tools.states import parse_ts
from .td_machine import local

OPEN_JOB = ("sent", "queued", "active")
CUT_PLANNED = ("planned", "released", "running", "done")  # у цих станах `plan_waste_pct` — результат оптимізатора


class TdPortal(models.AbstractModel):
    _name = "td.portal"
    _description = "Портал: дані для 3D і плитки"

    @api.model
    def _td_can_see(self):
        return self.env.su or self.env.user.has_group("td_factory3d.group_td_user")

    @api.model
    def _td_now(self):
        """«Зараз» — як у вузькому місці: демо-годинник «Переглядача» (лише демо-бази), інакше реальний час."""
        return self.env["td.bottleneck"]._td_now()

    # --- завдання за добу -----------------------------------------------------------------------------
    @api.model
    def _td_day_jobs(self, now):
        """Завдання подачі за київську добу `now`: відкриті й завершені з початку доби, не пізніші за `now`."""
        d0 = portal_tools.day_start(now)
        jobs = (
            self.env["td.gantry.job"]
            .sudo()
            .search(
                [
                    ("type", "=", "feed"),
                    ("state", "in", OPEN_JOB + ("done",)),
                    "|",
                    ("state", "in", OPEN_JOB),
                    ("finished", ">=", d0),
                ],
                order="id desc",
                limit=portal_tools.JOBS_MAX,
            )
        )
        jobs = jobs.filtered(lambda j: not j.started or j.started <= now)
        return jobs.sorted(lambda j: (j.started or now, j.id))

    @api.model
    def _td_cut_maps(self, jobs):
        """`{job.id: td.cut.map}`: карта, прив'язана до завдання, інакше остання не скасована карта його МО."""
        Cut = self.env["td.cut.map"].sudo()
        by_prod = {}
        prods = jobs.mapped("production_id")
        if prods:
            for cmap in Cut.search([("production_id", "in", prods.ids), ("state", "!=", "cancel")], order="id"):
                by_prod[cmap.production_id.id] = cmap  # остання за id перекриває попередні
        return {j.id: j.cut_map_id or by_prod.get(j.production_id.id) or Cut for j in jobs}

    @api.model
    def _td_job_node(self, job, cmap, d0, now):
        prod = job.production_id
        log = []
        for entry in job.sheet_log or []:
            ts = parse_ts(entry.get("ts"))
            if ts and d0 <= ts <= now:
                log.append((ts, entry.get("stack") or ""))
        log.sort(key=lambda e: e[0])
        log = log[-portal_tools.LOG_MAX :]
        finished = job.finished if job.finished and job.finished <= now else False
        state, done = job.state, job.done
        if state == "done" and not finished:
            state, done = "active", len(log)  # демо-годинник «до» завершення: на момент `now` завдання ще виконується
        node = {
            "id": job.name,
            "ws": job.ws_id or "",
            "state": state,
            "stack": job.stack_id.code or (log[0][1] if log else ""),
            "target": job.target_code or "",
            "sheets": job.sheets,
            "done": done,
            "product": job.product_id.default_code or "",
            "name": job.product_id.name or "",
            "lot": job.lot_id.name or "",
            "ref": job.external_ref or prod.name or "",
            "mo": prod.name or "",
            "s": portal_tools.to_sec(job.started, d0),
            "e": portal_tools.to_sec(finished, d0),
            "log": [[portal_tools.to_sec(ts, d0), code] for ts, code in log],
        }
        if prod:
            node["mo_product"] = prod.product_id.name or ""
            node["origin"] = prod.origin or ""
        if cmap:
            planned = cmap.state in CUT_PLANNED and cmap.plan_sheets > 0
            node["cut"] = {
                "name": cmap.name,
                "state": cmap.state,
                "sheets": cmap.plan_sheets,
                "waste_pct": round(cmap.plan_waste_pct, 1) if planned else None,
            }
        return node

    @api.model
    def _td_equipment_node(self, now=None):
        """`equipment["GANTRY-1"].portal` (R-31 п. 1): завдання доби з ланцюжком, зведення «сьогодні»."""
        now = now or self._td_now()
        d0 = portal_tools.day_start(now)
        jobs = self._td_day_jobs(now)
        maps = self._td_cut_maps(jobs)
        nodes = [self._td_job_node(j, maps[j.id], d0, now) for j in jobs]
        return {
            "day": local(now, "%Y-%m-%d"),
            "now": portal_tools.to_sec(now, d0),
            "cycle_s": portal_tools.CYCLE_S,
            "jobs": nodes,
            "today": self._td_today(jobs, maps),
        }

    @api.model
    def _td_today(self, jobs, maps):
        return {
            "jobs": len(jobs),
            "sheets": sum(j.done for j in jobs),
            "waste_pct": portal_tools.waste_weighted(
                (
                    maps[j.id].plan_waste_pct if maps[j.id].state in CUT_PLANNED and maps[j.id].plan_sheets else None,
                    j.sheets,
                )
                for j in jobs
            ),
        }

    # --- стоси ----------------------------------------------------------------------------------------
    @api.model
    def _td_stack_nodes(self, codes=None, now=None):
        """`locations[PLT-*].portal` (R-31 п. 2): `{код: вузол}` для стосів (`codes=None` — усі).

        `qty` — листів за показанням порталу на момент `upd` (секунди доби; без часу показання — `now`), якщо даних
        порталу немає — за Odoo (`src="odoo"`). Залишок на довільний `t` рахує клієнт: показання ± листи журналів.
        """
        now = now or self._td_now()
        d0 = portal_tools.day_start(now)
        domain = [("code", "in", list(codes))] if codes is not None else []
        stacks = self.env["td.gantry.stack"].sudo().search(domain)
        if not stacks:
            return {}
        jobs = (
            self.env["td.gantry.job"]
            .sudo()
            .search(
                [("type", "=", "feed"), ("state", "in", OPEN_JOB), ("stack_id", "in", stacks.ids)],
                order="priority desc, id",
            )
        )
        nxt = {}
        for job in jobs.sorted(lambda j: (j.state != "active",)):
            nxt.setdefault(job.stack_id.id, job)
        res = {}
        for stack in stacks:
            seen = bool(stack.ws_seen)
            product = stack.ws_product_id or stack.odoo_product_id if seen else stack.odoo_product_id
            node = {
                "qty": int(stack.ws_qty) if seen else int(round(stack.odoo_qty)),
                "upd": portal_tools.to_sec(min(stack.ws_updated, now), d0) if seen and stack.ws_updated else None,
                "src": "portal" if seen else "odoo",
                "capacity": int(stack.capacity or 0),
                "thickness": int(product.td_thickness_mm or 0),
                "product": product.default_code or (stack.ws_product if seen else "") or "",
                "name": product.name or "",
                "lot": (stack.ws_lot if seen else "") or stack.odoo_lot_id.name or "",
            }
            job = nxt.get(stack.id)
            if job:
                node["next"] = {
                    "job": job.name,
                    "state": job.state,
                    "target": job.target_code or "",
                    "sheets": job.sheets,
                    "done": job.done,
                    "ref": job.external_ref or job.production_id.name or "",
                }
            res[stack.code] = node
        return res

    # --- плитка «Огляд верстатів» ---------------------------------------------------------------------
    @api.model
    def td_tile(self):
        """Плитка «Портал: N завдань сьогодні, відходи розкрою X %» — `{jobs, sheets, waste_pct}` або `False`.

        `False` — немає прав (`group_td_user`) або портал не підключено (немає стосів і завдань).
        """
        if not self._td_can_see():
            return False
        has_stacks = self.env["td.gantry.stack"].sudo().search_count([], limit=1)
        has_jobs = self.env["td.gantry.job"].sudo().search_count([], limit=1)
        if not (has_stacks or has_jobs):
            return False
        now = self._td_now()
        jobs = self._td_day_jobs(now)
        return self._td_today(jobs, self._td_cut_maps(jobs))
