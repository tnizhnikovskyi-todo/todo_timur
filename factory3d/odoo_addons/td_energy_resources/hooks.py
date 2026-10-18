"""post_init_hook / uninstall_hook (W3_SPEC 5.5, 5.6). Каркас: тіло пише воркер A.

Контракт для воркерів (імена функцій фіксовані): `_set_el_on_meters(env)`, `_ensure_resource_signals(env)` (читає
`data/resource_signals.csv`, `data/resource_sources.csv`), `_seed_points_meters(env)` (читає `data/resource_points.csv`,
`data/resource_meters.csv`), `_bind_react_signals(env)`;
після `_seed_points_meters` — `env["td.energy.point"]._td_bind_extra()`.
"""


def post_init_hook(env):
    """5.5: кроки 1…6 (ідемпотентні; ті самі функції викликає міграція)."""


def uninstall_hook(env):
    """5.6: видаляє неелектричні лічильники, знімає `e_react_signal_id`, свої крони й параметри."""
