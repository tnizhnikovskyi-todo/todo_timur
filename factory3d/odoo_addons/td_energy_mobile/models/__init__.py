# Порядок (W4_SPEC H.0): шаблони → обходи → розширення події → налаштування. Воркер C цей файл не править.
from . import td_energy_round_template  # noqa: F401  (C: M-H1, M-H2, M-H3)
from . import td_energy_round  # noqa: F401  (C: M-H4, M-H5, API-H1…API-H6)
from . import td_energy_event  # noqa: F401  (C: M-H6 `selection_add` 'round')
from . import res_config_settings  # noqa: F401  (C: M-H7)
