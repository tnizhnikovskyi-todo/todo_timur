"""W1-A: AC-93…AC-100, AC-118, AC-119 — життєвий цикл подій (R-24, R-25), діагностика лічильника."""

import importlib.util
import os
from datetime import datetime, timedelta

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from ..tools import dates
from .common import TAGS, TestW1Common

MIGRATION = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "migrations", "19.0.1.1.0", "post-migration.py"
)


@tagged(*TAGS)
class TestW1Event(TestW1Common):
    def log(self, level="warn", kind="meter", code="PM-QF-C2", text="Лічильник PM-QF-C2 не на зв'язку. 33 хв.", **kw):
        return self.Event._td_log(level, kind, code, text, ts=kw.pop("ts", self.now), **kw)

    def as_user(self, rec, user):
        return rec.with_user(user)

    def test_title_split(self):  # AC-93
        ev = self.log(text="Лічильник PM-QF-C2 не на зв'язку. 33 хв без даних.")
        self.assertEqual(
            (ev.title, ev.detail, ev.state), ("Лічильник PM-QF-C2 не на зв'язку", "33 хв без даних.", "active")
        )
        short = self.log(text="Короткий текст без роздільників")
        self.assertEqual((short.title, short.detail), ("Короткий текст без роздільників", ""))
        colon = self.log(text="PFC-2: ступінь 3 не вмикається")
        self.assertEqual((colon.title, colon.detail), ("PFC-2", "ступінь 3 не вмикається"))
        long = self.log(text="x" * 140)
        self.assertEqual(long.title, "x" * 125 + "…")
        self.assertEqual(long.detail, "")

    def test_state_initial(self):  # AC-94
        info = self.log(level="info", kind="peak", code="SWB-1", text="Пік доби 631 кВт. 79 % договірної.")
        self.assertEqual((info.state, info.title), ("na", "Пік доби 631 кВт"))
        explicit = self.log(text="Довгий текст. Деталі.", title="Мій заголовок", detail="Мої деталі")
        self.assertEqual((explicit.title, explicit.detail), ("Мій заголовок", "Мої деталі"))
        with self.assertRaises(ValidationError):
            self.Event.create({"level": "info", "kind": "peak", "text": "x", "state": "active"})
        with self.assertRaises(ValidationError):
            self.Event.create({"level": "warn", "kind": "peak", "text": "x", "state": "na"})

    def test_ack(self):  # AC-95
        ev = self.log()
        self.as_user(ev, self.u_eng).action_ack()
        self.assertEqual((ev.state, ev.acked_by, ev.acked_at), ("acked", self.u_eng, self.now))
        self.assertTrue(self.as_user(ev, self.u_eng2).action_ack())  # повторно: без змін
        self.assertEqual(ev.acked_by, self.u_eng)
        other = self.log(text="Інша. Подія.")
        with self.assertRaisesRegex(AccessError, "Підтверджувати тривоги може лише енергетик."):
            self.as_user(other, self.u_view).action_ack()

    def test_take_race(self):  # AC-96
        ev = self.log()
        self.as_user(ev, self.u_eng).action_take()
        self.assertEqual((ev.assigned_user_id, ev.state, ev.taken_at), (self.u_eng, "acked", self.now))
        with self.assertRaises(UserError) as caught:
            self.as_user(ev, self.u_eng2).action_take()
        self.assertEqual(str(caught.exception), "Уже в роботі: %s." % self.u_eng.name)
        done = self.log(text="Закрита. Подія.")
        done.write({"state": "resolved"})
        with self.assertRaisesRegex(UserError, "Подію вже закрито."):
            self.as_user(done, self.u_eng).action_take()

    def test_resolve_release(self):  # AC-97
        ev = self.log()
        self.as_user(ev, self.u_eng).action_take()
        self.as_user(ev, self.u_eng).action_release()
        self.assertEqual((ev.assigned_user_id.id, ev.state), (False, "acked"))
        self.as_user(ev, self.u_eng).action_take()
        with self.assertRaises(AccessError):
            self.as_user(ev, self.u_eng2).action_resolve()
        self.as_user(ev, self.u_eng).action_resolve()
        self.assertEqual((ev.state, ev.resolved_at), ("resolved", self.now))
        other = self.log(text="Чужа. Подія.")
        self.as_user(other, self.u_eng).action_take()
        self.as_user(other, self.u_chief).action_resolve()
        self.assertEqual(other.state, "resolved")
        info = self.log(level="info", kind="peak", code="SWB-1", text="Інфо. Подія.")
        with self.assertRaisesRegex(UserError, "Інформаційну подію закривати не потрібно."):
            self.as_user(info, self.u_chief).action_resolve()

    def test_auto_resolve_meter(self):  # AC-98
        node = self.Node.search([("code", "=", "C2")])
        meter = self.Meter.search([("code", "=", "PM-QF-C2")])
        ev = self.log(node=node)
        other = self.log(text="Інший. Лічильник.", code="PM-QF-1", node=self.Node.search([("code", "=", "BW-1")]))
        keep = self.log(level="warn", kind="peak", code="SWB-1", text="Пік. Високий.")
        meter.write({"data_state": "stale"})
        self.fresh("energy/lines/C2/kwh_total", 1000.0)
        meter._td_update_state()
        self.assertEqual(meter.data_state, "ok")
        self.assertEqual((ev.state, ev.resolved_at), ("resolved", self.now))
        self.assertEqual((other.state, keep.state), ("active", "active"))

    def test_auto_resolve_threshold(self):  # AC-99
        sig = self.env["td.signal"].search([("code", "=", "energy/lines/BW-2/i_now")])
        ev = self.log(kind="threshold", code="QF-2", text="Струм. Високий.", signal=sig)
        ats = self.log(kind="ats", code="ATS-1", text="АВР. Невдалий пуск.", signal=sig)
        self.fresh(sig.code, 100.0)
        self.Event._td_status_event(sig, "warn")
        self.assertEqual((ev.state, ats.state), ("resolved", "active"))

    def test_migration_events(self):  # AC-100
        warn = self.log(text="Лічильник X. 33 хв без даних.")
        info = self.log(level="info", kind="peak", code="SWB-1", text="Пік доби. 5 кВт.")
        bad = self.log(level="bad", kind="threshold", code="T1", text="Перевантаження T1: 950 кВА")
        self.env.cr.execute(
            "UPDATE td_energy_event SET title = NULL, detail = NULL, state = 'na', resolved_at = NULL WHERE id IN %s",
            (tuple((warn | info | bad).ids),),
        )
        self.env.invalidate_all()
        spec = importlib.util.spec_from_file_location("w1_migration", MIGRATION)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.migrate(self.env.cr, "19.0.1.0.0")
        self.env.invalidate_all()
        self.assertEqual(
            (warn.title, warn.detail, warn.state, warn.resolved_at),
            ("Лічильник X", "33 хв без даних.", "resolved", warn.ts),
        )
        self.assertEqual((info.state, info.title), ("na", "Пік доби"))
        self.assertEqual((bad.state, bad.title), ("resolved", "Перевантаження T1"))
        snapshot = [(e.id, e.title, e.detail, e.state, e.resolved_at) for e in (warn | info | bad)]
        module.migrate(self.env.cr, "19.0.1.0.0")
        self.env.invalidate_all()
        self.assertEqual(snapshot, [(e.id, e.title, e.detail, e.state, e.resolved_at) for e in (warn | info | bad)])

    def test_alarm_order(self):  # AC-118
        self.Event.search([]).unlink()
        mins = lambda n: self.now - timedelta(minutes=n)  # noqa: E731
        acked = self.log(text="Підтверджена. Подія.", ts=mins(5))
        self.as_user(acked, self.u_eng).action_ack()
        warn = self.log(text="Увага. Подія.", ts=mins(30))
        bad = self.log(level="bad", kind="threshold", code="T1", text="Аварія. Подія.", ts=mins(60))
        infos = [
            self.log(level="info", kind="peak", code="SWB-1", text="Інфо %d. x." % k, ts=mins(100 + k))
            for k in range(4)
        ]
        dash = self.env["td.energy.dashboard"].with_user(self.u_view)
        items = dash.get_alarms()["items"]
        self.assertEqual([i["id"] for i in items][:3], [bad.id, warn.id, acked.id])
        self.assertEqual([i["id"] for i in items][3:], [e.id for e in infos])
        self.assertEqual(dash.get_alarms()["active_count"], 2)
        self.assertEqual(len(dash.get_alarms(limit=2)["items"]), 2)
        self.as_user(warn, self.u_eng).action_take()
        mine = self.env["td.energy.dashboard"].with_user(self.u_eng).get_alarms(scope="mine")["items"]
        self.assertEqual([i["id"] for i in mine], [warn.id])
        self.assertTrue(mine[0]["taken_by_me"])
        active = dash.get_alarms(scope="active")["items"]
        self.assertEqual({i["state"] for i in active}, {"active", "acked"})

    def test_diag_text(self):  # AC-119
        meter = self.Meter.search([("code", "=", "PM-QF-C2")])
        source = meter.source_id
        source.write({"last_ok": dates.to_utc(datetime(2026, 10, 17, 13, 47, 12))})
        self.log(node=self.Node.search([("code", "=", "C2")]))
        item = self.env["td.energy.dashboard"].with_user(self.u_view).get_alarms()["items"][0]
        diag = item["diag"]
        self.assertIn(source.code, diag)
        self.assertIn("%s:%s" % (source.params["host"], source.params["port"]), diag)
        self.assertIn("unit %s" % source.params["unit"], diag)
        self.assertIn("13:47:12", diag)
        self.assertIn("колектор %s" % source.collector_id.code, diag)
        self.assertIn("комірку QF-C2", diag)
        self.assertEqual([a["code"] for a in item["actions"]], ["diag", "ticket"])
