"""W4-C: `TestWHCommon` — фікстури мобільного модуля (W4_SPEC H.13): шаблон макета, сигнали, мок `get_pult`,
обхід у заданому стані, користувачі груп, «зараз» через контекст `f3d_now` (як у W1).

Збережено імена `TAGS` і `TestWHCommon` (їх імпортує контрактний тест менеджера).
"""

from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from odoo.addons.td_energy.tests.common import TestW1Common
from odoo.addons.td_energy.tools import dates

from ..tools import schedule

TAGS = ("post_install", "-at_install", "td", "td_wh")
SLOT_NOW = datetime(2026, 10, 20, 11, 20)  # вівторок 14:20 Київ (UTC+3 до 25.10): слот «Зміна 1»
T1, T2 = "energy/transformers/T1/temp_c", "energy/transformers/T2/temp_c"


def utc(*local):
    """Місцевий (Київ) час → UTC naive."""
    return dates.to_utc(datetime(*local))


class TestWHCommon(TestW1Common):
    now = SLOT_NOW
    real_pult = False  # True — тест викликає справжній `get_pult` (за замовчуванням — мок без даних ДГУ)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Round = cls.env["td.energy.round"]
        cls.Item = cls.env["td.energy.round.item"]
        cls.Template = cls.env["td.energy.round.template"]
        cls.Slot = cls.env["td.energy.round.slot"]
        cls.tpl = cls._template()
        cls.slot1, cls.slot2 = cls.tpl.slot_ids
        icp = cls.env["ir.config_parameter"].sudo()
        for key, val in (("keep_days", "730"), ("value_fresh_s", "120"), ("missed_event", "1"), ("history_limit", "3")):
            icp.set_param("td.energy_mobile." + key, val)
        cls._n_users = 0

    def setUp(self):
        super().setUp()
        if not self.real_pult:
            patcher = patch.object(
                self.env.registry["td.energy.dashboard"], "get_pult", return_value={"meta": {}, "kpis": {}}
            )
            patcher.start()
            self.addCleanup(patcher.stop)

    # --- фікстури ---------------------------------------------------------------------------------------
    @classmethod
    def _template(cls):
        """Шаблон макета `TP-GRSH` (2 слоти, 6 пунктів) з `data/round_template_data.xml`."""
        return cls.env.ref("td_energy_mobile.round_tpl_tp_grsh")

    def _user(self, groups):
        """Новий користувач із групами (xml-id); логін унікальний у тесті."""
        type(self)._n_users += 1
        return self._mk_user("wh_user_%d" % self._n_users, list(groups))

    def _signal(self, code, value, ts=None):
        """Сигнал зі значенням `value`: `last_ts = ts` (за замовчуванням `now`)."""
        self.env.cr.execute(
            "UPDATE td_signal SET last_value=%s, last_ts=%s, status='ok', last_quality='good' WHERE code=%s",
            (value, ts or self.now, code),
        )
        self.assertEqual(self.env.cr.rowcount, 1, code)
        self.env["td.signal"].invalidate_model()

    @contextmanager
    def _pult_patch(self, fuel_pct=78):
        """Мок `td.energy.dashboard.get_pult`: частина `kpis` з `generation.genset.fuel_pct` (`None` — немає даних)."""
        genset = {"fuel_pct": fuel_pct} if fuel_pct is not None else None
        pult = {"meta": {}, "kpis": {"generation": {"genset": genset}}}
        with patch.object(self.env.registry["td.energy.dashboard"], "get_pult", return_value=pult) as mock:
            yield mock

    def R(self, local=None, user=None):
        """`td.energy.round` з «зараз» = `local` (кортеж `datetime(*local)`, Київ) і користувачем `user`."""
        rec = self.Round
        if local:
            rec = rec.with_context(f3d_now=utc(*local))
        return rec.with_user(user) if user else rec

    def _round(self, slot=None, state="open", now=None, template=None, done=0, performer=None):
        """Обхід шаблона за слотом (за замовчуванням «Зміна 1») на добу `now` (UTC; за замовчуванням `self.now`)."""
        now = now or self.now
        template = template or self.tpl
        slot = slot or template.slot_ids[:1]
        day = dates.local_day(now)
        starts_at, due_at = schedule.slot_bounds(day, slot.time_from, slot.time_to)
        rnd = self.Round._td_create_round(template, slot, day, starts_at, due_at)
        vals = {"state": state}
        if performer:
            vals.update(performer_id=performer.id)
        if state in ("done", "missed"):
            vals["finished_at"] = due_at if state == "missed" else now
        rnd.write(vals)
        for item in rnd.item_ids[:done]:
            item.write({"done": True, "done_at": now, "done_by": (performer or self.u_eng).id, "result": "ok"})
        return rnd

    def _event_count(self, code):
        return self.Event.sudo().search_count([("kind", "=", "round"), ("code", "=", code)])
