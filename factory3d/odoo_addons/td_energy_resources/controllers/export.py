"""API-07 `GET /td/energy/resources/export?day=YYYY-MM-DD[&day_to=YYYY-MM-DD][&resources=gas,air]` (FR-12, R-24; W3-E).

Єдиний HTTP-маршрут модуля (A-10): `auth="user"`, група `td_energy.group_td_energy_user`; параметри проходять
суворі регулярні вирази й перевірки меж, у SQL потрапляють лише біндами; тексти помилок — без значень із запиту.
Джерело — SQL-view `td.energy.usage` (читання поза ACL, лише після перевірки групи). Книга — `xlsxwriter`
(`constant_memory`): лист «Ресурси» (інтервали за `ts_start, ресурс, потік`) і «Підсумок» (Σ за ресурсом і потоком).
Стовпці ціни й вартості — лише з `group_td_energy_cost`. Час у комірках — місцевий (Київ), `dd.mm.yyyy hh:mm`.
"""

import io
import re
from datetime import date

import xlsxwriter

from odoo import http
from odoo.http import request

from odoo.addons.td_energy.tools import dates

from ..tools.build import rparam_float

COST_GROUP = "td_energy.group_td_energy_cost"
USER_GROUP = "td_energy.group_td_energy_user"
MAX_ROWS = 200_000  # у тесті підміняється
FETCH = 5000
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CODE_RE = re.compile(r"^[a-z0-9_]{1,8}$")
FLOWS = {
    "import": "Імпорт",
    "export": "Експорт",
    "generation": "Генерація",
    "load": "Навантаження",
    "supply": "Надходження",
    "branch": "Гілка",
}
QUALITY = {
    "measured": "Виміряно",
    "estimated": "Оцінено",
    "interpolated": "Інтерпольовано",
    "missing": "Немає даних",
}
FROM_SQL = """
  FROM td_energy_usage u
  JOIN td_energy_resource r ON r.id = u.resource_id
  JOIN td_energy_meter m ON m.id = u.meter_id AND m.company_id IN %s
  LEFT JOIN td_energy_node n ON n.id = u.node_id
  LEFT JOIN td_energy_point p ON p.id = u.point_id
 WHERE u.day >= %s AND u.day <= %s AND r.code IN %s
"""
COUNT_SQL = "SELECT COUNT(*)" + FROM_SQL
ROWS_SQL = (
    "SELECT u.ts_start, r.name, r.uom_label, u.flow, COALESCE(n.code, p.code, m.code), u.qty, u.cost, u.quality"
    + FROM_SQL
    + " ORDER BY u.ts_start, r.sequence, r.id, u.flow, 5"
)


