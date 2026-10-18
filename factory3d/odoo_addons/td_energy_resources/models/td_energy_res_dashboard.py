"""M-08 `td.energy.res.dashboard` — API екрана «Енергоресурси» (FR-08…FR-12; W3-E).

Доступ — у методах (ACL моделі немає): `group_td_energy_user` або суперкористувач; сигнали, показання й інтервали
читаються через `sudo()`; ключі вартості без `group_td_energy_cost` видаляються з відповіді (як W1 M-27).
Хуки ядра (порожні; перекриває міст `td_energy_resources_bms`, C-04): `_td_heat_kpis(ctx)`, `_td_heat_list(ctx)`,
`_td_heat_chart_note(ctx)`, `_td_resource_extra(code, ctx)`. `ctx` — словник `Screen.make_ctx`
(`tools/resource_data.py`).
"""

import logging
import re
from datetime import date, datetime

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from ..tools import resource_data

_logger = logging.getLogger(__name__)

COST_GROUP = "td_energy.group_td_energy_cost"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class TdEnergyResDashboard(models.AbstractModel):
    _name = "td.energy.res.dashboard"
    _description = "Енергетика: дані екрана ресурсів"

    @api.model
    def _td_check_access(self):
        if not (self.env.is_superuser() or self.env.user.has_group("td_energy.group_td_energy_user")):
            raise AccessError(_("Немає доступу до Енергетики."))

    # --- API-01 ---------------------------------------------------------------------------------------------
    @api.model
    def get_resources(self, code=None):
        """API-01: JSON «Енергоресурси» (вкладки, підсумок, KPI, графік доби, список, нотатки) для ресурсу `code`
        (за умовчанням — перша вкладка). Збій частини не ламає решту: повтор по частинах із `{"error": …}`."""
        self._td_check_access()
        try:
            with self.env.cr.savepoint():
                return resource_data.Screen(self.env, self, code).build()
        except UserError:
            raise
        except Exception:
            _logger.exception("td_energy_resources: екран ресурсів — повтор по частинах")
        return resource_data.Screen(self.env, self, code, isolate=True).build()

    # --- API-10 ---------------------------------------------------------------------------------------------
    @api.model
    def _td_totals(self, day_from, day_to, resource_codes=None):
        """API-10 (для W4/звітів): `[{"resource", "qty", "kwh_eq", "cost", "co2_kg"}…]` за місцеві доби
        `[day_from, day_to]` з `td.energy.usage`: електрика — потік `import`, решта ресурсів — `supply` (R-07).
        Читання через `sudo`; без групи вартості ключ `cost` відсутній."""
        self._td_check_access()
        first, last = self._td_to_date(day_from), self._td_to_date(day_to)
        self.env.flush_all()  # view читає таблиці напряму
        domain = [("active", "=", True)]
        if resource_codes:
            domain.append(("code", "in", list(resource_codes)))
        resources = self.env["td.energy.resource"].sudo().search(domain)
        groups = (
            self.env["td.energy.usage"]
            .sudo()
            ._read_group(
                [("resource_id", "in", resources.ids), ("day", ">=", first), ("day", "<=", last)],
                ["resource_id", "flow"],
                ["qty:sum", "kwh_eq:sum", "cost:sum", "co2_kg:sum"],
            )
        )
        sums = {(res.id, flow): (qty, kwh, cost, co2) for res, flow, qty, kwh, cost, co2 in groups}
        with_cost = self.env.user.has_group(COST_GROUP)
        out = []
        for res in resources:
            qty, kwh, cost, co2 = sums.get((res.id, "import" if res.code == "el" else "supply"), (0.0,) * 4)
            row = {
                "resource": res.code, "qty": round(qty or 0.0, 3), "kwh_eq": round(kwh or 0.0, 3),
                "cost": round(cost or 0.0, 2), "co2_kg": round(co2 or 0.0, 3),
            }  # fmt: skip
            if not with_cost:
                row.pop("cost")
            out.append(row)
        return out

    @api.model
    def _td_to_date(self, value):
        """`date`, `datetime` або рядок `YYYY-MM-DD` (суворо: без хвоста); інакше `UserError`."""
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        if isinstance(value, str) and DATE_RE.match(value):
            try:
                return date.fromisoformat(value)
            except ValueError:
                pass
        raise UserError(_("Невірна дата."))

    # --- хуки ядра (R-B2, C-04; перекриває міст) ----------------------------------------------------------------
    @api.model
    def _td_heat_kpis(self, ctx):
        """KPI «Температура в цеху», «Рекуперація AHU-1» (і підпис `power`): у ядрі порожньо."""
        return []

    @api.model
    def _td_heat_list(self, ctx):
        """Список «Куди йде тепло» з BMS (`[{"code", "name", "value", "quality"}]`): у ядрі `None` — з точок."""
        return None

    @api.model
    def _td_heat_chart_note(self, ctx):
        """Підстановка `{capacity}` у примітці графіка тепла (потужність котлів): у ядрі `None`."""
        return None

    @api.model
    def _td_resource_extra(self, code, ctx):
        """Додаткові блоки відповіді ресурсу `code`: у ядрі порожньо."""
        return {}
