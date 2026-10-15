from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo.tests import tagged

from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")


@tagged(*TAGS)
class TestRotatePushEvents(F3DTelemetryCase):
    def event(self, n, ts):
        return self.env["f3d.push.event"].create({"event_id": "%064x" % n, "route": "lpr", "ts": ts})

    def test_rotate_events(self):
        now = datetime(2026, 11, 14, 2, 40)
        with freeze_time(now):
            old = self.event(1, now - timedelta(days=31))
            young = self.event(2, now - timedelta(days=29))
            self.env["f3d.reading"]._cron_rotate()
            self.assertFalse(old.exists())
            self.assertTrue(young.exists())

    def test_rotate_events_batches(self):
        from odoo.addons.factory3d_telemetry.models import f3d_reading

        now = datetime(2026, 11, 14, 2, 40)
        with freeze_time(now):
            olds = self.env["f3d.push.event"]
            for k in range(5):
                olds |= self.event(10 + k, now - timedelta(days=40, minutes=k))
            with patch.object(f3d_reading, "ROTATE_BATCH", 2):
                self.env["f3d.reading"]._cron_rotate()
            self.assertFalse(olds.exists())
