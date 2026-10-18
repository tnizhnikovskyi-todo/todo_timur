"""W4-C: права, record rules, нейтралізація, деінсталяція: AC-H17, AC-H21, ТБ-H1, ТБ-H2."""

from pathlib import Path

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .. import hooks
from .common import TAGS, TestWHCommon

NEUTRALIZE = Path(__file__).resolve().parent.parent / "data" / "neutralize.sql"
CRONS = ("cron_td_energy_round_open", "cron_td_energy_round_close", "cron_td_energy_round_rotate")


@tagged(*TAGS)
class TestWHSecurity(TestWHCommon):
    def test_ac_h17_acl(self):
        rnd = self._round(self.slot1)
        item = rnd.item_ids[0]
        view, eng, chief, admin = self.u_view, self.u_eng, self.u_chief, self.u_admin
        # …_user читає, не пише
        self.assertEqual(rnd.with_user(view).name, rnd.name)
        self.assertEqual(item.with_user(view).title, item.title)
        with self.assertRaises(AccessError):
            rnd.with_user(view).write({"note": "x"})
        with self.assertRaises(AccessError):
            self.Round.with_user(view).create(
                {"template_id": self.tpl.id, "date": "2026-10-21", "starts_at": self.now, "due_at": self.now}
            )
        # …_manager створює/пише обходи; пункти — лише методами; не видаляє
        rnd.with_user(eng).write({"note": "нотатка"})
        self.assertEqual(rnd.note, "нотатка")
        with self.assertRaises(AccessError):
            item.with_user(eng).write({"done": True})
        with self.assertRaises(AccessError):
            rnd.with_user(eng).unlink()
        with self.assertRaises(AccessError):
            self.Template.with_user(eng).create({"name": "Х", "code": "T-X"})
        with self.assertRaises(AccessError):
            self.tpl.with_user(eng).write({"name": "Інша"})
        # …_chief править шаблони; скасовує/завершує чужі
        self.tpl.with_user(chief).write({"note": "правка chief"})
        new_tpl = self.Template.with_user(chief).create({"name": "Новий", "code": "T-NEW"})
        new_tpl.with_user(chief).unlink()
        self.R(user=eng).action_toggle_item(item.id, True)
        self.assertTrue(rnd.with_user(chief).action_cancel())
        self.assertEqual(rnd.state, "cancelled")
        with self.assertRaises(UserError):
            rnd.with_user(chief).action_cancel()  # уже закрито
        with self.assertRaises(AccessError):
            rnd.with_user(eng).action_cancel()
        # admin — усе, зокрема прямий запис пункту й видалення
        item.with_user(admin).write({"comment": "admin"})
        self.assertEqual(item.comment, "admin")
        rnd.with_user(admin).unlink()
        self.assertFalse(rnd.exists())

    def test_ac_h17_company_rule(self):
        company2 = self.env["res.company"].create({"name": "Інша компанія"})
        tpl2 = self.Template.create({"name": "Чужий", "code": "T-C2", "company_id": company2.id})
        rnd2 = self.Round.create(
            {
                "template_id": tpl2.id, "date": "2026-10-20", "starts_at": self.now, "due_at": self.now,
                "company_id": company2.id,
            }
        )  # fmt: skip
        own = self._round(self.slot1)
        eng = self.u_eng
        self.assertEqual(self.Round.with_user(eng).search([("id", "in", (own | rnd2).ids)]), own)
        self.assertEqual(self.Template.with_user(eng).search([("id", "=", tpl2.id)]).ids, [])
        with self.assertRaises(AccessError):
            rnd2.with_user(eng).read(["name"])
        with self.assertRaises(AccessError):
            self.R(user=eng).get_mobile(round_id=rnd2.id)
        item = rnd2.item_ids[:1] or self.Item.create({"round_id": rnd2.id, "code": "x", "title": "X"})
        with self.assertRaises(AccessError):
            self.R(user=eng).action_toggle_item(item.id, True)

    def test_ac_h21_neutralize_and_uninstall(self):
        for name in CRONS:
            cron = self.env.ref("td_energy_mobile." + name)
            self.assertTrue(cron.active, name)
        nodes = self.env["td.energy.node"].search_count([])
        self.env.cr.execute(NEUTRALIZE.read_text(encoding="utf-8"))
        self.env.invalidate_all()
        for name in CRONS:
            self.assertFalse(self.env.ref("td_energy_mobile." + name).active, name)
        # деінсталяція: події `round` → `manual`; крони й параметри модуля знято; дані td_energy цілі
        event = self.Event._td_log("warn", "round", "ROUND-9-t1", "Обхід: тест")
        self.assertEqual(event.kind, "round")
        hooks.uninstall_hook(self.env)
        event.invalidate_recordset(["kind"])
        self.assertEqual(event.kind, "manual")
        self.assertFalse(self.env.ref("td_energy_mobile.cron_td_energy_round_open", raise_if_not_found=False))
        self.assertFalse(self.env["ir.config_parameter"].sudo().search_count([("key", "like", "td.energy_mobile.%")]))
        self.assertEqual(self.env["td.energy.node"].search_count([]), nodes)
        self.assertTrue(self.env["ir.config_parameter"].sudo().get_param("td.energy.read_enabled"))

    # --- ТБ-H1, ТБ-H2 ---------------------------------------------------------------------------------
    def test_tb_h1_no_group(self):
        rnd = self._round(self.slot1)
        item = rnd.item_ids[0]
        for user in (self.u_plain, self.u_view):
            R = self.R(user=user)
            for call in (
                lambda: R.action_toggle_item(item.id, True),
                lambda: R.action_finish(rnd.id),
                lambda: R.action_start(self.tpl.id),
            ):
                with self.assertRaises(AccessError):
                    call()
        self.assertFalse(item.done)
        self.assertEqual(rnd.state, "open")

    def test_tb_h2_foreign_round(self):
        rnd = self._round(self.slot1)
        a, b, chief = self.u_eng, self.u_eng2, self.u_chief
        self.R(user=a).action_toggle_item(rnd.item_ids[0].id, True)
        with self.assertRaisesRegex(UserError, "Обхід виконує"):
            self.R(user=b).action_toggle_item(rnd.item_ids[1].id, True)
        for item in rnd.item_ids[1:]:
            self.R(user=a).action_toggle_item(item.id, True)
        with self.assertRaisesRegex(UserError, "Обхід виконує"):
            self.R(user=b).action_finish(rnd.id)
        self.assertEqual(rnd.state, "in_progress")
        self.assertEqual(self.R(user=chief).action_finish(rnd.id)["deviation_count"], 0)
        self.assertEqual(rnd.state, "done")
