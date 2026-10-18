"""Міграція 19.0.1.0.0 (W3_SPEC 5.5, воркер A): `resource_id = el`, `mode = 'counter'` у наявних лічильників.

Увесь код — у `hooks` (ідемпотентний; ті самі функції викликає `post_init_hook`). Каркас.
"""


def migrate(cr, version):
    """Каркас."""
