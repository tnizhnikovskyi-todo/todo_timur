"""Хуки установки/видалення factory3d_constructor (SPEC §5.2, §5.3, R-24)."""

import json
import logging

from ..services import snapshot
from . import link, seed

_logger = logging.getLogger('odoo.addons.factory3d_constructor.hooks')

PARAM_PREFIX = 'factory3d.constructor.'
PARAM_PUBLISH = PARAM_PREFIX + 'publish_enabled'
PARAM_REPORT = PARAM_PREFIX + 'seed_report'

# §5.2: роль паспорта → категорія (решта → other)
CATEGORY_BY_ROLE = {}
for _category, _roles in {
    'machine': "beam_saw beam_saw_book sliding_table_saw vertical_panel_saw edgebander edgebander_laser nesting_cnc "
    "ptp_cnc "
    "throughfeed_drilling dowel_inserting hinge_insertion wide_belt_sander membrane_press glue_spray_booth "
    "manual_spray_booth automatic_spraying uv_line uv_oven drying box_machine case_clamp_auto case_clamp_manual "
    "shrink_line strapping stretch_wrapper briquetting_press compressor dust_extraction",
    'rack': "board_rack board_storage highbay_rack server_rack",
    'forklift': "forklift board_forklift tugger",
    'panel': "main_switchboard busbar_main busbar_dist substation acb tapoff pfc ats lighting_control",
    'robot': "robot_return sorting_cell",
}.items():
    for _role in _roles.split():
        CATEGORY_BY_ROLE[_role] = _category


def step_params(env):
    """Крок 1: publish_enabled за factory3d.base.environment (CB-10): True на test, False на prod."""
    params = env['ir.config_parameter'].sudo()
    if not params.get_param(PARAM_PUBLISH):
        environment = params.get_param('factory3d.base.environment') or 'test'
        params.set_param(PARAM_PUBLISH, 'True' if environment == 'test' else 'False')
        return environment
    return None


def step_categories(env):
    """Крок 2: f3d_category у паспортів base (лише де порожньо/other — ручні значення не перезаписуємо)."""
    Passport = env['f3d.equipment.passport'].sudo().with_context(active_test=False)
    changed = 0
    for passport in Passport.search([('f3d_category', 'in', ('other', False))]):
        category = CATEGORY_BY_ROLE.get(passport.role)
        if category and category != passport.f3d_category:
            passport.f3d_category = category
            changed += 1
    return changed


def step_seed(env, data):
    """Крок 3: площадка з seed (якщо немає)."""
    return seed.load_seed(env, data)


def step_baseline(env, site, created):
    """Крок 5: версія v1 «Імпорт із макета» (лише якщо в площадки ще немає версій)."""
    if site.version_ids:
        return None
    user = env.ref('base.user_root')
    version = snapshot.create_version(
        site.sudo().with_user(user),
        note="Імпорт із макета",
        report={'created': [], 'updated': [], 'archived': [], 'warnings': [], 'seed': created},
        is_seed=True,
    )
    return version


def run_seed_hook(env, data=None):
    """Кроки 3-6 для площадки seed; повертає звіт `seed_report` (R-24: повторний запуск дає той самий звіт)."""
    data = seed.normalize_seed(data or seed.read_seed())
    env = env(su=True)
    site, created, skipped, resolved = step_seed(env, data)
    if created:
        step_baseline(env, site, created)
    linked = link.link_existing(env, site)
    slots = env['f3d.slot'].search([('site_id', '=', site.id)])
    report = {
        'site_id': site.id,
        'created': {
            'layers': env['f3d.layer'].search_count([('site_id', '=', site.id)]),
            'slots': len(slots),
            'cells': sum(slots.mapped('cell_count')),
            'placements': env['f3d.placement'].search_count([('site_id', '=', site.id)]),
            'variants': len(resolved),
        },
        'linked': linked['linked'],
        'unlinked': linked['unlinked'],
        'skipped_variants': skipped,
    }
    env['ir.config_parameter'].sudo().set_param(PARAM_REPORT, json.dumps(report, ensure_ascii=False, sort_keys=True))
    return report


def post_init_hook(env):
    """Порядок: params → categories → seed → link → baseline → report (R-24); кожен крок ідемпотентний."""
    step_params(env)
    step_categories(env)
    try:
        with env.cr.savepoint():
            run_seed_hook(env)
    except Exception:
        _logger.exception("Seed «Меблеве підприємство» не завантажено; модуль встановлено без нього")


def uninstall_hook(env):
    """§5.3: видаляє лише власні ir.config_parameter; записи Odoo й знімки версій лишаються."""
    env['ir.config_parameter'].sudo().search([('key', '=like', PARAM_PREFIX + '%')]).unlink()
