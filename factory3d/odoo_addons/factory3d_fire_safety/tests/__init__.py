# test_data_sync.py — pytest/unittest поза Odoo, тут не підключається.
# common.py (FireCase) використовується W1+ тестами; тести W2…W5 підключаються їхніми воркерами:
# from . import test_hooks, test_sync, …
from . import test_w0
from . import common
from . import test_norms
from . import test_event
from . import test_evacuation
from . import test_sync
from . import test_security_readonly
from . import test_requests
from . import test_drill
from . import test_passage_source
