"""Фікстури тестів factory3d_machine_connect (SPEC §13.0.1).

Теги всіх класів: `@tagged('post_install', '-at_install', 'f3d', 'f3d_machine_connect')`.
Від `F3DTelemetryMixin` використовуються лише `col`, `token`, `push()`, `set_sql()`, `api()`, `team_mech`, `user_plain`
і параметри telemetry; колектор і токен створюються тут (без сигналів telemetry).
"""

import hashlib
import json
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo.addons.factory3d_telemetry.tests.common import F3DTelemetryMixin
from odoo.tests import HttpCase, TransactionCase, new_test_user

from .. import hooks

D0 = date(2026, 10, 12)  # понеділок, EEST (UTC+3)
EEST = timedelta(hours=3)
P = "factory3d.machine_connect."

PARAMS = {
    "read_enabled": "True",
    "auto_start_enabled": "False",
    "write_enabled": "False",
    "micro_stop_s": "120",
    "pause_after_min": "10",
    "finish_idle_s": "60",
    "qty_sync_mode": "finish",
    "qty_sync_s": "300",
    "coverage_min": "0.95",
    "oee_good": "0.75",
    "oee_warn": "0.5",
    "no_job_activity_min": "15",
    "stack_diff_tolerance": "0",
    "stack_diff_confirm_min": "10",
    "gantry_auto_replenish": "False",
    "gantry_auto_feed": "False",
    "cutting_mode": "collector",
    "export_token_ttl_s": "600",
    "keep_log_days": "400",
    "keep_event_days": "90",
}

UA_STATES = ["OFFLINE", "STANDBY", "READY", "WORKING", "ERROR"]
UA_MODES = ["OTHER", "AUTOMATIC", "SEMIAUTOMATIC", "MANUAL", "SETUP", "SLEEP"]
SIGNAL_ROLES = {
    "state": "state",
    "mode": "mode",
    "alarm": "alarm",
    "pieces_out": "pieces",
    "job": "job",
    "event": "event",
    "job_cmd": "cmd",
    "machine_state": "machine_state",
}


def kt(t, day=D0):
    """«09:55[:ss]» за Києвом (EEST) → naive UTC datetime: `kt("09:55") == datetime(2026, 10, 12, 6, 55)`."""
    parts = [int(x) for x in t.split(":")]
    parts += [0] * (3 - len(parts))
    return datetime(day.year, day.month, day.day, *parts) - EEST


@contextmanager
def at(t, day=D0):
    with freeze_time(kt(t, day)):
        yield


