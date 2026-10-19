"""TestWbBridge: AC-B01…AC-B09 — міст td_energy_resources_bms: привʼязка BMS, KPI й список «Тепло», рекуперація AHU-1,
детектори `preheat_early`, `ahu_recuperation`, `dock_gates`, backfill тепла, шаблон UI-B1."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from lxml import etree

from odoo.tests import tagged
from odoo.tools import file_open

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.dates import to_local
from odoo.addons.td_energy_resources.tests.common import NOW, SLOT, TAGS, TestW3Common
from odoo.addons.td_energy_resources.tools import shifts

from ..models.td_energy_point import find_dock, find_dock_signal
from ..tools import heat

POINT_MODULE = "odoo.addons.td_energy_resources_bms.models.td_energy_point"
LO = datetime(2026, 10, 9, 21, 0)  # 00:00 Київ 10.10: початок вікна L = 7 для NOW
OUTDOOR = "ventilation/totals/outdoor_c"
HEAT_CODES = {"HM-BOILER", "HM-CHP", "HM-RV", "HM-AHU1", "HM-DOCK", "HM-OFFICE"}
BASE_POINTS = {"HEAT-BOILER", "HEAT-CHP", "RV-ALL", "AHU-1", "OFFICE"}  # без DOCK: він — лише з сигналом воріт


@tagged(*TAGS)
class TestWbBridge(TestW3Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("td.energy.shift_calendar_id", False)  # умовчання макета
        cls.Dash = cls.env["td.energy.res.dashboard"]
        cls.Meter = cls.env["td.energy.meter"]
        cls.balance = cls.env["td.bms.heat.balance"].search([], limit=1)
        cls.units = cls.env["td.bms.hvac.unit"].search([])
        cls.ahu = cls.units.filtered(lambda u: u.code == "AHU-1")
        cls.rv = cls.units.filtered(lambda u: u.code.startswith("RV-"))
        cls.heat_after_install = set(cls.Point.search([("resource_id.code", "=", "heat")]).mapped("code"))
        cls.drop_installed_dock()

    @classmethod
    def drop_installed_dock(cls):
        """Відтворюваний початковий стан для будь-якої конфігурації: з td_yard міст уже створив DOCK і HM-DOCK із
        сигналу реальних воріт (GATE-E), а фікстури тестів створюють той самий код. Прибираємо їх у транзакції класу;
        `bind()` підставляє `find_dock_signal` патчем, тож реальні ворота не втручаються (повна конфігурація —
        `test_yard_*`)."""
        cls.env["td.energy.meter"].with_context(active_test=False).search([("code", "=", "HM-DOCK")]).unlink()
        cls.env["td.energy.point"].with_context(active_test=False).search(
            [("resource_id.code", "=", "heat"), ("code", "=", "DOCK")]
        ).unlink()

    # --- допоміжне
    def heat_points(self):
        return self.Point.search([("resource_id.code", "=", "heat")])

    def heat_meters(self):
        return self.Meter.search([("resource_id.code", "=", "heat")])

    def chp_signal(self):
        return self.ensure(self.balance, "chp_heat_signal_id", "infra/chp/heat_kw", "кВт")

    def dock_signal(self):
        return self.Signal.search([("code", "=", "test/yard/gate_open")], limit=1) or self.signal(
            "test/yard/gate_open", unit=""
        )

    def ensure(self, record, field, code, unit=""):
        """Сигнал поля `field` запису BMS: наявний, інакше створюється й привʼязується (в шаблонній БД є не всі)."""
        if not record[field]:
            record[field] = self.Signal.search([("code", "=", code)], limit=1) or self.signal(code, unit=unit)
        return record[field]

    def bind(self, with_dock=False, invert=False):
        """`_td_bind_extra` з підміною пошуку воріт: фікстура `test/yard/gate_open` (`invert` — NC-контакт, `invert_di`)
        або порожній набір (воріт немає)."""
        self.env.flush_all()
        gate_signal = self.dock_signal() if with_dock else self.Signal
        with patch(POINT_MODULE + ".find_dock", return_value=(gate_signal, invert)):
            return self.Point._td_bind_extra()

    def feed_signal(self, signal, value):
        self.fresh(signal.code, value)

    def rule(self, code):
        return self.env.ref("td_energy_resources_bms.rule_" + code)

    def slots(self):
        return [LO + SLOT * i for i in range(96 * 7)]

    def work_days(self):
        win = shifts.load_windows(self.env)
        return [
            date(2026, 10, 10) + timedelta(days=n)
            for n in range(7)
            if win.windows_for(date(2026, 10, 10) + timedelta(days=n))
        ], win

    # --- AC-B01, AC-B02: привʼязка
    def test_bind_points_and_meters(self):  # AC-B01
        codes = set(self.heat_points().mapped("code"))
        self.assertEqual(codes, BASE_POINTS)  # DOCK — лише з сигналом воріт (setUpClass прибрав той, що з td_yard)
        # HM-CHP: баланс BMS отримав сигнал тепла КГУ незалежно від порядку встановлення td_bms / td_energy
        self.assertEqual({m.code for m in self.heat_meters()}, {"HM-BOILER", "HM-CHP", "HM-RV", "HM-AHU1", "HM-OFFICE"})
        self.assertEqual(len(self.units), 29)
        points = {p.code: p for p in self.heat_points()}
        self.assertEqual((points["HEAT-BOILER"].kind, points["HEAT-CHP"].kind), ("source", "source"))
        self.assertEqual(points["RV-ALL"].hvac_ref, "RV-*")
        self.assertEqual(points["AHU-1"].hvac_unit_id, self.ahu)
        self.assertEqual(
            (points["OFFICE"].estimate_method, points["OFFICE"].estimate_params),
            ("residual", {"from": ["HEAT-BOILER", "HEAT-CHP"]}),
        )
        meters = {m.code: m for m in self.heat_meters()}
        rv_signals = self.rv.heat_signal_id
        self.assertEqual(len(meters["HM-RV"].flow_signal_ids), len(rv_signals))
        self.assertEqual(meters["HM-RV"].flow_signal_ids, rv_signals)
        self.assertEqual(len(rv_signals), 25)
        self.assertEqual(meters["HM-BOILER"].flow_signal_ids, self.balance.boiler_heat_signal_id)
        self.assertEqual(meters["HM-CHP"].flow_signal_ids.mapped("code"), ["infra/chp/heat_kw"])
        self.assertEqual(meters["HM-CHP"].flow_signal_ids, self.balance.chp_heat_signal_id)
        self.assertEqual((meters["HM-CHP"].point_id.code, meters["HM-CHP"].point_id.kind), ("HEAT-CHP", "source"))
        self.assertEqual(meters["HM-AHU1"].flow_signal_ids, self.ahu.heat_signal_id)
        self.assertEqual((meters["HM-OFFICE"].mode, meters["HM-RV"].mode), ("estimate", "flow_integrate"))
        self.assertTrue(all(m.role == "resource" and m.resource_id.code == "heat" for m in meters.values()))

    def test_chp_heat_source_migration(self):  # міграція 19.0.1.0.2: стара база без сигналу КГУ у балансі → HM-CHP
        meter = self.Meter.search([("code", "=", "HM-CHP")])
        self.assertTrue(meter)
        meter.unlink()  # стан бази до міграції: баланс без сигналу тепла КГУ, лічильника немає
        self.balance.chp_heat_signal_id = False
        self.assertEqual(self.bind(), {"points": 0, "meters": 0})  # немає сигналу — лічильник пропущено
        self.assertFalse(self.Meter.search([("code", "=", "HM-CHP")]))
        self.balance._td_bms_link_optional()  # те саме робить міграція td_bms / моста
        self.assertEqual(self.balance.chp_heat_signal_id.code, "infra/chp/heat_kw")
        self.assertEqual(self.bind(), {"points": 0, "meters": 1})
        meter = self.Meter.search([("code", "=", "HM-CHP")])
        self.assertEqual(
            (meter.point_id.code, meter.point_id.kind, meter.mode), ("HEAT-CHP", "source", "flow_integrate")
        )
        self.assertEqual(meter.flow_signal_ids, self.balance.chp_heat_signal_id)
        self.assertEqual(self.bind(), {"points": 0, "meters": 0})  # ідемпотентно

    def test_chp_heat_is_production_not_consumption(self):  # тепло КГУ — надходження (виробіток), не споживання
        self.bind(with_dock=True)
        sources = self.Point.search([("resource_id.code", "=", "heat"), ("kind", "=", "source")])
        self.assertEqual(set(sources.mapped("code")), {"HEAT-BOILER", "HEAT-CHP"})
        consumers = self.Point.search([("resource_id.code", "=", "heat"), ("kind", "=", "consumer")])
        self.assertNotIn("HEAT-CHP", consumers.mapped("code"))
        office = self.Point.search([("resource_id.code", "=", "heat"), ("code", "=", "OFFICE")])
        self.assertEqual(office.estimate_params, {"from": ["HEAT-BOILER", "HEAT-CHP"]})  # залишок = джерела − виміряні
        self.ResInterval._td_backfill(days=1, until=datetime(2026, 10, 17, 0, 0), seed=20261018)
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT u.flow, COUNT(*) FROM td_energy_usage u JOIN td_energy_meter m ON m.id = u.meter_id"
            " WHERE m.code = 'HM-CHP' GROUP BY u.flow"
        )
        flows = dict(self.env.cr.fetchall())
        self.assertEqual(set(flows), {"supply"})  # ніколи не `branch`: у гілках споживання тепла КГУ немає
        self.assertGreater(flows["supply"], 0)

    def test_bind_idempotent_keeps_manual_edits(self):  # AC-B01
        self.assertEqual(
            self.bind(), {"points": 0, "meters": 0}
        )  # HM-CHP уже є (сигнал КГУ привʼязано при встановленні)
        self.assertEqual(len(self.heat_meters()), 5)
        self.Point.search([("code", "=", "RV-ALL")]).name = "Мої RV"
        self.Meter.search([("code", "=", "HM-RV")]).write({"name": "Мій лічильник", "max_rate": 999.0})
        self.assertEqual(self.bind(), {"points": 0, "meters": 0})
        self.assertEqual((len(self.heat_points()), len(self.heat_meters())), (5, 5))
        self.assertEqual(self.Point.search([("code", "=", "RV-ALL")]).name, "Мої RV")
        meter = self.Meter.search([("code", "=", "HM-RV")])
        self.assertEqual((meter.name, meter.max_rate), ("Мій лічильник", 999.0))
        self.assertEqual(len(meter.flow_signal_ids), 25)

    def test_bind_dock_with_gate_signal(self):  # AC-B01: DOCK — лише за наявності сигналу воріт (Q-08)
        stats = self.bind(with_dock=True)
        self.assertEqual(stats["points"], 1)
        dock = self.Point.search([("code", "=", "DOCK"), ("resource_id.code", "=", "heat")])
        self.assertEqual((dock.estimate_method, dock.kind), ("gate_loss", "consumer"))
        self.assertEqual(dock.state_signal_id.code, "test/yard/gate_open")
        self.assertEqual(dock.estimate_params["loss_kw_per_k"], 3.5)
        self.assertEqual(dock.estimate_params["t_out_signal"], OUTDOOR)
        self.assertEqual(dock.estimate_params["t_in"], self.balance.t_in_set)
        meter = self.Meter.search([("code", "=", "HM-DOCK")])
        self.assertEqual((meter.mode, meter.point_id), ("estimate", dock))
        self.assertEqual(self.bind(with_dock=True), {"points": 0, "meters": 0})
        self.assertIs(dock.estimate_params["state_invert"], False)  # NO-контакт: інверсії немає

    def dock_point(self):
        return self.Point.search([("code", "=", "DOCK"), ("resource_id.code", "=", "heat")])

    def test_bind_dock_state_invert(self):  # AC-B01, Q-08: інверсія NC-воріт зберігається й слідує за invert_di
        self.assertEqual(self.bind(with_dock=True, invert=True)["points"], 1)
        dock = self.dock_point()
        self.assertIs(dock.estimate_params["state_invert"], True)
        self.assertEqual(dock.estimate_params["loss_kw_per_k"], 3.5)
        dock.estimate_params = dict(dock.estimate_params, loss_kw_per_k=4.2)  # ручна правка іншого параметра
        self.assertEqual(self.bind(with_dock=True, invert=True), {"points": 0, "meters": 0})  # без змін — ідемпотентно
        self.assertEqual((dock.estimate_params["state_invert"], dock.estimate_params["loss_kw_per_k"]), (True, 4.2))
        self.bind(with_dock=True, invert=False)  # `invert_di` воріт змінили → параметр оновлено
        self.assertEqual((dock.estimate_params["state_invert"], dock.estimate_params["loss_kw_per_k"]), (False, 4.2))
        self.bind(with_dock=True, invert=True)  # та сама точка, без дублів
        self.assertIs(dock.estimate_params["state_invert"], True)
        self.assertEqual(len(self.dock_point()), 1)
        other = self.signal("test/yard/gate_other", unit="")
        dock.state_signal_id = other  # точку вручну привʼязали до іншого сигналу — інверсію не чіпаємо
        self.bind(with_dock=True, invert=False)
        self.assertEqual((dock.state_signal_id, dock.estimate_params["state_invert"]), (other, True))

    def test_bind_dock_legacy_params_without_invert(self):  # точка з попередньої версії (без ключа): NO — без запису
        self.bind(with_dock=True)
        dock = self.dock_point()
        dock.estimate_params = {"loss_kw_per_k": 3.5, "t_out_signal": OUTDOOR, "t_in": 18.0}
        self.bind(with_dock=True)
        self.assertNotIn("state_invert", dock.estimate_params)  # відсутній ключ = False, зайвого запису немає
        self.bind(with_dock=True, invert=True)
        self.assertIs(dock.estimate_params["state_invert"], True)

    def test_dock_loss_nc_gate_end_to_end(self):  # R-04 п. 4: NC-ворота через міст → оцінка HM-DOCK як у NO
        self.bind(with_dock=True, invert=True)
        dock = self.dock_point()
        t0 = datetime(2026, 10, 17, 6, 0)
        gate, out = dock.state_signal_id, self.Signal.search([("code", "=", OUTDOOR)], limit=1)
        self.feed(gate, [(t0 - timedelta(seconds=60), 1.0), (t0 + timedelta(seconds=225), 0.0)])  # NC: відкрито 75 %
        self.feed(out, [(t0 - timedelta(seconds=300), 7.0), (t0 + timedelta(seconds=600), 7.0)])
        meter = self.Meter.search([("code", "=", "HM-DOCK")])
        self.build(meter, now=t0 + SLOT)
        row = [r for r in self.rows(meter) if r[0] == t0][0]
        self.assertAlmostEqual(row[2], 3.5 * (dock.estimate_params["t_in"] - 7.0) * 0.75, places=2)
        self.assertEqual(row[6], "estimated")

    def test_bind_without_balance_or_yard(self):  # AC-B01
        with patch.object(heat, "balance", return_value=self.env["td.bms.heat.balance"]):
            self.assertEqual(self.Point._td_bind_extra(), {})
        self.assertEqual(self.bind(), {"points": 0, "meters": 0})  # воріт немає (патч) — DOCK не створюється
        self.assertFalse(self.heat_points().filtered(lambda p: p.code == "DOCK"))
        self.assertFalse(self.Meter.search([("code", "=", "HM-DOCK")]))
        self.assertFalse(find_dock_signal({"td.signal": self.Signal}))  # середовище без td.yard.gate (td_yard немає)
        self.assertEqual(find_dock({"td.signal": self.Signal}), (self.Signal, False))

    def test_install_order_state(self):  # AC-B02: auto_install, залежності, результат після установки
        module = self.env["ir.module.module"].search([("name", "=", "td_energy_resources_bms")])
        self.assertEqual(module.state, "installed")
        self.assertTrue(module.auto_install)
        self.assertEqual(set(module.dependencies_id.mapped("name")), {"td_energy_resources", "td_bms"})
        self.assertLessEqual(BASE_POINTS, self.heat_after_install)  # post_init_hook моста відпрацював
        if "td.yard.gate" in self.env:  # DOCK — лише якщо td_yard встановлено до моста; решта збігається
            self.assertLessEqual(self.heat_after_install - BASE_POINTS, {"DOCK"})
        else:
            self.assertEqual(self.heat_after_install, BASE_POINTS)

    # --- AC-B01, AC-B02, Q-08: повна конфігурація (td_yard)
    def yard_gate_model(self):
        if "td.yard.gate" not in self.env:
            self.skipTest("td_yard не встановлено — повну конфігурацію не перевірити")
        return self.env["td.yard.gate"]

    def test_yard_real_gate_binds_dock(self):  # AC-B01: DOCK — за сигналом воріт відвантаження td_yard (схід, out/both)
        gate = self.yard_gate_model().search(
            [("state_signal_id", "!=", False), ("side", "=", "east"), ("direction", "in", ("out", "both"))],
            order="sequence, id",
            limit=1,
        )
        self.assertEqual(gate, self.env.ref("td_yard.gate_e"))  # КПП відвантаження (виїзд)
        self.assertEqual(find_dock_signal(self.env), gate.state_signal_id)
        self.assertEqual(self.Point._td_bind_extra()["points"], 1)  # без підміни: ворота td_yard (DOCK прибрано)
        dock = self.Point.search([("code", "=", "DOCK"), ("resource_id.code", "=", "heat")])
        self.assertEqual((dock.estimate_method, dock.kind), ("gate_loss", "consumer"))
        self.assertEqual(dock.state_signal_id, gate.state_signal_id)
        meter = self.Meter.search([("code", "=", "HM-DOCK")])
        self.assertEqual((meter.mode, meter.point_id), ("estimate", dock))
        self.assertEqual(self.Point._td_bind_extra(), {"points": 0, "meters": 0})  # ідемпотентно
        self.fx_gates()  # детектор dock_gates працює з сигналом реальних воріт; дія — у «Двір»
        item = self.rule("dock_gates")._td_detect_dock_gates(NOW)[0]
        self.assertEqual((item["dedup_key"], item["point_code"]), ("dock_gates:*", "DOCK"))
        self.assertEqual([a["code"] for a in item["actions"]], ["yard_gates"])
        self.assertEqual(item["actions"][0]["params"], {"xmlid": "td_yard.action_td_yard_gate"})

    def test_yard_gate_selection(self):  # Q-08: лише схід, out/both, активні, зі стан-сигналом; порядок sequence, id
        Gate = self.yard_gate_model()
        real = self.env.ref("td_yard.gate_e").state_signal_id
        signals = {k: self.signal("test/yard/gate_%s" % k, unit="") for k in "abcd"}

        def make(code, side, direction, key=None, **kw):
            return Gate.create(
                dict(td_code=code, name=code, side=side, direction=direction, sequence=1, **kw,
                     state_signal_id=key and signals[key].id)
            )  # fmt: skip

        make("T-W", "west", "out", "a")  # захід
        make("T-E-IN", "east", "in", "b")  # в'їзд
        make("T-E-NOSIG", "east", "out")  # без сигналу
        make("T-E-OFF", "east", "out", "c", active=False)  # архівні
        self.assertEqual(find_dock_signal(self.env), real)  # лишається GATE-E (sequence 20)
        make("T-E-BOTH", "east", "both", "d")
        self.assertEqual(find_dock_signal(self.env), signals["d"])  # sequence 1 < 20

    def test_yard_gate_company_filter(self):  # Q-08: ворота іншої компанії не потрапляють у DOCK цієї
        Gate = self.yard_gate_model()
        real = self.env.ref("td_yard.gate_e")
        other = self.env["res.company"].create({"name": "T-Інша компанія"})
        foreign = self.signal("test/yard/gate_foreign", unit="")
        Gate.create(
            dict(td_code="T-E-FOREIGN", name="T-E-FOREIGN", side="east", direction="out", sequence=1,
                 state_signal_id=foreign.id, company_id=other.id, invert_di=True)
        )  # fmt: skip
        self.assertEqual(
            find_dock(self.env), (real.state_signal_id, bool(real.invert_di))
        )  # sequence 1 < 20 — не береться
        self.assertEqual(find_dock(self.env, other), (foreign, True))  # а для своєї компанії — береться
        self.assertEqual(
            find_dock(self.env, self.env["res.company"].create({"name": "T-Порожня"})), (self.Signal, False)
        )
        self.assertEqual(self.Point._td_bind_extra()["points"], 1)
        self.assertEqual(self.dock_point().state_signal_id, real.state_signal_id)

    def test_yard_gate_nc_invert_follows_invert_di(self):  # R-B1: `DOCK.state_invert` = `td.yard.gate.invert_di`
        self.yard_gate_model()
        gate = self.env.ref("td_yard.gate_e")
        gate.invert_di = True
        self.assertEqual(find_dock(self.env), (gate.state_signal_id, True))
        self.assertEqual(self.Point._td_bind_extra()["points"], 1)  # без підміни: ворота td_yard
        dock = self.dock_point()
        self.assertIs(dock.estimate_params["state_invert"], True)
        gate.invert_di = False  # монтажник виправив контакт → повторна привʼязка оновлює параметр
        self.assertEqual(self.Point._td_bind_extra(), {"points": 0, "meters": 0})
        self.assertIs(dock.estimate_params["state_invert"], False)
        self.assertEqual(len(self.dock_point()), 1)

    # --- AC-B03, AC-B05: KPI й список «Тепло»
    def fx_heat_screen(self):
        self.bind(with_dock=True)
        b = self.balance
        self.feed_signal(b.boiler_heat_signal_id, 390.0)
        self.feed_signal(self.ensure(b, "boiler_supply_signal_id", "equipment/BOILER/supply_c", "°C"), 70.0)
        self.feed_signal(self.ensure(b, "boiler_return_signal_id", "equipment/BOILER/return_c", "°C"), 52.0)
        for unit in self.rv:
            self.feed_signal(unit.heat_signal_id, 228.0 / len(self.rv))
        self.feed_signal(self.ahu.heat_signal_id, 74.0)
        dock = self.Meter.search([("code", "=", "HM-DOCK")])
        self.res_interval(dock, datetime(2026, 10, 17, 11, 0), 11.5, quality="estimated", rate=46.0)

    def test_heat_kpis_and_list(self):  # AC-B03
        self.fx_heat_screen()
        data = self.Dash.get_resources("heat")
        kpis = {k["id"]: k for k in data["resource"]["kpis"]}
        self.assertEqual(kpis["power"]["value"], 390)
        self.assertEqual(kpis["power"]["note"], "подача 70 °C · зворот 52 °C")
        self.assertEqual({"power", "today", "indoor", "recovery"}, set(kpis))
        items = data["resource"]["list"]["items"]
        self.assertEqual(
            [(i["code"], i["value"]) for i in items], [("RV-ALL", 228), ("AHU-1", 74), ("DOCK", 46), ("OFFICE", 42)]
        )
        self.assertEqual([i["quality"] for i in items], ["measured", "measured", "estimated", "estimated"])
        self.assertEqual(data["resource"]["list"]["unaccounted"], {"value": 0, "pct": 0.0})

    def test_heat_list_hook(self):  # AC-B03: хук напряму; OFFICE = max(0, Σ джерел − решта)
        points = [
            {"code": c, "name": n, "kind": k}
            for c, n, k in (("HEAT-BOILER", "К", "source"), ("RV-ALL", "RV", "consumer"), ("AHU-1", "A", "consumer"),
                            ("DOCK", "Д", "consumer"), ("OFFICE", "О", "consumer"))
        ]  # fmt: skip
        ctx = {"points": points, "rates": {"RV-ALL": 228.0, "AHU-1": 74.0, "DOCK": 46.0}, "rate": 390.0}
        got = {i["code"]: i["value"] for i in self.Dash._td_heat_list(ctx)}
        self.assertEqual(got, {"RV-ALL": 228.0, "AHU-1": 74.0, "DOCK": 46.0, "OFFICE": 42.0})
        ctx["rate"] = 300.0  # решта більша за джерела — залишок не від'ємний
        self.assertEqual({i["code"]: i["value"] for i in self.Dash._td_heat_list(ctx)}["OFFICE"], 0.0)
        ctx["rate"] = None
        self.assertIsNone({i["code"]: i["value"] for i in self.Dash._td_heat_list(ctx)}["OFFICE"])
        self.assertIsNone(
            self.Dash._td_heat_list({"points": [{"code": "X", "name": "X", "kind": "consumer"}], "rates": {}})
        )

    def feed_ahu(self, supply=21.0, heat_kw=74.0, flow=32000.0, indoor=18.4, outdoor=7.0, dp=200.0):
        for signal, value in (
            (self.ahu.supply_signal_id, supply), (self.ahu.heat_signal_id, heat_kw), (self.ahu.airflow_signal_id, flow),
            (self.ahu.indoor_signal_id, indoor), (self.ahu.filter_signal_id, dp),
            (self.Signal.search([("code", "=", OUTDOOR)]), outdoor),
        ):  # fmt: skip
            self.feed_signal(signal, value)

    def kpis(self):
        return {k["id"]: k for k in self.Dash._td_heat_kpis({"env": self.env, "now": NOW})}

    def test_recovery_kpi(self):  # AC-B04: R-B3, фікстура 32 000 м³/год, 74 кВт, 21,0/18,4/7,0
        self.feed_ahu()
        eta = heat.recuperation(21.0, 74.0, 32000.0, 20000.0, 18.4, 7.0)
        self.assertAlmostEqual(eta, 0.6315, places=3)
        kpi = self.kpis()["recovery"]
        self.assertEqual(kpi["value"], 63)  # η = 0,632 → «63 %» (як у макеті, ціле)
        self.assertEqual((kpi["tone"], kpi["quality"], kpi["unit"]), ("bad", "estimated", "%"))
        self.assertEqual((kpi["id"], kpi["note"]), ("recovery", "норма ≥ 70 %"))
        self.feed_ahu(dp=280.0)  # ΔP > 250 Па
        self.assertEqual(self.kpis()["recovery"]["note"], "норма ≥ 70 % · фільтр брудний")
        self.feed_ahu(heat_kw=59.0)  # η ≈ 0,75 ≥ норми
        good = self.kpis()["recovery"]
        self.assertEqual(good["tone"], "good")
        self.assertGreaterEqual(good["value"], 70.0)

    def test_recovery_guards(self):  # AC-B04: T_in − T_out < 5, η ∉ [0, 1], малий потік, немає даних
        self.assertIsNone(heat.recuperation(21.0, 74.0, 32000.0, 20000.0, 10.0, 7.0))  # ΔT = 3 К
        self.assertIsNone(heat.recuperation(21.0, 0.0, 32000.0, 20000.0, 18.4, 7.0))  # η = 1,23
        self.assertIsNone(heat.recuperation(21.0, 200.0, 32000.0, 20000.0, 18.4, 7.0))  # η < 0
        self.assertIsNone(heat.recuperation(21.0, 74.0, 1000.0, 20000.0, 18.4, 7.0))  # < 10 % номіналу
        self.assertIsNone(heat.recuperation(21.0, None, 32000.0, 20000.0, 18.4, 7.0))
        self.feed_ahu(indoor=10.0)
        kpi = self.kpis()["recovery"]
        self.assertEqual((kpi["value"], kpi["tone"], kpi["note"]), (None, "neutral", "—"))
        extract = self.signal("ventilation/units/AHU-1/extract_c", unit="°C")  # зарезервований сигнал витяжки
        self.feed_signal(extract, 19.4)
        self.feed_ahu(indoor=10.0)
        self.assertEqual(self.kpis()["recovery"]["value"], 58)  # T_in = 19,4: η = 0,5805

    def test_indoor_kpi_and_chart_note(self):  # AC-B05
        self.feed_ahu()
        for unit in self.units.filtered(lambda u: u.required_in_work and u.kind in ("roofvent", "ahu")):
            self.feed_signal(unit.indoor_signal_id, 18.4)
        self.balance.t_in_set = 18.0
        indoor = self.kpis()["indoor"]
        self.assertEqual((indoor["value"], indoor["unit"], indoor["tone"]), (18.4, "°C", "good"))
        self.assertEqual(indoor["note"], "уставка 18 °C · зовні 7 °C")
        self.assertEqual(indoor["label"], "Температура в цеху")
        for unit in self.units.filtered(lambda u: u.required_in_work and u.kind in ("roofvent", "ahu")):
            self.feed_signal(unit.indoor_signal_id, 19.0)  # відхилення рівно 1 К
        self.assertEqual(self.kpis()["indoor"]["tone"], "good")
        for unit in self.units.filtered(lambda u: u.required_in_work and u.kind in ("roofvent", "ahu")):
            self.feed_signal(unit.indoor_signal_id, 19.6)
        self.assertEqual(self.kpis()["indoor"]["tone"], "bad")
        self.stale(OUTDOOR)
        self.assertEqual(self.kpis()["indoor"]["note"], "уставка 18 °C")
        self.balance.capacity_kw = 520
        self.assertEqual(self.Dash._td_heat_chart_note({"env": self.env}), "520")
        self.fx_heat_screen()
        self.assertEqual(
            self.Dash.get_resources("heat")["resource"]["chart"]["note"], "теплобаланс цеху з BMS · котли 520 кВт"
        )
        self.balance.capacity_kw = 0
        self.assertIsNone(self.Dash._td_heat_chart_note({"env": self.env}))
        other = self.env["res.company"].create({"name": "Інша компанія без балансу"})
        env2 = self.env(context=dict(self.env.context, allowed_company_ids=[other.id]))
        self.assertEqual(self.Dash._td_heat_kpis({"env": env2, "now": NOW}), [])
        self.assertIsNone(self.Dash._td_heat_chart_note({"env": env2}))
        self.assertIsNone(self.Dash._td_heat_list({"points": [], "rates": {}}))

    # --- AC-B06: preheat_early
    def fx_preheat(self, ready_before=55, days=None, boiler_rate=46.0):
        """Цех досягає 18 °C за `ready_before` хв до зміни у робочі дні; газ котельні `boiler_rate` перед зміною."""
        unit = self.units.filtered(lambda u: u.code == "RV-01")
        days, win = days or self.work_days()[0], shifts.load_windows(self.env)
        for day in days:
            start = win.first_start(day)
            grid = [start - timedelta(hours=6) + timedelta(minutes=5 * i) for i in range(6 * 12 + 1)]
            self.feed(
                unit.indoor_signal_id,
                [(t, 15.0 if t < start - timedelta(minutes=ready_before) else 18.5) for t in grid],
            )
        meter = self.Meter.search([("code", "=", "GM-BOILER")])
        rows = []
        starts = [win.first_start(d) for d in self.work_days()[0]]
        for ts in self.slots():
            local = to_local(ts)
            hot = any(s - timedelta(hours=4) <= ts < s for s in starts)
            rows.append(
                {
                    "meter_id": meter.id, "metric": "main", "ts_start": ts, "ts_end": ts + SLOT, "day": local.date(),
                    "hour_local": local.hour, "qty": (boiler_rate if hot else 0.0) * 0.25,
                    "rate_avg": boiler_rate if hot else 0.0, "kwh_eq": 0.0, "price": 0.0, "cost": 0.0,
                    "quality": "measured", "built_at": NOW,
                }
            )  # fmt: skip
        self.ResInterval.create(rows)

    def test_preheat_early(self):  # AC-B06
        self.fx_preheat()
        self.env.flush_all()
        found = self.rule("preheat_early")._td_detect_preheat_early(NOW)
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertEqual(item["dedup_key"], "preheat_early:*")
        self.assertAlmostEqual(item["est_qty_month"], 415.0, delta=0.1)
        self.assertEqual(item["est_saving_month"], 8216.0)
        self.assertEqual(item["text"], "Цех досягає 18 °C о 06:05, а зміна о 07:00. Пізніший старт на 25 хв.")
        ev = item["evidence"]
        self.assertEqual((ev["margin_med_min"], ev["days"], ev["preheat_rate_m3h"]), (55.0, 5, 46.0))

    def test_preheat_early_engine_actions(self):  # AC-B06: дія — посилання на налаштування BMS (без control)
        self.fx_preheat()
        rule = self.rule("preheat_early")
        self.assertEqual(rule.action_run()["created"], 1)
        opp = self.env["td.energy.opportunity"].search([("dedup_key", "=", "preheat_early:*")])
        self.assertEqual(opp.resource_id.code, "gas")
        self.assertEqual(opp.actions[0]["params"], {"xmlid": "td_bms.action_td_bms_heat_balance_open"})
        self.assertEqual(self.env["td.energy.opportunity"].get_list("gas")["items"][0]["actions"][0]["enabled"], True)

    def test_preheat_early_negative(self):  # AC-B06
        self.fx_preheat(ready_before=25)  # margin_med 25 ≤ margin_min 30
        self.env.flush_all()
        self.assertEqual(self.rule("preheat_early")._td_detect_preheat_early(NOW), [])

    def test_preheat_early_few_days(self):  # AC-B06: днів < 3
        self.fx_preheat(days=self.work_days()[0][:2])
        self.env.flush_all()
        self.assertEqual(self.rule("preheat_early")._td_detect_preheat_early(NOW), [])

    # --- AC-B07: ahu_recuperation
    def fx_ahu_series(self, heat_kw=73.9318, dp=280.0):
        grid = [LO - timedelta(minutes=30) + timedelta(minutes=15 * i) for i in range(96 * 7 + 4)]
        for signal, value in (
            (self.ahu.supply_signal_id, 21.0), (self.ahu.heat_signal_id, heat_kw),
            (self.ahu.airflow_signal_id, 32000.0),
            (self.ahu.indoor_signal_id, 18.4), (self.ahu.filter_signal_id, dp),
            (self.Signal.search([("code", "=", OUTDOOR)]), 7.0),
        ):  # fmt: skip
            self.feed(signal, [(t, value) for t in grid])
        self.env.flush_all()

    def test_ahu_recuperation(self):  # AC-B07: η 0,632, норма 0,70, ΔT 11,4, 80 год, 2,0722
        self.fx_ahu_series()
        found = self.rule("ahu_recuperation")._td_detect_ahu_recuperation(NOW)
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertEqual((item["dedup_key"], item["node_code"]), ("ahu_recuperation:AHU-1", "AHU-1"))
        self.assertAlmostEqual(item["est_qty_month"], 2921.6, delta=0.5)
        self.assertAlmostEqual(item["est_saving_month"], 6054.0, delta=2)
        ev = item["evidence"]
        self.assertAlmostEqual(ev["eta_mean"], 0.632, places=3)
        self.assertEqual((ev["run_hours"], ev["dt"], ev["airflow_m3h"]), (80.0, 11.4, 32000.0))
        self.assertAlmostEqual(ev["loss_kw"], 8.43, places=2)
        self.assertIn("63,2 %", item["text"])
        self.assertIn("фільтр", item["text"])  # ΔP 280 > 250
        self.assertEqual(self.rule("ahu_recuperation").actions[0]["kind"], "ticket")
        self.rule("ahu_recuperation").action_run()
        opp = self.env["td.energy.opportunity"].search([("dedup_key", "=", "ahu_recuperation:AHU-1")])
        self.assertEqual(opp.node_id.code, "AHU-1")
        self.assertIn("[OPP-%d]" % opp.id, opp.actions[0]["params"]["description"])

    def test_ahu_recuperation_dp_only(self):  # AC-B07: лише ΔP → економія 0 → резерв не створюється
        self.fx_ahu_series(heat_kw=59.0, dp=280.0)  # η ≈ 0,75 ≥ 0,70
        found = self.rule("ahu_recuperation")._td_detect_ahu_recuperation(NOW)
        self.assertEqual((len(found), found[0]["est_saving_month"]), (1, 0.0))
        self.assertEqual(found[0]["evidence"]["warning"], "filter_dp_only")
        stats = self.rule("ahu_recuperation").action_run()
        self.assertEqual((stats["found"], stats["created"]), (0, 0))
        self.assertFalse(self.env["td.energy.opportunity"].search([("dedup_key", "=", "ahu_recuperation:AHU-1")]))

    def test_ahu_recuperation_ok(self):  # AC-B07: η у нормі й фільтр чистий
        self.fx_ahu_series(heat_kw=59.0, dp=200.0)
        self.assertEqual(self.rule("ahu_recuperation")._td_detect_ahu_recuperation(NOW), [])

    # --- AC-B08: dock_gates
    def make_dock(self, invert=False):
        heat_res = self.resource("heat")
        signal = self.signal("test/yard/gate_open", unit="")
        return self.Point.create(
            {
                "resource_id": heat_res.id, "code": "DOCK", "name": "Втрати через ворота", "kind": "consumer",
                "estimate_method": "gate_loss", "state_signal_id": signal.id,
                "estimate_params": {
                    "loss_kw_per_k": 3.5, "t_out_signal": OUTDOOR, "t_in": 18.0, "state_invert": invert,
                },
            }
        )  # fmt: skip

    def fx_gates(self, spans_min=(12, 12, 12, 16)):
        """Щодоби відкриття воріт тривалістю `spans_min` (хв) о 09:00, 11:00, 13:00, 15:00; зовні 7 °C. Для точки з
        `state_invert` (NC) сигнал протилежний: 0 — відкрито, 1 — закрито."""
        point = self.Point.search([("code", "=", "DOCK"), ("resource_id.code", "=", "heat")])
        invert = bool(point.estimate_params.get("state_invert"))
        out = self.Signal.search([("code", "=", OUTDOOR)])
        for day in (date(2026, 10, 10) + timedelta(days=n) for n in range(7)):
            d0 = dates.local_day_bounds(day)[0]
            points = []
            for k, minutes in enumerate(spans_min):
                t = d0 + timedelta(hours=9 + 2 * k)
                points += [(t, 0.0 if invert else 1.0), (t + timedelta(minutes=minutes), 1.0 if invert else 0.0)]
            self.feed(point.state_signal_id, points)
            self.feed(out, [(d0 + timedelta(hours=1), 7.0), (d0 + timedelta(hours=13), 7.0)])
        self.env.flush_all()

    def test_dock_gates(self):  # AC-B08: 4/добу, 52 хв, норма 20, 3,5 кВт/К, ΔT 11
        self.make_dock()
        self.fx_gates()
        found = self.rule("dock_gates")._td_detect_dock_gates(NOW)
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertEqual((item["dedup_key"], item["point_code"]), ("dock_gates:*", "DOCK"))
        self.assertAlmostEqual(item["est_qty_month"], 622.3, delta=0.3)
        self.assertAlmostEqual(item["est_saving_month"], 1290.0, delta=1)
        ev = item["evidence"]
        self.assertEqual((ev["long_per_day"], ev["open_min_day"], ev["dt"], ev["loss_kw"]), (4.0, 52.0, 11.0, 38.5))
        self.assertAlmostEqual(ev["excess_h_day"], 0.5333, places=3)
        yard = bool(self.env.ref("td_yard.action_td_yard_gate", raise_if_not_found=False))
        self.assertEqual(
            [a["code"] for a in item["actions"]], ["yard_gates"] if yard else []
        )  # без td_yard — запасна дія
        self.rule("dock_gates").action_run()
        opp = self.env["td.energy.opportunity"].search([("dedup_key", "=", "dock_gates:*")])
        self.assertEqual(opp.resource_id.code, "heat")
        first = self.env["td.energy.opportunity"].get_list("heat")["items"][0]["actions"][0]
        self.assertEqual(first["code"], "yard_gates" if yard else "open")

    def test_dock_gates_nc_contact(self):  # AC-B08: NC-ворота (`state_invert`, сигнал протилежний) — та сама знахідка
        self.make_dock(invert=True)
        self.fx_gates()
        found = self.rule("dock_gates")._td_detect_dock_gates(NOW)
        self.assertEqual(len(found), 1)
        ev = found[0]["evidence"]
        self.assertEqual((ev["long_per_day"], ev["open_min_day"], ev["dt"], ev["loss_kw"]), (4.0, 52.0, 11.0, 38.5))
        self.assertAlmostEqual(found[0]["est_saving_month"], 1290.0, delta=1)

    def test_dock_gates_negative(self):  # AC-B08: довгих відкриттів < 3 на добу
        self.make_dock()
        self.fx_gates(spans_min=(12, 12, 5, 5))  # дві довгі (≥ 10 хв) на добу
        self.assertEqual(self.rule("dock_gates")._td_detect_dock_gates(NOW), [])

    def test_dock_gates_no_point(self):  # AC-B08: немає точки DOCK — правило пропущено без помилки
        self.assertEqual(self.rule("dock_gates")._td_detect_dock_gates(NOW), [])
        rule = self.rule("dock_gates")
        stats = rule.action_run()
        self.assertEqual((stats["found"], stats["created"]), (0, 0))
        self.assertFalse(rule.last_error)

    def test_openings(self):  # R-B4: розбір сирих показань воріт
        t0 = datetime(2026, 10, 12, 6, 0)
        pts = [
            (t0, 1.0),
            (t0 + timedelta(minutes=12), 0.0),
            (t0 + timedelta(hours=1), 1.0),
            (t0 + timedelta(hours=1, minutes=5), 1.0),
        ]
        spans = heat.openings(pts)
        self.assertEqual(spans[0], (t0, t0 + timedelta(minutes=12)))
        self.assertEqual(spans[1][0], t0 + timedelta(hours=1))
        self.assertEqual(
            spans[1][1], t0 + timedelta(hours=1, minutes=5) + timedelta(seconds=heat.HOLD_S)
        )  # не закрите — обрізається
        inv = [(ts, 1.0 - v) for ts, v in pts]  # NC-контакт: протилежні значення дають ті самі відкриття
        self.assertEqual(heat.openings(inv, invert=True), spans)

    # --- AC-B09: backfill тепла
    def sums(self, code):
        self.env.flush_all()
        self.env.cr.execute(
            "SELECT COALESCE(SUM(r.qty), 0), COUNT(*) FROM td_energy_res_interval r "
            "JOIN td_energy_meter m ON m.id = r.meter_id WHERE m.code = %s AND r.is_backfill",
            (code,),
        )
        return self.env.cr.fetchone()

    def test_backfill_heat(self):  # AC-B09
        self.chp_signal()
        self.bind(with_dock=True)
        until = datetime(2026, 10, 17, 0, 0)
        stats = self.ResInterval._td_backfill(days=3, until=until, seed=20261018)
        slots = 3 * 96
        self.assertEqual(self.sums("HM-BOILER")[1], slots)
        boiler, gas = self.sums("HM-BOILER")[0], self.sums("GM-BOILER")[0]
        self.assertGreater(boiler, 0)
        self.assertAlmostEqual(boiler, gas * 10.5 * 0.914, delta=0.03 * boiler)  # ± 3 %
        sources = boiler + self.sums("HM-CHP")[0]
        branches = sum(self.sums(c)[0] for c in ("HM-RV", "HM-AHU1", "HM-DOCK", "HM-OFFICE"))
        self.assertAlmostEqual(branches, sources, delta=0.05 * sources)  # Σ гілок ≈ джерел ± 5 %
        self.assertGreaterEqual(stats["meters"], 6)
        self.env.cr.execute(
            "SELECT m.code, r.quality FROM td_energy_res_interval r JOIN td_energy_meter m ON m.id = r.meter_id "
            "WHERE m.code IN ('HM-DOCK', 'HM-OFFICE', 'HM-BOILER') AND r.is_backfill GROUP BY m.code, r.quality"
        )
        self.assertEqual(
            dict(self.env.cr.fetchall()), {"HM-DOCK": "estimated", "HM-OFFICE": "estimated", "HM-BOILER": "measured"}
        )
        before = {c: self.sums(c) for c in HEAT_CODES}
        again = self.ResInterval._td_backfill(days=3, until=until, seed=20261018)  # ідемпотентність
        self.assertEqual({c: self.sums(c) for c in HEAT_CODES}, before)
        self.assertEqual(again["rows"], 0)
        self.assertGreater(again["skipped"], 0)
        purged = self.ResInterval._td_backfill(days=3, until=until, seed=20261018, purge=True)
        self.assertGreater(purged["purged_rows"], 0)
        self.assertEqual(sum(self.sums(c)[1] for c in HEAT_CODES), 0)

    def test_backfill_heat_resource_filter(self):  # AC-B09: `resources` без heat — тепло не генерується
        self.bind(with_dock=True)
        self.ResInterval._td_backfill(days=1, until=datetime(2026, 10, 17, 0, 0), resources=["gas"])
        self.assertEqual(sum(self.sums(c)[1] for c in HEAT_CODES), 0)
        self.assertGreater(self.sums("GM-BOILER")[1], 0)

    def test_backfill_rates_formula(self):  # R-B5: генератори
        class State:
            heat_need, heat_chp, shift, hs = 300.0, 497.0, True, 10.0
            local = datetime(2026, 10, 17, 10, 0)

        rates = heat.backfill_rates(State)
        self.assertEqual((rates["HM-BOILER"], rates["HM-CHP"]), (0.0, 497.0))  # потреба нижча за КГУ
        self.assertAlmostEqual(rates["HM-RV"], 0.585 * 300.0)
        self.assertAlmostEqual(rates["HM-AHU1"], 0.19 * 300.0)
        self.assertGreater(rates["HM-DOCK"], 0.0)
        self.assertAlmostEqual(
            rates["HM-RV"] + rates["HM-AHU1"] + rates["HM-DOCK"] + rates["HM-OFFICE"],
            rates["HM-BOILER"] + rates["HM-CHP"],
        )
        State.shift = False
        self.assertEqual(heat.backfill_rates(State)["HM-DOCK"], 0.0)  # поза змінами ворота закриті
        self.assertAlmostEqual(heat.t_out_demo(200, 9), 7.0 + 8.0)  # doy 200 — максимум сезонної складової, sin(0) = 0

    # --- UI-B1
    def test_heat_note_template(self):  # UI-B1: шаблон-розширення ResKpis (закоментований до злиття W3-C)
        with file_open("td_energy_resources_bms/static/src/heat_note.xml", "rb") as f:
            raw = f.read().decode()
        etree.fromstring(raw.encode())  # файл — коректний XML
        self.assertIn('t-inherit="td_energy_resources.ResKpis"', raw)
        self.assertIn('t-inherit-mode="extension"', raw)
        self.assertIn("hasclass('o_td_res_quality')", raw)
        self.assertIn("оцінка", raw)
        self.assertEqual(self.env.ref("td_energy_resources_bms.rule_preheat_early").control_intent, False)

    def test_perf_heat_tab(self):  # AC-60 (ТП-01) для вкладки «Тепло» з мостом: ≤ 30 SQL на холодному кеші
        self.fx_heat_screen()
        self.feed_ahu()
        self.Dash.get_resources("heat")
        counts = []
        for _ in range(3):
            self.env.flush_all()
            self.env.invalidate_all()
            before = self.env.cr.sql_log_count
            self.Dash.get_resources("heat")
            counts.append(self.env.cr.sql_log_count - before)
        self.assertLessEqual(max(counts), 30, counts)
