import copy
import logging

from odoo import api, models
from odoo.exceptions import AccessError

from ..tools import chains as chains_tools
from ..tools import docs as docs_tools
from ..tools import payload as payload_tools

_logger = logging.getLogger(__name__)

# розділи, без яких обчислення chains неможливе (R-10…R-13)
NEEDED = ("productions", "workorders", "locations", "pickings")
UPSTREAM = ("stock", "production", "logistics", "quality")


class F3dViewerProviderChains(models.AbstractModel):
    """M-01g: ланцюжки, шляхи матеріалів, живі поля зон (R-10…R-13)."""

    _name = "td.viewer.provider.chains"
    _inherit = "td.viewer.provider"
    _description = "3D: постачальник — ланцюжки й зони"

    _td_sequence = 70
    _td_sections = ("sheet_chain", "ship_chain", "material_paths", "full_cycle_mo", "zones")
    _td_group = "mrp.group_mrp_user"

    @api.model
    def _td_viewer_collect(self, payload, ctx):
        env = self.env
        sections = ctx.get("sections")
        status = sections if isinstance(sections, dict) else {}
        partial = not env.user.has_group("stock.group_stock_user") or any(
            k not in payload or status.get(k) in ("denied", "error", "missing") for k in NEEDED
        )
        if partial:
            productions = payload.get("productions") or []
            payload["sheet_chain"] = {"steps": [], "path": []}
            payload["ship_chain"] = {"steps": []}
            payload["material_paths"] = []
            payload["full_cycle_mo"] = productions[0]["name"] if productions else None
        else:
            payload.update(chains_tools.compute(payload))
            self._td_doc_states(payload)
        if isinstance(sections, dict):
            sections["chains"] = "partial" if partial else "live"
        self._td_chains_zones(payload, ctx)

    @api.model
    def _td_doc_states(self, payload):
        """R-23: стани документів, названих у кроках `productions[].supply|delivery` (`doc`, `note`), яких немає в
        `pickings` / `quality_checks` / `productions` payload (напр. внутрішнє переміщення `WH/INT/00061` з нотатки
        контролю): `supply.docs` / `delivery.docs` = {назва: {kind, state}}. Один пакетний запит на модель."""
        known = {x["name"] for key in ("pickings", "quality_checks", "productions") for x in payload.get(key) or []}
        blocks = []
        for mo in payload.get("productions") or []:
            for key in ("supply", "delivery"):
                blk = mo.get(key)
                if blk:
                    steps = blk.get("steps") or []
                    texts = [blk.get("note")] + [t for st in steps for t in (st.get("doc"), st.get("note"))]
                    blocks.append((blk, docs_tools.names_in(*texts) - known))
        wanted = set().union(*(n for _blk, n in blocks)) if blocks else set()
        found = docs_tools.lookup_states(self.env, wanted) if wanted else {}
        for blk, names in blocks:
            if names & found.keys():
                blk["docs"] = {n: found[n] for n in sorted(names) if n in found}

    @api.model
    def _td_chains_zones(self, payload, ctx):
        """R-13 (X-29): живі поля всіх активних `td.zone`, злиті глибоко зі статичним записом."""
        env = self.env
        if not payload_tools.access_ok(env, "td.zone"):
            return
        static = (ctx.get("static") or {}).get("zones") or {}
        known = set(payload["locations"]) if isinstance(payload.get("locations"), dict) else None
        by_dock = {}
        for p in payload.get("pickings") or []:
            if p.get("dock"):
                by_dock.setdefault(p["dock"], []).append(p["name"])
        zones = payload.setdefault("zones", {})
        for zone in env["td.zone"].search_fetch([("active", "=", True)], order="sequence, td_code"):
            code = zone.td_code
            st = static.get(code)
            rec = {"name": zone.name, "zone_type": zone.zone_type}
            if zone.polygon:
                rec["polygon"] = zone.polygon
            if zone.is_roof:
                rec["is_roof"] = True
            try:
                odoo_loc = zone.root_location_id.complete_name or None
            except AccessError:
                odoo_loc = None
            rec["odoo_location"] = odoo_loc or (st or {}).get("odoo_location")
            if st is not None:
                locs, wcs = list(st.get("locations") or []), list(st.get("workcenters") or [])
            else:
                locs = [c for c in zone.location_ids.mapped("td_code") if c]
                wcs = [c for c in zone.workcenter_ids.mapped("td_code") if c]
            if known is not None:
                locs = [c for c in locs if c in known]
            rec["locations"], rec["workcenters"] = locs, wcs
            if code.startswith(("Z-RCV-", "Z-OUT-")):
                side = "W" if code.startswith("Z-RCV-") else "E"
                rec["pickings"] = by_dock.get(f"DOCK-{side}{code[-1]}", [])
            if isinstance(zones.get(code), dict):
                payload_tools.deep_merge(zones[code], rec)
            else:
                zones[code] = rec

    @api.model
    def _td_viewer_delta(self, patch, ctx):
        """R-14 п. 5: зміна МО/переміщення — chains-ключі цілком і supply/delivery/components змінених МО."""
        env = self.env
        changes = ctx.get("changes") or {}
        if not any(m in changes for m in ("mrp.production", "stock.picking", "mrp.workorder")):
            return
        full_ctx = dict(ctx, codes=None, changes={})
        tmp = {}
        for key in UPSTREAM:
            name = payload_tools.PROVIDER_PREFIX + key
            if name not in env:
                continue
            prov = env[name]
            grp = getattr(prov, "_td_group", None)
            if grp and not payload_tools.group_ok(env, grp):
                continue
            prov._td_viewer_collect(tmp, full_ctx)
        if any(k not in tmp for k in NEEDED) or not env.user.has_group("stock.group_stock_user"):
            return
        patch.update(copy.deepcopy(chains_tools.compute(tmp)))
        self._td_doc_states(tmp)
        fresh = {m["name"]: m for m in tmp["productions"]}
        for rec in patch.get("productions") or []:
            src = fresh.get(rec.get("name"))
            if src:
                for k in ("supply", "delivery", "components"):
                    if k in src:
                        rec[k] = copy.deepcopy(src[k])