class TdEnergyResourcesExport(http.Controller):
    @staticmethod
    def _fail(status, text):
        return request.make_response(text, headers=[("Content-Type", "text/plain; charset=utf-8")], status=status)

    @staticmethod
    def _parse_day(value):
        if not isinstance(value, str) or not DATE_RE.match(value):
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None

    @http.route("/td/energy/resources/export", type="http", auth="user", methods=["GET"])
    def export(self, day=None, day_to=None, resources=None, **_kw):
        env = request.env
        if not env.user.has_group(USER_GROUP):
            return self._fail(403, "Немає доступу до Енергетики.")
        first = self._parse_day(day)
        last = self._parse_day(day_to) if day_to not in (None, "") else first
        today = dates.local_day(dates.now_utc(env))
        if not first or not last or last < first or last > today:
            return self._fail(400, "Невірна дата.")
        if (last - first).days + 1 > rparam_float(env, "export_max_days", 31.0):
            return self._fail(400, "Занадто великий діапазон дат.")
        active = {r.code for r in env["td.energy.resource"].sudo().search([])}
        codes = [c.strip() for c in resources.split(",")] if isinstance(resources, str) and resources else list(active)
        if len(set(codes)) != len(codes) or any(not CODE_RE.match(c) or c not in active for c in codes):
            return self._fail(400, "Невідомий ресурс.")
        env.flush_all()
        cr, companies = env.cr, tuple(env.companies.ids) or (env.company.id,)
        params = (companies, first, last, tuple(codes))
        cr.execute(COUNT_SQL, params)
        if cr.fetchone()[0] > MAX_ROWS:
            return self._fail(413, "Забагато рядків: звузьте період або перелік ресурсів.")
        cost = env.user.has_group(COST_GROUP)
        data = self._build(cr, params, cost)
        name = "energoresursy_%s.xlsx" % first.isoformat()
        headers = [
            ("Content-Type", XLSX),
            ("Content-Disposition", 'attachment; filename="%s"' % name),
            ("Content-Length", str(len(data))),
            ("Cache-Control", "no-store"),
        ]
        return request.make_response(data, headers=headers)

    @staticmethod
    def _build(cr, params, cost):
        """Книга xlsx: лист «Ресурси» потоком (`fetchmany`) і «Підсумок» з агрегатів, зібраних під час потоку."""
        buf = io.BytesIO()
        book = xlsxwriter.Workbook(buf, {"constant_memory": True})
        head = book.add_format({"bold": True, "bg_color": "#e5e7eb", "border": 1, "text_wrap": True})
        when = book.add_format({"num_format": "dd.mm.yyyy hh:mm"})
        qty_fmt, price_fmt, money_fmt = (
            book.add_format({"num_format": "# ##0.000"}),
            book.add_format({"num_format": "# ##0.0000"}),
            book.add_format({"num_format": "# ##0.00"}),
        )
        sheet = book.add_worksheet("Ресурси")
        columns = ["Ресурс", "Потік", "Об'єкт", "Початок (Київ)", "Кількість", "Одиниця"]
        columns += ["Ціна, ₴", "Вартість, ₴"] if cost else []
        sheet.write_row(0, 0, columns + ["Якість"], head)
        sheet.set_column(0, 1, 18)
        sheet.set_column(2, 2, 16)
        sheet.set_column(3, 3, 18)
        sheet.set_column(4, 8, 14)
        sums, row = {}, 0
        cr.execute(ROWS_SQL, params)
        while True:
            chunk = cr.fetchmany(FETCH)
            if not chunk:
                break
            for ts, res_name, uom, flow, obj, qty, amount, quality in chunk:
                row += 1
                qty, amount = qty or 0.0, amount or 0.0
                local = dates.to_local(ts).replace(tzinfo=None)
                sheet.write_string(row, 0, res_name)
                sheet.write_string(row, 1, FLOWS.get(flow, flow))
                sheet.write_string(row, 2, obj or "")
                sheet.write_datetime(row, 3, local, when)
                sheet.write_number(row, 4, qty, qty_fmt)
                sheet.write_string(row, 5, uom or "")
                col = 6
                if cost:
                    sheet.write_number(row, 6, round(amount / qty, 4) if qty else 0.0, price_fmt)
                    sheet.write_number(row, 7, amount, money_fmt)
                    col = 8
                sheet.write_string(row, col, QUALITY.get(quality, quality or ""))
                total = sums.setdefault((res_name, flow), [uom, 0.0, 0.0])
                total[1] += qty
                total[2] += amount
        summary = book.add_worksheet("Підсумок")
        columns = ["Ресурс", "Потік", "Кількість", "Одиниця"] + (["Вартість, ₴"] if cost else [])
        summary.write_row(0, 0, columns, head)
        summary.set_column(0, 4, 18)
        for i, ((res_name, flow), (uom, qty, amount)) in enumerate(sums.items(), start=1):
            summary.write_string(i, 0, res_name)
            summary.write_string(i, 1, FLOWS.get(flow, flow))
            summary.write_number(i, 2, round(qty, 3), qty_fmt)
            summary.write_string(i, 3, uom or "")
            if cost:
                summary.write_number(i, 4, round(amount, 2), money_fmt)
        book.close()
        return buf.getvalue()
