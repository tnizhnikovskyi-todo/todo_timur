"""W1-A: M-27 `td.energy.dashboard` — API Пульту, картки вузла, мобільного екрана й розділу генерації (AbstractModel).

Контроль доступу — у методах (ACL моделі немає): `group_td_energy_user`; ключі вартості без групи вартості
видаляються з відповіді (не ховаються). Хуки `_td_genset_summary`, `_td_generation_cards`, `_td_node_facts_extra`,
`_td_node_card_extra` перевизначає міст `td_genset_factory3d` (C-31).
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from ..tools import dashboard, dates, node_card, sld

MOBILE_TABS = ("state", "alarms", "scheme")


class TdEnergyDashboard(models.AbstractModel):
    _name = "td.energy.dashboard"
    _description = "Енергетика: дані Пульту"

    @api.model
    def _td_check_access(self):
        if not (self.env.is_superuser() or self.env.user.has_group("td_energy.group_td_energy_user")):
            raise AccessError(_("Немає доступу до Енергетики."))

    # --- API --------------------------------------------------------------------------------------------
    @api.model
    def get_pult(self, period="now", parts=None):
        """API-05: JSON «Пульт»; `period` ∈ now|shift|day|month, `parts` — підмножина частин (або `None`)."""
        self._td_check_access()
        return dashboard.Pult(self.env, period, hooks=self).build(parts)

    @api.model
    def get_alarms(self, limit=None, scope="all"):
        """API-06: `{"active_count", "items": [alarm…]}`; `scope` ∈ all|active|mine."""
        self._td_check_access()
        return dashboard.alarms(self.env, None, dates.now_utc(self.env), limit=limit, scope=scope)

    @api.model
    def get_node_card(self, code, period="day"):
        """API-07: картка вузла за R-30."""
        self._td_check_access()
        if period != "day":
            raise UserError(_("Невідомий період: %s.", period))
        snap = sld.Snap(self.env(su=True), dates.now_utc(self.env))
        cost = self.env.user.has_group("td_energy.group_td_energy_cost")
        return node_card.card(self.env, snap, code, self, cost)

    @api.model
    def get_mobile(self, tab="state"):
        """API-12: дані мобільного екрана (`tab` ∈ state|alarms|scheme; `None` — усі три)."""
        self._td_check_access()
        if tab is not None and tab not in MOBILE_TABS:
            raise UserError(_("Невідома вкладка: %s.", tab))
        return dashboard.mobile(dashboard.Pult(self.env, "now", hooks=self), tab)

    @api.model
    def get_generation(self):
        """API-13: `{"cards": [card…], "ts": iso}` (R-38)."""
        self._td_check_access()
        return {
            "cards": self._td_generation_cards(),
            "ts": fields.Datetime.to_string(dates.now_utc(self.env)),
        }

    # --- хуки розширення (C-31); у базі — лише СЕС, КГУ, BESS, АВР -----------------------------------------
    @api.model
    def _td_genset_summary(self):
        return None

    @api.model
    def _td_generation_cards(self):
        return dashboard.generation_cards(dashboard.Pult(self.env, "now", hooks=self))

    @api.model
    def _td_node_facts_extra(self, node):
        return []

    @api.model
    def _td_node_card_extra(self, node):
        return {}
