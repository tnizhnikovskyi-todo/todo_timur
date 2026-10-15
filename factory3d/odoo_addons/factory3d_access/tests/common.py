import json
from unittest import mock

from odoo.tests import TransactionCase
from odoo.tools import file_open


def load_fixture(name):
    """Ответ BioStar (P-10) из tests/fixtures/<name>.json."""
    with file_open(f'factory3d_access/tests/fixtures/{name}.json') as fh:
        return json.load(fh)


def fixture_rows(name, collection):
    """Строки коллекции фикстуры: fixture_rows('users', 'UserCollection')."""
    return load_fixture(name)[collection]['rows']


class AccessCase(TransactionCase):
    """Общая база тестов factory3d_access: сеть запрещена (SPEC §13.1, DoD §14)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, f3d_no_commit=True))
        patcher = mock.patch(
            'requests.Session.request',
            side_effect=AssertionError('Сетевой вызов в юнит-тесте запрещён'))
        patcher.start()
        cls.addClassCleanup(patcher.stop)

    load_fixture = staticmethod(load_fixture)
    fixture_rows = staticmethod(fixture_rows)
