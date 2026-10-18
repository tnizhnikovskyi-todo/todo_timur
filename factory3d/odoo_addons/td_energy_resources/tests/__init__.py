# Воркери цей файл не правлять. Стендові тести (`stand/`) — pytest проти стенда, тут не імпортуються.
from . import test_w3_data, test_w3_integrate, test_w3_estimate, test_w3_cost, test_w3_usage  # noqa: F401  (A)
from . import test_w3_backfill  # noqa: F401  (A)
from . import test_w3_dashboard, test_w3_export, test_w3_security  # noqa: F401  (E)
from . import test_w3_opportunity, test_w3_detectors  # noqa: F401  (B)
from . import test_w3_ui, test_w3_hoot  # noqa: F401  (C)
