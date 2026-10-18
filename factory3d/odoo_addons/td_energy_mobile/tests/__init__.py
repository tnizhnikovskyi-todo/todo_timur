# Воркер C цей файл не править. Стендові тести (`stand/`) — pytest проти стенда, тут не імпортуються.
from . import test_wh_contracts  # noqa: F401  (менеджер: C-06, C-07, API-H1 — `contracts/`)
from . import test_wh_template, test_wh_schedule, test_wh_round, test_wh_value  # noqa: F401  (C)
from . import test_wh_api, test_wh_security, test_wh_ui, test_wh_hoot  # noqa: F401  (C)
