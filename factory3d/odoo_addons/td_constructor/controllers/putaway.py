"""API-15: куди піде товар і чи вміститься (F04-05, F04-06).

Правила як у API-01…10: JSON-RPC, auth user, `{ok: true, …}` або `{ok: false, code, message}` (HTTP 200); читання —
від імені користувача (площадка під record rules), дані Odoo читаються під sudo лише в межах відповіді."""

from odoo import http
from odoo.http import request

from ..services import capacity, putaway
from .constructor import fail, find_site

MAX_CODES = 500


def _num(value, default=0.0):
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) and value >= 0 else default


class TdPutawayController(http.Controller):
    # --- API-15 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/putaway/where', type='jsonrpc', auth='user', methods=['POST'])
    def putaway_where(
        self,
        site_id=None,
        product_id=None,
        quantity=None,
        location_id=None,
        location_code=None,
        package_type_id=None,
        **kw,
    ):
        """«Куди покладе Odoo»: товар/упаковка/кількість/локація приймання → місце за стратегією розміщення
        (лише застосовані правила `stock.putaway.rule`)."""
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        site = site.sudo()
        product = env['product.product'].sudo().browse(product_id if isinstance(product_id, int) else 0).exists()
        if not product:
            return fail('validation', "product_id: товар не знайдено.")
        Loc = env['stock.location'].sudo().with_context(active_test=False)
        if isinstance(location_id, int) and not isinstance(location_id, bool):
            location = Loc.browse(location_id).exists()
        elif isinstance(location_code, str) and location_code:
            location = Loc.search(['|', ('td_code', '=', location_code), ('barcode', '=', location_code)], limit=1)
        else:
            location = putaway.default_location_in(site)
        if not location or (location.company_id and location.company_id != site.company_id):
            return fail('not_found', "Локацію приймання не знайдено.")
        package = None
        if isinstance(package_type_id, int) and not isinstance(package_type_id, bool):
            package = env['stock.package.type'].sudo().browse(package_type_id).exists() or None
        result = putaway.where(env, site, product, _num(quantity, 1.0), location, package)
        return dict(ok=True, estimate=False, **result)

    # --- API-15 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/putaway/fit', type='jsonrpc', auth='user', methods=['POST'])
    def putaway_fit(self, site_id=None, product_id=None, package_type_id=None, codes=None, **kw):
        """«Чи вміститься»: без `product_id`/`codes` — усі правила розміщення чернетки (`{uid: [{code, reason}]}`);
        з ними — товар/упаковка проти вказаних комірок (`{код: [причини]}`). Невідоме пропускається."""
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        site = site.sudo()
        if product_id is None and package_type_id is None and codes is None:
            return {'ok': True, 'rules': putaway.fit_rules(site)}
        if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes) or len(codes) > MAX_CODES:
            return fail('validation', "codes має бути списком рядків (до %d)." % MAX_CODES)
        product = env['product.product'].sudo().browse(product_id if isinstance(product_id, int) else 0).exists()
        package = (
            env['stock.package.type'].sudo().browse(package_type_id if isinstance(package_type_id, int) else 0).exists()
        )
        if not product and not package:
            return fail('validation', "Вкажіть товар або тип упаковки.")
        item = putaway.item_of(env, product, package)
        scene = capacity.plan_check_scene(site, {})
        limits = capacity.site_cell_limits(site)
        cells = {code: cell for slot in scene.slots.values() for code, cell in scene.slot_cells(slot).items()}
        out = {}
        for code in codes:
            if code in cells:
                out[code] = putaway.fit_problems(
                    item, cells[code], limits.get(code) or cells[code]['max_load_kg'] or 0.0
                )
        return {'ok': True, 'items': out}