class F3DMachineMixin(F3DTelemetryMixin):
    D0 = D0
    kt = staticmethod(kt)
    at = staticmethod(at)

    @classmethod
    def _setup_machine_fixtures(cls):
        cls._setup_base_fixtures()
        env = cls.env
        icp = env["ir.config_parameter"].sudo()
        for key, val in PARAMS.items():
            icp.set_param(P + key, val)
        cls.col = env["f3d.collector"].create({"code": "COL-T", "name": "Тестовий колектор"})
        cls.token = cls._gen_token(cls.col)
        cls._setup_users()
        cls._setup_calendar()
        cls._setup_equipment_workcenters()
        cls._setup_products()
        cls._setup_stacks()
        cls._setup_sources_signals()
        cls._setup_machines()
        cls.startClassPatcher(
            patch.object(
                type(cls.env["f3d.gantry.stack"]),
                "GANTRY_TARGETS",
                ("SAW-1", "SAW-2", "SAW-3", "NEST-1", "SAW-T"),
            )
        )

    # --- користувачі, календар, працівники ---------------------------------------------------------
    @classmethod
    def _setup_users(cls):
        env, base = cls.env, "base.group_user,"
        f3d = "factory3d_base."
        mk = lambda login, groups: new_test_user(env, login=login, groups=groups, tz="Europe/Kyiv")  # noqa: E731
        cls.user_f3d = mk("f3dm_user", base + f3d + "group_f3d_user")
        cls.user_f3d_manager = mk("f3dm_manager", base + f3d + "group_f3d_manager")
        cls.user_f3d_admin = mk("f3dm_admin", base + f3d + "group_f3d_admin")
        cls.user_mrp = mk("f3dm_mrp", base + "mrp.group_mrp_user")
        cls.user_mrp_manager = mk("f3dm_mrp_manager", base + "mrp.group_mrp_manager")
        cls.user_stock = mk("f3dm_stock", base + "stock.group_stock_user")
        cls.user_stock_manager = mk("f3dm_stock_manager", base + "stock.group_stock_manager")
        Emp = env["hr.employee"]
        cls.emp_mrp = Emp.create({"name": "Оператор МРП (тест)", "user_id": cls.user_mrp.id})
        cls.emp_master = Emp.create({"name": "Майстер (тест)", "user_id": cls.user_mrp_manager.id})
        for attr, name, barcode, code in (
            ("emp_ua", "Оператор UA (тест)", "OPUAT", "OP-UA-T"),
            ("emp_saw", "Оператор SAW (тест)", "OPSAWT", "OP-SAW-T"),
            ("emp_io", "Оператор IO (тест)", "OPIOT", "OP-IO-T"),
            ("emp_x", "Сторонній оператор", "OPXT", "OP-X-T"),
        ):
            setattr(cls, attr, Emp.create({"name": name, "barcode": barcode, "f3d_code": code}))

    @classmethod
    def _setup_calendar(cls):
        att = []
        for dow in "01234":
            att.append(
                (0, 0, {"name": "Ранок", "dayofweek": dow, "hour_from": 7.0, "hour_to": 11.5, "day_period": "morning"})
            )
            att.append(
                (
                    0,
                    0,
                    {"name": "День", "dayofweek": dow, "hour_from": 12.0, "hour_to": 15.5, "day_period": "afternoon"},
                )
            )
        cls.cal = cls.env["resource.calendar"].create(
            {"name": "Зміна 1 (тест)", "tz": "Europe/Kyiv", "hours_per_day": 8, "attendance_ids": [(5, 0, 0)] + att}
        )

    # --- обладнання, РЦ ----------------------------------------------------------------------------
    @classmethod
    def _setup_equipment_workcenters(cls):
        env = cls.env
        Eq = env["maintenance.equipment"]
        for attr, name, code in (
            ("eq_ua", "Верстат OPC UA (тест)", "UA-T"),
            ("eq_io", "Верстат I/O (тест)", "IO-T"),
            ("eq_saw", "Розкрій (тест)", "SAW-T"),
        ):
            setattr(cls, attr, Eq.create({"name": name, "f3d_code": code, "maintenance_team_id": cls.team_mech.id}))
        cls.eq_gantry = Eq.search_f3d("GANTRY-1") or Eq.create({"name": "Портал (тест)", "f3d_code": "GANTRY-1"})
        WC = env["mrp.workcenter"]
        for attr, name, code in (
            ("wc_ua", "Верстат OPC UA (тест)", "UA-T"),
            ("wc_io", "Верстат I/O (тест)", "IO-T"),
            ("wc_saw", "Розкрій (тест)", "SAW-T"),
            ("wc_cnc", "Присадка (тест)", "CNC-T"),
        ):
            setattr(
                cls,
                attr,
                WC.create({"name": name, "f3d_code": code, "resource_calendar_id": cls.cal.id, "time_efficiency": 100}),
            )
        # DEC-1: у CE 19.0 немає wc.employee_ids (mrp_workorder, Enterprise) — очищаємо лише якщо поле є.
        if "employee_ids" in WC._fields:
            (cls.wc_ua | cls.wc_io | cls.wc_saw | cls.wc_cnc).write({"employee_ids": [(5, 0, 0)]})

    # --- товари, партії ----------------------------------------------------------------------------
    @classmethod
    def _setup_products(cls):
        Product = cls.env["product.product"]

        def prod(name, code, **kw):
            return Product.create({"name": name, "default_code": code, **kw})

        board = {"is_storable": True, "tracking": "lot", "f3d_sheet_length_mm": 2800, "f3d_sheet_width_mm": 2070}
        cls.board = prod("ДСП 16 мм тест 2800×2070", "BOARD-T", f3d_thickness_mm=16, **board)
        cls.board2 = prod("ДСП 16 мм тест (інший декор)", "BOARD-T2", f3d_thickness_mm=16, **board)
        cls.hdf = prod("ХДФ 3 мм тест 2800×2070", "HDF-T", f3d_thickness_mm=3, **board)
        cls.edge = prod("Крайка тест", "EB-T", type="consu")
        cls.fg = prod("Тумба тест", "FG-T")
        Lot = cls.env["stock.lot"]
        company = cls.env.company.id
        cls.lot_l1 = Lot.create({"name": "L1", "product_id": cls.board.id, "company_id": company})
        cls.lot_l2 = Lot.create({"name": "L2", "product_id": cls.board.id, "company_id": company})

    @classmethod
    def _setup_stacks(cls):
        env = cls.env
        wh = env["stock.warehouse"].search([("company_id", "=", env.company.id)], limit=1)
        Loc = env["stock.location"]
        for attr, code in (("loc_t1", "PLT-T1"), ("loc_t2", "PLT-T2")):
            setattr(
                cls,
                attr,
                Loc.create(
                    {
                        "name": code,
                        "location_id": wh.lot_stock_id.id,
                        "f3d_code": code,
                        "f3d_loc_kind": "stack",
                        "f3d_capacity": 60,
                    }
                ),
            )
        cls.stack_t1 = env["f3d.gantry.stack"].create({"location_id": cls.loc_t1.id})
        cls.stack_t2 = env["f3d.gantry.stack"].create({"location_id": cls.loc_t2.id})

    @classmethod
    def put_stock(cls, product, location, qty, lot=None):
        cls.env["stock.quant"]._update_available_quantity(product, location, qty, lot_id=lot)

    # --- джерела й сигнали -------------------------------------------------------------------------
    @classmethod
    def _setup_sources_signals(cls):
        env = cls.env
        Src, Sig = env["f3d.source"], env["f3d.signal"]
        ua_params = {
            "endpoint": "opc.tcp://iot-sim:4840/f3d/",
            "security_mode": "None",
            "ns_uri": "http://todo.ltd/f3d/iot_sim/instances/",
        }

        def src(code, typ, params):
            return Src.create(
                {
                    "code": code,
                    "name": code,
                    "type": typ,
                    "params": params,
                    "collector_id": cls.col.id,
                    "module": "machine_connect",
                    "read_enabled": True,
                    "write_enabled": False,
                }
            )

        cls.src_ua = src("UA-UA-T", "opcua", ua_params)
        cls.src_saw = src("UA-SAW-T", "opcua", ua_params)
        cls.src_io = src("MB-U80-T", "modbus_tcp", {"host": "iot-sim", "port": 502, "unit": 80})
        ws = {
            "base_url": "http://iot-sim:8082",
            "auth": "api_key",
            "key_ref": "F3D_WOODSTORE_KEY",
            "vendor": "woodstore",
        }
        cut = {"base_url": "http://iot-sim:8083", "auth": "api_key", "key_ref": "F3D_CUTOPT_KEY", "vendor": "cutopt"}
        cls.src_ws = src("REST-WOODSTORE-T", "rest_vendor", ws)
        cls.src_cut = src("REST-CUTOPT-T", "rest_vendor", cut)
        cls.src_der = env.ref("factory3d_machine_connect.source_mc_derived")

        def make(code, protocol, io_unit, io_slot, source, eq, wc, prefix):
            sigs = {}
            for row in hooks._signal_rows(code, protocol, io_unit, io_slot, with_meta=True):
                template = row.pop("template")
                row.pop("source")
                row["source_id"] = (cls.src_der if template == "mc_state" else source).id
                if eq:
                    row["equipment_id"] = eq.id
                if wc:
                    row["workcenter_id"] = wc.id
                sigs[row["code"].rsplit("/", 1)[1]] = Sig.create(row)
            for key, sig in sigs.items():
                setattr(
                    cls, "sig_%s_%s" % (prefix, {"machine_state": "mstate"}.get(key, SIGNAL_ROLES.get(key, key))), sig
                )
            return sigs

        make("UA-T", "opcua", None, None, cls.src_ua, cls.eq_ua, cls.wc_ua, "ua")
        make("SAW-T", "opcua", None, None, cls.src_saw, cls.eq_saw, cls.wc_saw, "saw")
        make("IO-T", "io", 80, 0, cls.src_io, cls.eq_io, cls.wc_io, "io")
        # GANTRY-1 і оптимізатор: знайти за кодом (на копії демо їх створив хук) або створити за Додатком C.2
        rows = hooks._signal_rows("GANTRY-1", "gantry", None, None, with_meta=True)
        rows += hooks._signal_rows("CUTOPT", "cutopt", None, None, with_meta=True)
        for row in rows:
            template, source = row.pop("template"), row.pop("source")
            src_rec = {"REST-WOODSTORE": cls.src_ws, "REST-CUTOPT": cls.src_cut, "MC-DERIVED": cls.src_der}[source]
            sig = Sig.with_context(active_test=False).search([("code", "=", row["code"])], limit=1)
            if sig:
                sig.write({"source_id": src_rec.id})
            else:
                if template != "cut_cmd":
                    row["equipment_id"] = cls.eq_gantry.id
                sig = Sig.create({**row, "source_id": src_rec.id})
            attr = {
                "g_state": "sig_g_state",
                "g_job": "sig_g_job",
                "g_cmd": "sig_g_cmd",
                "g_stacks": "sig_g_stacks",
                "cut_cmd": "sig_cut_cmd",
            }.get(template)
            if attr:
                setattr(cls, attr, sig)

    @classmethod
    def _setup_machines(cls):
        Machine = cls.env["f3d.machine"]

        def mk(wc, protocol, source, prefix, eq, **kw):
            vals = {"workcenter_id": wc.id, "protocol": protocol, "equipment_id": eq.id if eq else False, **kw}
            if source:
                vals["source_id"] = source.id
            if prefix:
                for role, field in (
                    ("state", "sig_state_id"),
                    ("mode", "sig_mode_id"),
                    ("alarm", "sig_alarm_id"),
                    ("pieces", "sig_pieces_id"),
                    ("job", "sig_job_id"),
                    ("event", "sig_event_id"),
                    ("cmd", "sig_job_cmd_id"),
                    ("mstate", "sig_machine_state_id"),
                ):
                    sig = getattr(cls, "sig_%s_%s" % (prefix, role), None)
                    if sig:
                        vals[field] = sig.id
            return Machine.create(vals)

        cls.m_ua = mk(cls.wc_ua, "opcua", cls.src_ua, "ua", cls.eq_ua, auto_start_mode="job_or_single")
        cls.m_saw = mk(cls.wc_saw, "opcua", cls.src_saw, "saw", cls.eq_saw, auto_start_mode="job")
        cls.m_io = mk(cls.wc_io, "io", cls.src_io, "io", cls.eq_io, io_slot=0, auto_start_mode="job_or_single")
        cls.m_cnc = mk(cls.wc_cnc, "manual", None, None, None)

    # --- екземплярні помічники ---------------------------------------------------------------------
    def setUp(self):
        super().setUp()
        freezer = freeze_time(kt("10:30"))
        freezer.start()
        self.addCleanup(freezer.stop)

    def _icp(self):
        return self.env["ir.config_parameter"].sudo()

    def enable_autostart(self):
        self._icp().set_param(P + "auto_start_enabled", "True")

    def enable_write(self):
        """Чотири запобіжники Odoo (п'ятий — `F3D_WRITE_ENABLED` колектора — в Odoo-тестах не діє)."""
        self._icp().set_param(P + "write_enabled", "True")
        self._icp().set_param("factory3d.telemetry.write_enabled", "True")
        (self.src_ua | self.src_saw | self.src_ws | self.src_cut).write({"write_enabled": True})
        (self.sig_ua_cmd | self.sig_saw_cmd | self.sig_g_cmd | self.sig_cut_cmd).write({"write_enabled": True})

    def rk(self, sig, text=None, value=None, t="10:00:00", q="good"):
        res = {"code": sig.code, "ts": kt(t), "text": text, "value": value, "q": q}
        return {k: v for k, v in res.items() if v is not None}

    def ua(self, m, t, state=None, mode=None, alarm=None, pieces=None, job=None, q="good"):
        res = []
        if state is not None:
            res.append(self.rk(m.sig_state_id, state, UA_STATES.index(state), t, q))
        if mode is not None:
            res.append(self.rk(m.sig_mode_id, mode, UA_MODES.index(mode), t, q))
        if alarm is not None:
            res.append(self.rk(m.sig_alarm_id, "on" if alarm else "off", 1 if alarm else 0, t, q))
        if pieces is not None:
            res.append(self.rk(m.sig_pieces_id, None, pieces, t, q))
        if job is not None:
            res.append(self.rk(m.sig_job_id, job, None, t, q))
        return res

    def io(self, m, t, run=None, alarm=None, pieces=None, q="good"):
        res = []
        if run is not None:
            res.append(self.rk(m.sig_state_id, "run" if run else "stop", 1 if run else 0, t, q))
        if alarm is not None:
            res.append(self.rk(m.sig_alarm_id, "on" if alarm else "off", 1 if alarm else 0, t, q))
        if pieces is not None:
            res.append(self.rk(m.sig_pieces_id, None, pieces, t, q))
        return res

    def feed(self, readings, src="collector"):
        res = self.push(readings, src=src)
        self.env.invalidate_all()
        return res

    def tick(self, t):
        with at(t):
            self.env["f3d.machine"]._cron_tick()

    def oee_tick(self, t):
        with at(t):
            self.env["f3d.oee.shift"]._cron_oee()

    def gantry_tick(self, t):
        with at(t):
            self.env["f3d.gantry.job"]._cron_gantry()

    def cutmap_tick(self, t):
        with at(t):
            self.env["f3d.cut.map"]._cron_cutmap()

    def push_event(self, route, payload, source):
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        event_id = hashlib.sha256(("%s\n%s\n%s" % (route, source, canonical)).encode()).hexdigest()
        ev = {
            "event_id": event_id,
            "route": route,
            "ts": datetime.utcnow(),
            "remote": source,
            "headers": {},
            "payload": payload,
        }
        return self.env["f3d.push.event"].sudo()._f3d_receive([ev], self.col)

    def ev_ua(self, m, message_id, category, text, t, kind="alarm", active=True):
        payload = {
            "kind": kind,
            "source": m.source_id.code,
            "machine": m.code,
            "time": kt(t).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "message_id": message_id,
            "message_name": message_id,
            "category": category,
            "severity": 500,
            "text": text,
            "texts": {"uk": text},
            "path": [m.code],
            "group": "Drive",
            "active": active,
            "acked": False,
            "args": {},
        }
        return self.push_event("mc_opcua", payload, m.source_id.code)

    def make_log(self, m, state, start, end=None, wo=None, pieces=0):
        return (
            self.env["f3d.machine.state.log"]
            .sudo()
            .create(
                {
                    "machine_id": m.id,
                    "state": state,
                    "date_start": kt(start),
                    "date_end": kt(end) if end else False,
                    "workorder_id": wo.id if wo else False,
                    "pieces": pieces,
                }
            )
        )

    def cmd_done(self, cmd, result=None, data=None):
        text = result if result is not None else json.dumps(data, ensure_ascii=False, sort_keys=True)[:256]
        cmd.sudo().write({"state": "done", "result": text, "result_data": data, "done_at": datetime.utcnow()})

    def cmd_fail(self, cmd, error):
        cmd.sudo().write({"state": "failed", "error": error})

    def cmd_expire(self, cmd):
        cmd.sudo().write({"state": "expired"})

    def acts(self, rec, summary=None):
        domain = [("res_model", "=", rec._name), ("res_id", "=", rec.id)]
        if summary:
            domain.append(("summary", "=", summary))
        return self.env["mail.activity"].sudo().search(domain)

    # --- make_mo -----------------------------------------------------------------------------------
    def make_mo(self, wc, qty=14, comps=None, name=None, cycle=2.2):
        comps = comps if comps is not None else ((self.board, 0.5),)
        env = self.env
        bom = env["mrp.bom"].create(
            {
                "product_tmpl_id": self.fg.product_tmpl_id.id,
                "product_qty": 1,
                "bom_line_ids": [(0, 0, {"product_id": p.id, "product_qty": q}) for p, q in comps],
                "operation_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Операція %s" % wc.f3d_code,
                            "workcenter_id": wc.id,
                            "time_mode": "manual",
                            "time_cycle_manual": cycle,
                        },
                    )
                ],
            }
        )
        vals = {"product_id": self.fg.id, "product_qty": qty, "bom_id": bom.id}
        if name:
            vals["name"] = name
        mo = env["mrp.production"].create(vals)
        mo.action_confirm()
        mo.action_assign()
        return mo


class F3DMachineCase(F3DMachineMixin, TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_machine_fixtures()


class F3DMachineHttpCase(F3DMachineMixin, HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_machine_fixtures()
