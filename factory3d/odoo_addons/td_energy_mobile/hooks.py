"""post_init_hook / uninstall_hook (W4_SPEC H.5.3, H.5.4). Каркас: тіло пише воркер C.

Контракт: `_seed_template(env)` (ідемпотентно: шаблон `TP-GRSH` завантажує XML `noupdate`, функція лише перевіряє;
обходи не створює); `uninstall_hook`: `td.energy.event.kind='round'` → `manual`, зняти власні крони й параметри.
"""


def post_init_hook(env):
    """H.5.3: `_seed_template(env)` (ідемпотентно)."""


def uninstall_hook(env):
    """H.5.4: події `round` → `manual`; видаляє власні крон-записи й параметри `td.energy_mobile.*`."""
