"""API-12: категорії зберігання й стратегії списання (F03-02, F03-06); довідники зони (F03-03, F03-04); ваги запасу.

Правила як у API-01…10: JSON-RPC, auth user, `{ok: true, …}` або `{ok: false, code, message}` (HTTP 200). Читання —
від імені користувача (дані Odoo — під sudo лише в межах відповіді); створення/зміна/видалення категорії — прямий
виклик менеджера
з підтвердженням (CD-20): `confirm: true`."""

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..services import capacity
from .constructor import fail, find_site, is_manager

MAX_CODES = 5000


class TdStorageController(http.Controller):
    # --- API-12 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/storage_categories', type='jsonrpc', auth='user', methods=['POST'])
    def storage_categories(self, op='list', id=None, vals=None, confirm=None, **kw):
        """`op`: `list` → `{categories, strategies, functions, attrs}`; `save` (`id?`, `vals`) → `{category}`;
        `delete` (`id`)."""
        env = request.env
        company = env.company
        if op == 'list':
            functions, attrs = capacity.ensure_zone_terms(env)
            return {
                'ok': True,
                'categories': capacity.list_categories(env, company),
                'strategies': capacity.list_strategies(env),
                'functions': functions,
                'attrs': attrs,
            }
        if op not in ('save', 'delete'):
            return fail('validation', "op: очікується list, save або delete.")
        if not is_manager(env):
            return fail('rights', "Категорії зберігання змінює лише менеджер конструктора.")
        if confirm is not True:
            return fail('validation', "Підтвердіть зміну категорій зберігання в Odoo: confirm = true.")
        try:
            with env.cr.savepoint():
                if op == 'delete':
                    capacity.delete_category(env, company, id if isinstance(id, int) else 0)
                    return {'ok': True, 'id': id}
                if not isinstance(vals, dict):
                    return fail('validation', "vals має бути об'єктом.")
                cat = capacity.save_category(env, company, vals, id if isinstance(id, int) else None)
                return {'ok': True, 'category': capacity.category_dict(cat)}
        except LookupError as exc:
            return fail('not_found', str(exc))
        except ValueError as exc:
            return fail('validation', str(exc))
        except AccessError as exc:
            return fail('rights', str(exc))
        except UserError as exc:
            return fail('validation', str(exc))

    # --- API-12 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/removal_strategies', type='jsonrpc', auth='user', methods=['POST'])
    def removal_strategies(self, **kw):
        return {'ok': True, 'strategies': capacity.list_strategies(request.env)}

    # --- F03-08, cell_load -----------------------------------------------------------------------
    @http.route('/f3d/constructor/storage/loads', type='jsonrpc', auth='user', methods=['POST'])
    def storage_loads(self, site_id=None, codes=None, **kw):
        """Залишки й вага запасу за кодами комірок площадки й макс. вага комірки:
        `{loads: {код: {qty, weight_kg}}, limits}`."""
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        site = site.sudo()
        limits = capacity.site_cell_limits(site)
        if codes is not None:
            if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes) or len(codes) > MAX_CODES:
                return fail('validation', "codes має бути списком рядків (до %d)." % MAX_CODES)
            wanted = codes
        else:
            wanted = list(limits)
        return {
            'ok': True,
            'loads': capacity.stock_loads(env, wanted),
            'limits': {c: limits[c] for c in wanted if c in limits},
        }
