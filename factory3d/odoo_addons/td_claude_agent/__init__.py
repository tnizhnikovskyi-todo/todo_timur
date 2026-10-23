from . import models
from . import wizard


def _post_init_hook(env):
    """Стадії наявних проєктів → ролі за мітками (PM/AN/DV/QA)."""
    env["td.claude.role"]._td_map_stages()
